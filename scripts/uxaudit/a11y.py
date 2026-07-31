"""axe-core accessibility gate, split into violations we own and violations Streamlit owns.

Run by ``scripts/ux_audit.py --mode a11y``. Every page in ``pages.PAGES`` is
scanned at every viewport in ``pages.VIEWPORTS`` with the axe-core build
vendored in ``vendor/axe.min.js`` (see that directory's README for why it is
committed rather than fetched).

Why the results are partitioned
-------------------------------
A raw axe run against this app is unusable as a gate. Roughly two-thirds of the
nodes it flags come from markup Streamlit emits and we cannot reach: the sidebar
``<section>`` carries ``aria-expanded`` on an element whose role does not allow
it, ``stSidebarNavItems`` is a ``<ul>`` with non-``<li>`` children, and Streamlit
wraps no content in landmarks so ``region`` alone reports 15–44 nodes per page.
None of that is fixable without forking Streamlit. Gate on the raw output and
the job is permanently red, which means it gets ignored, which means the
failures we *can* fix ride along invisibly.

So results are partitioned against ``KNOWN_ACCEPTED``:

  **blocking** — everything else. Exits non-zero. These are ours.
  **accepted** — rules listed in ``KNOWN_ACCEPTED``. Reported, never blocking.

Two properties of that mechanism are deliberate and worth defending.

**It is a per-rule allowlist, not a severity threshold.** "Fail only on
critical" would be one line of code and would silence our own ``color-contrast``
failures (serious) while still letting Streamlit's ``aria-allowed-attr``
(critical) block the build — precisely inverted. Severity describes user impact;
it says nothing about who can fix it. Only rule identity does.

**Accepted violations are still printed, with node counts.** A silent allowlist
rots: Streamlit fixes ``region``, or our own code starts tripping a rule that is
on the list for an unrelated reason, and nobody notices because the entry has no
output. So the report ends with the accepted section, and any accepted rule that
produced *zero* violations is called out by name as a retirement candidate.
Reviewing that tail is the maintenance task this file asks of you.

Adding to ``KNOWN_ACCEPTED`` is a design decision, not a fix. An entry needs a
reason that says *why it is unreachable from this repo* — "Streamlit renders
this" — not "this is hard" or "this is low priority". Anything we could fix in
``dashboard/`` belongs in the backlog, failing, until it is fixed.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import Page, sync_playwright

from scripts.uxaudit.pages import PageSpec
from scripts.uxaudit.readiness import establish_session, wait_for_base_style

# The vendored scanner. Read from disk at scan time; nothing here touches the
# network. Pinned to the version recorded in vendor/README.md — the allowlist
# below is calibrated against that build's rule set.
_AXE_PATH = Path(__file__).parent / "vendor" / "axe.min.js"

# Highest impact first, for report ordering and for sorting within a section.
_IMPACT_ORDER: dict[str, int] = {
    "critical": 0,
    "serious": 1,
    "moderate": 2,
    "minor": 3,
    "unknown": 4,
}

# Longest outerHTML snippet kept per sample. axe already elides deep subtrees;
# this keeps a single long <div class="st-emotion-cache-...">  from eating the
# terminal.
_SAMPLE_CHARS = 200
_MAX_SAMPLES = 3

# ---------------------------------------------------------------------------
# The allowlist
# ---------------------------------------------------------------------------
# Rules we do not gate on, each with the reason it is unreachable from this
# repo. Read the module docstring before adding an entry.
#
# Everything NOT listed here blocks. In particular these four are non-empty
# today and are meant to fail:
#
#   color-contrast      → the sidebar search input's placeholder and st.metric
#                         delta text (<p>-7</p>), from our CSS in
#                         dashboard/ui/theme.py. Fixed by WP-8.
#   heading-order       → st.markdown("##### ...") / ("### ...") calls that skip
#                         a level (h5 under h2 on Overview, h3 under h1 on
#                         Failing Checks and What Changed). Fixed by WP-9.
#   empty-table-header  → the Failing Checks table renders without
#                         hide_index=True, so the index column gets a blank
#                         <th>. Fixed by WP-9.
#   scrollable-region-  → dashboard/ui/theme.py's share_link_block() puts a long
#     focusable           URL in st.code(); at 390px the resulting <pre>
#                         overflows and has no tabindex, so it cannot be
#                         scrolled by keyboard. Ours: we chose st.code, and a
#                         wrapping st.text_input or st.markdown avoids it.
#                         Mobile-only, and only on pages whose share URL carries
#                         query params (repo_detail, needing_attention,
#                         what_changed, ownership_views).
#
# When those land, the gate goes green on its own. Do not move them here.
KNOWN_ACCEPTED: dict[str, str] = {
    "aria-allowed-attr": (
        "Streamlit puts aria-expanded on section[data-testid=\"stSidebar\"] and on "
        "its own popover containers, whose roles do not permit the attribute; the "
        "markup is emitted by Streamlit's frontend bundle, not by any template we own."
    ),
    "list": (
        "Streamlit's page navigation renders <ul data-testid=\"stSidebarNavItems\"> "
        "with non-<li> wrapper divs between the list and its items; the nav is built "
        "by st.navigation and its DOM is not injectable from Python."
    ),
    "listitem": (
        "The mirror of the `list` finding — the same st.navigation markup leaves <li> "
        "elements without a conforming list parent, so both rules fire on one "
        "upstream defect."
    ),
    "region": (
        "Streamlit wraps no page content in a landmark, so every top-level block it "
        "emits is reported as outside a region (15-44 nodes per page). Landmarks "
        "would have to come from Streamlit's own layout containers; st.markdown "
        "cannot enclose sibling widgets."
    ),
}


@dataclass(frozen=True)
class Violation:
    """One axe rule failing on one page at one viewport.

    Aggregated per rule rather than per node: axe reports ``region`` as 44
    separate nodes on Overview, and 44 near-identical report lines hide the
    other findings. ``count`` and ``samples`` keep the detail that matters.

    Attributes:
        rule: axe rule id, e.g. ``color-contrast``. The allowlist key.
        impact: ``minor`` | ``moderate`` | ``serious`` | ``critical``, or
            ``unknown`` when axe reports no impact for the rule.
        count: Number of offending nodes.
        help: axe's human-readable help string for the rule.
        samples: Up to three truncated outerHTML snippets, to locate the nodes.
        page: ``PageSpec.name``.
        viewport: Viewport key from ``pages.VIEWPORTS``, e.g. ``desktop``.
    """

    rule: str
    impact: str
    count: int
    help: str
    samples: list[str]
    page: str
    viewport: str


def _axe_source() -> str:
    """Read the vendored axe-core bundle.

    Raises:
        FileNotFoundError: With a pointer to the vendor README, since a missing
            bundle means an incomplete checkout (or someone gitignored it) and
            the fix is to restore the file, not to fetch one.
    """
    if not _AXE_PATH.exists():
        raise FileNotFoundError(
            f"Vendored axe-core not found at {_AXE_PATH}. It is committed to this "
            f"repo on purpose — see {_AXE_PATH.parent / 'README.md'}. Restore it "
            "from git rather than downloading a different version, or the "
            "KNOWN_ACCEPTED allowlist no longer matches the scanner."
        )
    return _AXE_PATH.read_text(encoding="utf-8")


def run_axe(page: Page) -> list[dict]:
    """Inject vendored axe-core and return its raw violations list.

    Scans the whole document with no exclusions. Excluding Streamlit's chrome
    would be the obvious way to quieten the noise, but it also hides our own
    failures — the sidebar search input's contrast bug is *inside* the sidebar
    we would be excluding. The allowlist filters by rule instead, which is
    precise about who owns what; a DOM exclusion is not.

    Args:
        page: A Playwright page with the target already loaded and settled.

    Returns:
        axe's ``violations`` array as parsed JSON: one entry per failing rule,
        each with ``id``, ``impact``, ``help``, and a ``nodes`` list.
    """
    # Re-injected after every navigation, since add_script_tag does not survive
    # a page load. Guarded so repeated calls on one loaded page are cheap.
    if not page.evaluate("() => typeof window.axe !== 'undefined'"):
        page.add_script_tag(content=_axe_source())

    # resultTypes: ['violations'] tells axe to skip collecting node detail for
    # passes/incomplete/inapplicable, which is most of the runtime on a page
    # with a few thousand nodes. `document` as the context means whole-document.
    raw = page.evaluate(
        """
        async () => {
            const results = await window.axe.run(document, {
                resultTypes: ['violations'],
            });
            return JSON.stringify(results.violations);
        }
        """
    )
    return json.loads(raw)


def _to_violations(raw: list[dict], *, page_name: str, viewport: str) -> list[Violation]:
    """Collapse axe's raw per-rule output into ``Violation`` records."""
    out: list[Violation] = []
    for entry in raw:
        nodes = entry.get("nodes") or []
        samples = [
            _truncate(node.get("html", ""))
            for node in nodes[:_MAX_SAMPLES]
            if node.get("html")
        ]
        out.append(
            Violation(
                rule=entry.get("id", "<unknown-rule>"),
                # axe leaves impact null for a handful of rules; normalise so
                # sorting and report formatting never see None.
                impact=entry.get("impact") or "unknown",
                count=len(nodes),
                help=entry.get("help", ""),
                samples=samples,
                page=page_name,
                viewport=viewport,
            )
        )
    return out


def _truncate(html: str) -> str:
    """Flatten and shorten an outerHTML snippet for single-line report output."""
    flat = " ".join(html.split())
    if len(flat) <= _SAMPLE_CHARS:
        return flat
    return flat[: _SAMPLE_CHARS - 1] + "…"


def _page_url(base_url: str, spec: PageSpec) -> str:
    """Build the absolute URL for a page spec."""
    root = base_url.rstrip("/")
    url = f"{root}/{spec.path}" if spec.path else f"{root}/"
    if spec.query:
        url += f"?{urlencode(spec.query)}"
    return url


def _sort_key(violation: Violation) -> tuple[int, str, str, str]:
    """Order violations by severity, then deterministically for stable diffs."""
    return (
        _IMPACT_ORDER.get(violation.impact, _IMPACT_ORDER["unknown"]),
        violation.rule,
        violation.page,
        violation.viewport,
    )


def audit_all(
    base_url: str,
    *,
    pages: list[PageSpec],
    viewports: dict[str, tuple[int, int]],
) -> tuple[list[Violation], list[Violation]]:
    """Scan every (viewport, page) pair and partition the findings.

    One browser for the whole run; a fresh context per viewport so that no
    cookie, localStorage entry, or Streamlit session leaks between viewports and
    changes what renders. Teardown is unconditional — a page that fails to load
    must not leave a chromium process behind for CI to trip over later.

    Args:
        base_url: Origin of the running app, e.g. ``http://localhost:8612``.
        pages: Page specs to scan, from ``pages.resolve_pages``.
        viewports: Viewport key → ``(width, height)``.

    Returns:
        ``(blocking, accepted)``, each sorted severity-first. ``blocking`` is
        what the caller should exit non-zero on.
    """
    blocking: list[Violation] = []
    accepted: list[Violation] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for viewport_name, (width, height) in viewports.items():
                context = browser.new_context(viewport={"width": width, "height": height})
                try:
                    page = context.new_page()
                    # Run the entry script once for this context before touching
                    # any sub-page, so results do not depend on PAGES ordering.
                    establish_session(page, base_url)
                    for spec in pages:
                        found = _scan_one(
                            page,
                            _page_url(base_url, spec),
                            spec=spec,
                            viewport=viewport_name,
                        )
                        for violation in found:
                            target = (
                                accepted if violation.rule in KNOWN_ACCEPTED else blocking
                            )
                            target.append(violation)
                finally:
                    context.close()
        finally:
            browser.close()

    return sorted(blocking, key=_sort_key), sorted(accepted, key=_sort_key)


def _scan_one(
    page: Page,
    url: str,
    *,
    spec: PageSpec,
    viewport: str,
) -> list[Violation]:
    """Navigate, wait for the app to settle, and scan."""
    # networkidle covers the HTTP exchange; Streamlit then streams the render
    # over a websocket, which playwright does not count as network activity.
    # Hence the explicit settle. Scanning early yields a skeleton DOM and a
    # falsely clean report — the dangerous direction for a gate.
    page.goto(url, wait_until="networkidle", timeout=60_000)
    time.sleep(spec.settle_seconds)

    # Refuse to scan an unstyled render. Without the app's stylesheet the
    # colour-contrast rule has nothing to fail on, so the report comes back
    # cleaner than the truth — the same dangerous direction as scanning early.
    # See readiness.py for the underlying app bug (A0).
    wait_for_base_style(page, context=f"a11y {spec.name} @ {viewport}")

    raw = run_axe(page)
    return _to_violations(raw, page_name=spec.name, viewport=viewport)


def _format_group(violations: list[Violation]) -> list[str]:
    """Render violations grouped by rule, with per-page node counts."""
    lines: list[str] = []
    by_rule: dict[str, list[Violation]] = {}
    for violation in violations:
        by_rule.setdefault(violation.rule, []).append(violation)

    # Rule order follows the already-sorted input, so severity-first.
    for rule in dict.fromkeys(v.rule for v in violations):
        group = by_rule[rule]
        total = sum(v.count for v in group)
        lines.append(f"  [{group[0].impact}] {rule} — {total} node(s) across {len(group)} page/viewport pair(s)")
        if group[0].help:
            lines.append(f"      {group[0].help}")
        for violation in group:
            lines.append(
                f"      {violation.page} @ {violation.viewport}: {violation.count} node(s)"
            )
        # Samples from the worst offender only; three snippets per rule is
        # enough to find the CSS, and more turns the report into a DOM dump.
        worst = max(group, key=lambda v: v.count)
        for sample in worst.samples:
            lines.append(f"        · {sample}")
        lines.append("")
    return lines


def format_report(blocking: list[Violation], accepted: list[Violation]) -> str:
    """Human-readable stdout report. Blocking section first, then accepted.

    The accepted section is not decoration. It exists so a reader can check
    ``KNOWN_ACCEPTED`` against reality: every entry that still fires shows its
    node count, and every entry that fired on nothing is named as a retirement
    candidate. An allowlist nobody audits is just a disabled test.
    """
    lines: list[str] = ["", "=" * 78, "ACCESSIBILITY AUDIT (axe-core 4.10.2)", "=" * 78, ""]

    blocking_nodes = sum(v.count for v in blocking)
    lines.append(
        f"BLOCKING — {len(blocking)} finding(s), {blocking_nodes} node(s). "
        "These are ours to fix."
    )
    lines.append("-" * 78)
    if blocking:
        lines.extend(_format_group(blocking))
    else:
        lines.append("  None.")
        lines.append("")

    accepted_nodes = sum(v.count for v in accepted)
    lines.append(
        f"KNOWN AND ACCEPTED — {len(accepted)} finding(s), {accepted_nodes} node(s). "
        "Not gated on; see KNOWN_ACCEPTED in scripts/uxaudit/a11y.py."
    )
    lines.append("-" * 78)
    if accepted:
        for rule in dict.fromkeys(v.rule for v in accepted):
            group = [v for v in accepted if v.rule == rule]
            total = sum(v.count for v in group)
            lines.append(f"  [{group[0].impact}] {rule} — {total} node(s)")
            lines.append(f"      accepted because: {KNOWN_ACCEPTED[rule]}")
            per_page = ", ".join(
                f"{v.page}@{v.viewport}={v.count}" for v in group
            )
            lines.append(f"      {per_page}")
            lines.append("")
    else:
        lines.append("  None fired.")
        lines.append("")

    # The maintenance prompt: an allowlist entry with no matching violation is
    # either fixed upstream or was never real. Either way it should go.
    silent = [rule for rule in KNOWN_ACCEPTED if rule not in {v.rule for v in accepted}]
    if silent:
        lines.append(
            f"RETIRE? {len(silent)} accepted rule(s) produced zero violations in this run:"
        )
        for rule in silent:
            lines.append(f"  · {rule} — remove it from KNOWN_ACCEPTED, or confirm the")
            lines.append("    page that used to trip it is still in the audit inventory.")
        lines.append("")

    lines.append("=" * 78)
    return "\n".join(lines)

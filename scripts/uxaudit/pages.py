"""The audit inventory: which pages get captured, and at which viewports.

Two things here are easy to get wrong and are therefore pinned in code rather
than derived at runtime.

**URL paths.** Streamlit derives a multi-page URL slug from the *filename* in
``pages/``, not from the ``st.Page`` title. So the nav label "Checks Catalog"
lives at ``/glossary`` because the file is ``pages/06_glossary.py``. The paths
below are the verified-working ones; ``dashboard/lib/share.py`` maps the same
slugs for share links, and the two lists must agree.

**Settle times.** ``networkidle`` is not enough for this app. Streamlit streams
its render over the websocket after the initial HTTP exchange goes quiet, and
the data layer does a cold fetch of the ``wg-maintenance`` CSV on first paint.
Screenshotting too early yields empty chart frames and skeleton tables. The
per-page values below are measured, not guessed: Overview and Repo Detail pay
for charts plus the history load, Failing Checks and the Catalog build large
tables, the rest are cheap.

Seven pages are listed. ``pages/07_sql.py``, ``08_badges.py`` and
``10_cards.py`` are feature-flagged off by default and render a "not enabled"
stub, and ``99_healthz.py`` is a plain-text liveness endpoint, so none belong in
a visual baseline.

Note that every one of those files *is* still reachable by URL — Streamlit routes
to anything in ``pages/`` regardless of ``st.navigation`` — which is why each
gated page enforces its own flag (see ``dashboard/ui/page.py``).
``ownership_views`` stays in this inventory even though it is now hidden from the
nav when the snapshot carries no ownership fields: it remains routable, so it
still deserves regression cover.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    """One auditable page.

    Attributes:
        name: Filename slug used for the screenshot and report, e.g. ``overview``.
        path: URL path appended to the origin. Empty string for the root page.
        settle_seconds: Extra wait after ``networkidle``, for charts and the
            cold data fetch. See the module docstring for why this is needed.
        query: Extra query params to append, for pages that need a selection
            to render anything interesting.
    """

    name: str
    path: str
    settle_seconds: float = 6.0
    query: dict[str, str] | None = None


# Nav order, matching st.navigation() in streamlit_app.py: the five Health
# pages, then Ownership, then Meta.
PAGES: list[PageSpec] = [
    PageSpec(name="overview", path="", settle_seconds=7.0),
    PageSpec(name="repo_detail", path="repo_detail", settle_seconds=7.0),
    PageSpec(name="failing_checks", path="failing_checks", settle_seconds=4.0),
    PageSpec(name="needing_attention", path="needing_attention", settle_seconds=3.0),
    PageSpec(name="what_changed", path="what_changed", settle_seconds=3.0),
    PageSpec(name="ownership_views", path="ownership_views", settle_seconds=3.0),
    PageSpec(name="glossary", path="glossary", settle_seconds=4.0),
]

# 1440x1000 is a typical laptop browser; 390x844 is an iPhone 14 logical
# viewport, the width at which Streamlit collapses the sidebar and columns
# stack. Most responsive findings in the backlog only reproduce at the latter.
VIEWPORTS: dict[str, tuple[int, int]] = {
    "desktop": (1440, 1000),
    "mobile": (390, 844),
}


def resolve_pages(names: list[str] | None) -> list[PageSpec]:
    """Select page specs by name, preserving nav order.

    Args:
        names: Page slugs to keep. ``None`` or empty selects every page.

    Returns:
        The matching specs in ``PAGES`` order, not in the order requested, so
        that output ordering is stable regardless of how the CLI was invoked.

    Raises:
        ValueError: If any name is not a known page. The message lists the
            valid names, since a typo here is the most likely CLI mistake.
    """
    if not names:
        return list(PAGES)

    by_name = {page.name: page for page in PAGES}
    unknown = [name for name in names if name not in by_name]
    if unknown:
        raise ValueError(
            f"Unknown page(s): {', '.join(unknown)}. "
            f"Valid names: {', '.join(by_name)}"
        )
    wanted = set(names)
    return [page for page in PAGES if page.name in wanted]


# Regions excluded from the visual diff, keyed by "<viewport>/<page>.png". The
# literal "*" applies to every image.
#
# These are places the rendered output changes with wall-clock time rather than
# with code, so they would fail the gate on every run. The bulletin is the clear
# case: generate_weekly_bulletin() stamps "Generated: <timestamp>" at render
# time, which moves every minute.
#
# Keep this list short and specific. A mask hides real regressions inside it, so
# a whole-page or whole-column entry is almost always the wrong answer; the
# alternative for anything larger is to make the underlying value injectable so
# it can be pinned instead.
#
# Coordinates are (x0, y0, x1, y1) in captured-image pixels. They are inherently
# brittle against layout change, which is why the better long-term fix is to have
# capture.py tag volatile elements in the DOM and resolve boxes from there.
MASKS: dict[str, list[tuple[int, int, int, int]]] = {
    # "Generated: YYYY-MM-DD HH:MM UTC" inside the rendered bulletin.
    "desktop/what_changed.png": [(380, 630, 900, 665)],
    "mobile/what_changed.png": [(20, 700, 390, 760)],
}

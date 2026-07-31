"""Guards against auditing a page that never received the app's own styling.

This module exists because of a real bug in the dashboard, backlog item **A0**.
Streamlit's automatic ``pages/`` directory discovery serves any non-root URL
*before* ``streamlit_app.py`` executes. That file is where
``apply_base_style()`` lives, so a direct deep link to, say, ``/repo_detail``
on a cold server renders with none of the app's CSS: no Inter, no card
surfaces, no grade-pill colours, no sidebar gradient, and status chips
flattened into plain heading text. It also renders the raw filename-derived
nav instead of the configured one. The condition does not resolve on its own —
measured absent 45 seconds after ``networkidle``, and a rerun does not fix it.
Only a visit to ``/`` does.

Why that matters *here* rather than only in the backlog: an audit harness that
does not notice will happily record a baseline of the unstyled render, or scan
it for accessibility violations and report a clean bill of health because the
failing selectors never got their colours. Both outcomes are worse than a
failing run, because they look like success. This was observed: a
``--pages repo_detail`` capture produced a white sidebar and a stitched height
of 2947px against the styled 2912px, and exited 0.

So every audit entry point does two things:

1. **Establishes a session** by loading ``/`` once per browser context before
   visiting any sub-page. This is a workaround for A0, and it is why the
   default full-matrix run happens to produce correct output today: ``overview``
   is first in ``PAGES``, so it warms the session by accident. Doing it
   explicitly removes the dependency on inventory ordering.

2. **Asserts the marker is present** on every page before measuring it, and
   raises :class:`UnstyledPageError` when it is not. Keep this check even after
   A0 is fixed — step 1 becomes unnecessary, but step 2 is what stops a future
   regression from being silently baselined.

The marker is the ``--color-primary`` custom property, declared in the ``:root``
block that ``apply_base_style()`` injects. It is checked by searching the text
of ``<style>`` elements rather than by reading a computed style, because a
custom property resolves on ``:root`` even when the rest of the sheet is
missing in some browser states, and because the raw text check cannot be
satisfied by a partially-applied stylesheet.
"""
from __future__ import annotations

import os
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

# Custom property declared by dashboard/ui/theme.py's :root block. Its presence
# is proof that apply_base_style() ran *and* its output reached this document.
READINESS_MARKER = "--color-primary"

_MARKER_JS = """
(marker) => [...document.querySelectorAll('style')]
    .some((s) => s.textContent && s.textContent.includes(marker))
"""

# How long to keep polling for the marker once a page's own settle budget has
# already elapsed. Sized for the slowest environment rather than the fastest: a
# cold two-core CI runner pays for a network fetch, a pandas parse and a
# 171-repo scoring pass before the first paint, and the cost of waiting too long
# is a slow gate while the cost of waiting too little is a red one.
# UX_AUDIT_READY_TIMEOUT overrides it without a code change.
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("UX_AUDIT_READY_TIMEOUT", "75"))

_POLL_INTERVAL_SECONDS = 0.5

# Session warm-up needs the root page to have committed its style block, not to
# be fully painted, so it can be shorter than a capture settle.
_SESSION_TIMEOUT_SECONDS = float(os.environ.get("UX_AUDIT_SESSION_TIMEOUT", "90"))


class UnstyledPageError(RuntimeError):
    """Raised when a page rendered without the dashboard's base stylesheet.

    Signals backlog item A0 (or a regression of it). Deliberately fatal: the
    alternative is recording a baseline, or an accessibility verdict, that
    describes a page no real user sees.
    """


def base_style_present(page: Page) -> bool:
    """True when the injected base stylesheet is in this document."""
    try:
        return bool(page.evaluate(_MARKER_JS, READINESS_MARKER))
    except (PlaywrightError, PlaywrightTimeoutError):
        # An evaluate failure mid-navigation is not evidence of absence; the
        # caller's polling loop will ask again.
        return False


def wait_for_base_style(
    page: Page,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    context: str = "page",
) -> None:
    """Block until the base stylesheet is present, or fail loudly.

    Args:
        page: A page with the target URL already loaded and settled.
        timeout: Extra seconds to poll beyond whatever the caller already waited.
        context: Human label for the error message, e.g. ``"repo_detail @ mobile"``.

    Raises:
        UnstyledPageError: If the marker never appears. The message names the
            root cause so nobody spends an afternoon on the symptom.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if base_style_present(page):
            return
        time.sleep(_POLL_INTERVAL_SECONDS)

    raise UnstyledPageError(
        f"{context}: the dashboard's base stylesheet ({READINESS_MARKER}) never "
        f"appeared after {timeout:.0f}s of polling.\n\n"
        f"{describe_page(page)}\n\n"
        "Most likely causes, in the order worth checking:\n"
        "  1. The page raised. A Streamlit exception page carries no custom CSS, so "
        "     this guard fires on an app error rather than a styling problem — the "
        "     diagnostics above will show the traceback text if so.\n"
        "  2. The render did not finish inside the budget. Slow CI runners and a "
        "     cold upstream fetch can outlast it; raise the page's settle_seconds.\n"
        "  3. Backlog item A0 has regressed: a direct load of a non-root URL is "
        "     served by Streamlit's automatic pages/ discovery, which bypasses "
        "     streamlit_app.py and therefore apply_base_style().\n"
        "Capturing or scanning now would record a render no real user sees, which is "
        "why this is fatal rather than a warning."
    )


def describe_page(page: Page) -> str:
    """Best-effort snapshot of what the page actually contains.

    Called only on failure. Without this the guard reported that the stylesheet
    was missing and nothing about why, which turned a CI failure into a guessing
    exercise — the app raising and the app being slow look identical from the
    outside.
    """
    try:
        facts = page.evaluate(
            """() => {
                const text = (document.body && document.body.innerText) || '';
                const err = document.querySelector(
                    '[data-testid="stException"], [data-testid="stAlertContainer"]'
                );
                return {
                    url: location.href,
                    title: document.title,
                    styleTags: document.querySelectorAll('style').length,
                    stylesWithVars: [...document.querySelectorAll('style')]
                        .filter((s) => (s.textContent || '').includes('--color-')).length,
                    hasStreamlitApp: !!document.querySelector('.stApp'),
                    exceptionText: err ? (err.innerText || '').slice(0, 400) : '',
                    bodyExcerpt: text.replace(/\\s+/g, ' ').slice(0, 400),
                };
            }"""
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics must never mask the real error
        return f"  (could not inspect the page: {type(exc).__name__}: {exc})"

    lines = [
        "  Page state at failure:",
        f"    url            : {facts.get('url')}",
        f"    title          : {facts.get('title')!r}",
        f"    <style> tags   : {facts.get('styleTags')} "
        f"({facts.get('stylesWithVars')} containing --color-*)",
        f"    .stApp present : {facts.get('hasStreamlitApp')}",
    ]
    if facts.get("exceptionText"):
        lines.append(f"    ERROR ON PAGE  : {facts['exceptionText']}")
    lines.append(f"    body excerpt   : {facts.get('bodyExcerpt')!r}")
    return "\n".join(lines)


def establish_session(page: Page, base_url: str) -> None:
    """Load ``/`` so the entry script runs for this browser context.

    Workaround for A0, to be removed once WP-2A lands. Without it, whichever
    page happens to be visited first in a given context renders unstyled — so a
    narrowed run like ``--pages repo_detail`` silently audits a broken render
    while the full run gets away with it only because ``overview`` sorts first.

    Raises:
        UnstyledPageError: If even the root page fails to style, which means
            something more fundamental is wrong than A0.
    """
    root = base_url.rstrip("/") + "/"
    try:
        page.goto(root, wait_until="networkidle")
    except PlaywrightTimeoutError:
        page.goto(root, wait_until="load")

    wait_for_base_style(
        page,
        timeout=_SESSION_TIMEOUT_SECONDS,
        context=f"session warm-up via {root}",
    )

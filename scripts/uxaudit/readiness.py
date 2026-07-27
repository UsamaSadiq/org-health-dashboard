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
# already elapsed. Generous, because a cold server's first paint includes a
# full CSV fetch and a 171-repo scoring pass.
DEFAULT_TIMEOUT_SECONDS = 25.0

_POLL_INTERVAL_SECONDS = 0.5

# Session warm-up needs the root page to have committed its style block, not to
# be fully painted, so it can be shorter than a capture settle.
_SESSION_TIMEOUT_SECONDS = 40.0


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
        f"appeared after {timeout:.0f}s of polling.\n"
        "This is backlog item A0: a direct load of a non-root URL is served by "
        "Streamlit's automatic pages/ discovery, which bypasses streamlit_app.py "
        "and therefore apply_base_style(). Capturing or scanning now would record "
        "an unstyled render that no user reaching the app via / would ever see.\n"
        "Fix the app (WP-2A), or if this is unexpected, check that establish_session() "
        "ran for this browser context."
    )


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

"""Full-length page screenshots, produced by scroll-and-stitch.

``page.screenshot(full_page=True)`` is unusable on this app, and its failure
mode is silent — you get a well-formed PNG that happens to contain only the
first viewport. Streamlit does not scroll the document; it scrolls an inner
element, ``section[data-testid="stMain"]``, which is ``overflow-y: auto`` and
exactly viewport-tall. So ``document.scrollingElement.scrollHeight`` stays
pinned at the viewport height while the real content is several times taller.
Measured on this dashboard at 1440x1000, ``stMain.scrollHeight`` runs from
1000px (Needing Attention) to 5934px (Checks Catalog) with the document
reporting 1000px throughout.

The consequence is that every full-length capture has to be assembled by hand:
scroll the inner container in viewport-sized steps, screenshot the container's
rectangle at each step, and paste the results into one tall canvas. Three
things make that harder than it sounds, and each is handled below.

**The header occludes content at every slice boundary.** Streamlit's
``header[data-testid="stHeader"]`` is a *sibling* of the scroll container,
``position: absolute`` at the top of the main column, 60px tall, with an
opaque background. It does not move when ``stMain`` scrolls. A naive stitch
therefore repeats the header band every viewport *and* permanently loses the
60px of content sitting underneath it in every slice after the first. We
measure the header's rectangle at the top and the bottom of the scroll range;
if it did not move it is treated as a fixed occlusion, the scroll step is
reduced to ``slice_height - occlusion``, and the occluded band is cropped off
every slice but the first. Net effect: the header appears exactly once, at the
top, and no content is dropped. The measurement is empirical rather than a
hardcoded 60, so a Streamlit change to the header's size or positioning
degrades gracefully instead of silently corrupting baselines.

**The sidebar is a separate, non-scrolling column.** At desktop widths
``stMain`` starts at x=300 with the sidebar occupying x=0..300, and the sidebar
does not scroll with the content. Stitching the full viewport width would tile
the same sidebar down the whole image, which is both wrong-looking and noisy to
diff. Instead the *first* slice is captured full-width — so the sidebar is
present, once, and stays under regression cover — and every subsequent slice is
clipped to the main column and pasted at the main column's x offset. The
resulting left-hand gutter below the first viewport is pre-filled with the app
background colour sampled from the live DOM, so it is flat and contributes
nothing to a pixel diff. At mobile widths the sidebar is collapsed to zero
width and the main column already spans the viewport, so this special case
collapses to a no-op.

**The last slice overlaps the previous one.** The maximum scroll offset is
``scrollHeight - clientHeight``, which is rarely a whole multiple of the step,
so the final screenshot re-covers content already written. Rather than assume
the arithmetic, each slice's true content offset is read back from the DOM
after scrolling (the browser clamps, and the values are fractional) and the
already-written region is cropped off the top of the slice. The same code path
absorbs sub-pixel scroll drift anywhere in the page, not just at the end.

Determinism, because these images are checked in as baselines: device pixel
ratio 1, reduced-motion emulated (the app ships a ``prefers-reduced-motion``
block that collapses its own transitions), forced light colour scheme, and
Streamlit's churn-prone chrome — the toolbar, the "Running…" status widget, the
loading decoration bar — hidden. Web fonts are awaited before capture; the
theme pulls Inter from Google Fonts, and a missed load silently reflows every
line of text.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from PIL import Image
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from scripts.uxaudit.pages import PageSpec
from scripts.uxaudit.readiness import establish_session, wait_for_base_style

# The Streamlit scroll container. Everything hinges on this selector; the
# document-level fallback below exists in case a future Streamlit release
# changes it.
MAIN_SELECTOR = "section[data-testid='stMain']"

# Pause after each scroll step. Plotly figures below the fold are not painted
# until they intersect the viewport, so capturing immediately after setting
# scrollTop yields blank chart areas.
SLICE_SETTLE_SECONDS = 0.45

# Shorter pause for the warm-up pass, which only needs to trigger rendering,
# not to produce pixels.
PRERENDER_SETTLE_SECONDS = 0.25

NAVIGATION_TIMEOUT_MS = 60_000

# Chromium flags aimed purely at byte-stable output across machines and runs.
BROWSER_ARGS = [
    "--force-color-profile=srgb",
    "--hide-scrollbars",
    "--font-render-hinting=none",
    "--disable-lcd-text",
    "--disable-partial-raster",
]

# Suppresses the parts of Streamlit's chrome that change between runs without
# any code change on our side. Deliberately does *not* set `animation: none`:
# some Streamlit elements fade in from opacity 0 via keyframes, and cancelling
# the animation outright can leave them invisible. Collapsing the duration
# instead lands them on their end state, mirroring the app's own
# prefers-reduced-motion block in dashboard/ui/theme.py.
CAPTURE_CSS = """
[data-testid='stToolbar'],
[data-testid='stStatusWidget'],
[data-testid='stDecoration'],
[data-testid='stAppDeployButton'] {
  display: none !important;
}
::-webkit-scrollbar { width: 0 !important; height: 0 !important; }
* { scrollbar-width: none !important; }
*, *::before, *::after {
  animation-duration: 0.001ms !important;
  animation-delay: 0s !important;
  transition-duration: 0.001ms !important;
  transition-delay: 0s !important;
  scroll-behavior: auto !important;
}
"""

# Measures the scroll container and the geometry of the column we capture.
# Returns viewport-relative integers plus the app background colour, so the
# Python side never has to guess at layout.
_MEASURE_JS = """
() => {
  const rgb = (value) => {
    const m = /rgba?\\(([^)]+)\\)/.exec(value || '');
    if (!m) return null;
    const parts = m[1].split(',').map((n) => parseFloat(n));
    if (parts.length >= 4 && parts[3] === 0) return null;   // transparent
    return [Math.round(parts[0]), Math.round(parts[1]), Math.round(parts[2])];
  };
  const background = (() => {
    for (const sel of ['.stApp', 'body', 'html']) {
      const el = document.querySelector(sel);
      if (!el) continue;
      const c = rgb(getComputedStyle(el).backgroundColor);
      if (c) return c;
    }
    return [255, 255, 255];
  })();

  const main = document.querySelector("section[data-testid='stMain']");
  if (main) {
    const r = main.getBoundingClientRect();
    return {
      mode: 'main',
      column_x: Math.round(r.x),
      column_y: Math.round(r.y),
      width: main.clientWidth,
      height: main.clientHeight,
      content_height: main.scrollHeight,
      background: background,
    };
  }
  // Fallback: a Streamlit that scrolls the document after all.
  const doc = document.scrollingElement;
  return {
    mode: 'document',
    column_x: 0,
    column_y: 0,
    width: doc.clientWidth,
    height: window.innerHeight,
    content_height: doc.scrollHeight,
    background: background,
  };
}
"""

# The header is the only overlay this app has (nothing is position: fixed or
# sticky), so a single rectangle is enough to characterise the occlusion.
_HEADER_RECT_JS = """
() => {
  const h = document.querySelector("header[data-testid='stHeader']");
  if (!h) return null;
  const style = getComputedStyle(h);
  if (style.display === 'none' || style.visibility === 'hidden') return null;
  const r = h.getBoundingClientRect();
  if (r.height <= 0 || r.width <= 0) return null;
  return {top: r.top, bottom: r.bottom};
}
"""


@dataclass(frozen=True)
class _Geometry:
    """Everything needed to stitch, measured from the live DOM."""

    mode: str  # "main" (the Streamlit scroll container) or "document"
    column_x: int  # viewport x of the scrolling column
    column_y: int  # viewport y of the scrolling column
    width: int  # width of one slice
    height: int  # height of one slice — the container's clientHeight
    content_height: int  # full scrollable content height
    background: tuple[int, int, int]

    @property
    def max_scroll(self) -> int:
        return max(0, self.content_height - self.height)

    @property
    def sidebar_gutter(self) -> bool:
        """True when a non-scrolling column sits to the left of the content.

        A positive x offset is the signal: at desktop widths the expanded
        sidebar pushes stMain to x=300, while a collapsed (mobile) sidebar has
        zero width and leaves stMain at x=0.
        """
        return self.column_x > 0

    @property
    def canvas_width(self) -> int:
        return self.column_x + self.width if self.sidebar_gutter else self.width

    @property
    def paste_x(self) -> int:
        return self.column_x if self.sidebar_gutter else 0


def _measure(page: Page) -> _Geometry:
    raw = page.evaluate(_MEASURE_JS)
    return _Geometry(
        mode=str(raw["mode"]),
        column_x=int(raw["column_x"]),
        column_y=int(raw["column_y"]),
        width=int(raw["width"]),
        height=int(raw["height"]),
        content_height=int(raw["content_height"]),
        background=tuple(int(c) for c in raw["background"]),  # type: ignore[arg-type]
    )


def _scroll_to(page: Page, geom: _Geometry, top: int) -> float:
    """Scroll the container to `top` and return the offset the browser settled on.

    Never trust the requested value: the browser clamps to the scrollable range
    and reports a fractional result. The stitcher uses the returned figure to
    place the slice, which is what makes overlap handling exact.
    """
    if geom.mode == "main":
        return float(
            page.evaluate(
                """([selector, top]) => {
                    const el = document.querySelector(selector);
                    el.scrollTop = top;
                    return el.scrollTop;
                }""",
                [MAIN_SELECTOR, top],
            )
        )
    return float(
        page.evaluate(
            "(top) => { window.scrollTo(0, top); return window.scrollY; }",
            top,
        )
    )


def _header_rect(page: Page) -> dict[str, float] | None:
    return page.evaluate(_HEADER_RECT_JS)


def _wait_for_fonts(page: Page) -> None:
    """Block until webfonts are painted, or give up quietly.

    theme.py @imports Inter from Google Fonts. If capture races the font load,
    every text run reflows and the diff is total but meaningless.
    """
    try:
        page.wait_for_function("() => document.fonts && document.fonts.status === 'loaded'", timeout=10_000)
    except (PlaywrightTimeoutError, PlaywrightError):
        pass


def _prerender(page: Page, geom: _Geometry) -> dict[str, float] | None:
    """Walk the full scroll range once, then return to the top.

    Two jobs. It forces lazily-painted content (Plotly charts, dataframes)
    to render, which also means `content_height` can only be trusted *after*
    this pass. And it samples the header rectangle at the bottom of the range,
    which is how the caller decides whether the header is a fixed occlusion.

    Returns the header rectangle observed at maximum scroll, or None.
    """
    bottom_header: dict[str, float] | None = None
    step = max(1, geom.height // 2)
    for target in list(range(0, geom.max_scroll, step)) + [geom.max_scroll]:
        _scroll_to(page, geom, target)
        time.sleep(PRERENDER_SETTLE_SECONDS)
    bottom_header = _header_rect(page)
    _scroll_to(page, geom, 0)
    time.sleep(SLICE_SETTLE_SECONDS)
    return bottom_header


def _occlusion_height(
    geom: _Geometry,
    top_header: dict[str, float] | None,
    bottom_header: dict[str, float] | None,
) -> int:
    """Height of the fixed band that hides the top of every slice.

    A header only occludes if it is still in the same place after scrolling to
    the bottom — otherwise it scrolled away with the content and the slices
    need no correction. Returns 0 when there is nothing to correct for.
    """
    if not top_header or not bottom_header:
        return 0
    # Moved with the content ⇒ not an overlay.
    if abs(top_header["top"] - bottom_header["top"]) > 1:
        return 0
    overlap = round(top_header["bottom"] - geom.column_y)
    if overlap <= 0:
        return 0
    # Absurd result (a header taller than the viewport) means the measurement
    # is not describing what we think it is; stitch without a correction rather
    # than crop the whole page away.
    if overlap >= geom.height:
        return 0
    return int(overlap)


def _build_url(base_url: str, spec: PageSpec) -> str:
    root = base_url.rstrip("/")
    url = f"{root}/{spec.path.lstrip('/')}" if spec.path else f"{root}/"
    if spec.query:
        url += f"?{urlencode(spec.query)}"
    return url


def _screenshot(page: Page, *, x: int, y: int, width: int, height: int) -> Image.Image:
    """Grab a viewport rectangle. Uses clip rather than an element screenshot
    because element screenshots scroll the target into view, which would undo
    the scroll position we just set."""
    raw = page.screenshot(clip={"x": x, "y": y, "width": width, "height": height})
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _stitch(page: Page, geom: _Geometry, occlusion: int) -> Image.Image:
    canvas = Image.new("RGB", (geom.canvas_width, geom.content_height), geom.background)

    # Step short by the occluded band so the content it hides is still picked
    # up by the following slice.
    step = max(1, geom.height - occlusion)
    targets = list(range(0, geom.max_scroll, step))
    if geom.max_scroll not in targets:
        targets.append(geom.max_scroll)

    written = 0  # canvas rows filled so far == content rows already captured
    for index, target in enumerate(targets):
        if written >= geom.content_height:
            break

        actual = _scroll_to(page, geom, target)
        time.sleep(SLICE_SETTLE_SECONDS)

        first = index == 0
        full_width = first and geom.sidebar_gutter
        slice_img = _screenshot(
            page,
            x=0 if full_width else geom.column_x,
            y=geom.column_y,
            width=geom.canvas_width if full_width else geom.width,
            height=geom.height,
        )

        # The first slice keeps its header band (this is where the header is
        # allowed to appear); later slices start below it.
        valid_top = 0 if first else occlusion
        # Content row shown at `valid_top`, then discard whatever the previous
        # slice already covered. This is the overlap crop, and it also soaks up
        # sub-pixel scroll drift.
        top = valid_top + max(0, written - int(round(actual + valid_top)))
        if top >= slice_img.height:
            continue

        piece = slice_img.crop((0, top, slice_img.width, slice_img.height))
        overshoot = written + piece.height - geom.content_height
        if overshoot > 0:
            piece = piece.crop((0, 0, piece.width, piece.height - overshoot))
        if piece.height <= 0:
            continue

        canvas.paste(piece, (0 if full_width else geom.paste_x, written))
        written += piece.height

    return canvas


def capture_page(page: Page, spec: PageSpec, base_url: str) -> Image.Image:
    """Navigate to spec, settle, then scroll-and-stitch the Streamlit main
    scroll container into a single full-length image."""
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)
    url = _build_url(base_url, spec)

    # Suppress transitions even when the caller supplied its own page/context.
    page.emulate_media(reduced_motion="reduce", color_scheme="light")

    try:
        page.goto(url, wait_until="networkidle")
    except PlaywrightTimeoutError:
        # Streamlit's websocket normally does not defeat networkidle, but a
        # slow cold fetch can. A plain load plus the settle delay is enough.
        page.goto(url, wait_until="load")

    time.sleep(spec.settle_seconds)

    # Refuse to stitch an unstyled render. See readiness.py: a deep-linked page
    # can come up without the app's own stylesheet, and the resulting PNG looks
    # plausible enough to be committed as a baseline.
    wait_for_base_style(page, context=f"capture {spec.name}")

    page.add_style_tag(content=CAPTURE_CSS)  # style tags do not survive navigation
    _wait_for_fonts(page)

    geom = _measure(page)
    top_header = _header_rect(page)
    bottom_header = _prerender(page, geom)
    # Lazily-rendered charts can grow the container, so re-measure now that
    # everything has been painted at least once.
    geom = _measure(page)
    occlusion = _occlusion_height(geom, top_header, bottom_header)

    return _stitch(page, geom, occlusion)


def capture_all(
    base_url: str,
    out_dir: Path,
    *,
    pages: list[PageSpec],
    viewports: dict[str, tuple[int, int]],
) -> dict[str, Path]:
    """Capture every (viewport, page) pair. Create out_dir as needed.
    Return {"<viewport>/<page>.png": written_path}."""
    out_dir = Path(out_dir)
    written: dict[str, Path] = {}

    with sync_playwright() as playwright:
        # One browser for the whole matrix; a fresh context per viewport so
        # nothing leaks between sizes (and so session state starts clean).
        browser = playwright.chromium.launch(args=BROWSER_ARGS)
        try:
            for viewport_name, (width, height) in viewports.items():
                target_dir = out_dir / viewport_name
                target_dir.mkdir(parents=True, exist_ok=True)
                context = browser.new_context(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1,  # DPR 1 keeps baselines small and stable
                    reduced_motion="reduce",
                    color_scheme="light",
                    locale="en-US",
                    timezone_id="UTC",
                )
                try:
                    page = context.new_page()
                    # Run the entry script once for this context before touching
                    # any sub-page, so output does not depend on PAGES ordering.
                    establish_session(page, base_url)
                    for spec in pages:
                        image = capture_page(page, spec, base_url)
                        path = target_dir / f"{spec.name}.png"
                        image.save(path, format="PNG", optimize=True)
                        # Keys are display/report identifiers, so they use "/"
                        # on every platform — not os.path.join.
                        written[f"{viewport_name}/{spec.name}.png"] = path
                finally:
                    context.close()
        finally:
            browser.close()

    return written

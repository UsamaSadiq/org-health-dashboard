"""Design tokens and shared visual primitives for the dashboard.

Single source of truth for palette, typography scale, Plotly templating, and
small HTML helpers (grade pills). All UI modules resolve colours through
:func:`palette` rather than hard-coding them.

**Why a palette object rather than module constants.** The dark-mode toggle used
to be decorative. ``apply_base_style()`` emitted
``<script>document.documentElement.setAttribute('data-theme', …)</script>`` via
``st.markdown``, and browsers do not execute scripts inserted as ``innerHTML``,
so the attribute was never set: verified null both before and after toggling.
Every ``[data-theme="dark"]`` rule in this file was therefore dead code, and the
toggle visibly flipped while nothing changed.

The fix cannot be "set the attribute properly", because Plotly figures are not
styled by CSS at all — they bake colours in at construction time. So a theme
switch has to change *values*, not just selectors. Colours that vary by theme
live on :class:`Palette`; :func:`apply_base_style` emits the active palette's
values into ``:root``, and :func:`register_plotly_template` rebuilds the chart
template from the same object. Module-level colour constants were removed on
purpose: imported by value at module load, they could not follow the theme and
would silently render light-theme charts on a dark page.

Semantic and brand hues shift between themes too. The light theme's ``#15803D``
green and ``#0F4C5C`` primary are close to unreadable on a dark surface, so the
dark palette substitutes lighter variants rather than reusing them.
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from dataclasses import dataclass, field

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Session-state key written by the sidebar toggle in dashboard/ui/filters.py.
THEME_STATE_KEY = "theme_dark"


def _rgba(hex_color: str, alpha: float) -> str:
    """CSS rgba() string from a #rrggbb hex and an alpha.

    Chip and dot backgrounds are tints of their own foreground colour, so they
    have to be derived from the active palette rather than written as literals.
    """
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


@dataclass(frozen=True)
class Palette:
    """Every colour that varies between light and dark.

    Fields are plain hex strings so they can be used both in generated CSS and
    in Plotly figure construction, which accepts no CSS variables.
    """

    name: str

    # Brand
    primary: str
    primary_dark: str
    accent: str

    # Semantic
    success: str
    warn: str
    fail: str

    # Surfaces and type
    text: str
    muted: str
    page: str
    surface: str
    surface_alt: str
    border: str

    # Sidebar text sits on the primary gradient in both themes, so it is fixed
    # rather than derived from `text`.
    on_primary: str

    # The sidebar gradient is declared explicitly rather than derived from
    # `primary`: the dark palette's primary is a light teal (readable on a dark
    # page), and reusing it here would turn the sidebar bright.
    sidebar_from: str
    sidebar_to: str

    grade_colors: dict[str, str]
    grade_text_colors: dict[str, str]
    categorical: list[str] = field(default_factory=list)

    @property
    def status_colors(self) -> dict[str, str]:
        """Status keyword to colour, used by tables and badges."""
        return {
            "pass": self.success,
            "fail": self.fail,
            "warn": self.warn,
            "unknown": self.muted,
            # Distinct from "unknown": a metric whose column exists but whose
            # value was absent, so the score fell back to its default.
            "nodata": self.muted,
        }

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


LIGHT = Palette(
    name="light",
    primary="#0F4C5C",
    primary_dark="#0A3642",
    accent="#14B8A6",
    success="#15803D",
    warn="#D97706",
    fail="#B91C1C",
    text="#0F172A",
    muted="#475569",
    page="#F1F5F9",
    surface="#F8FAFC",
    surface_alt="#FFFFFF",
    border="#E2E8F0",
    on_primary="#FFFFFF",
    sidebar_from="#0F4C5C",
    sidebar_to="#0A3642",
    grade_colors={
        "A": "#15803D",
        "B": "#16A34A",
        "C": "#D97706",
        "D": "#EA580C",
        "F": "#B91C1C",
    },
    grade_text_colors={
        "A": "#FFFFFF",
        "B": "#FFFFFF",
        "C": "#111827",
        "D": "#FFFFFF",
        "F": "#FFFFFF",
    },
    categorical=["#0F4C5C", "#14B8A6", "#7C3AED", "#0EA5E9", "#D97706", "#B91C1C", "#475569"],
)

# Dark is not the light palette with an inverted background. The deep teal
# primary and the dark semantic greens/reds fail against a dark surface, so each
# is replaced by a lighter sibling. Grade fills become light pastels, which flips
# their pill text to dark.
DARK = Palette(
    name="dark",
    primary="#2DD4BF",
    primary_dark="#0A3642",
    accent="#2DD4BF",
    success="#4ADE80",
    warn="#FBBF24",
    fail="#F87171",
    text="#F1F5F9",
    muted="#94A3B8",
    page="#0F172A",
    surface="#1E293B",
    surface_alt="#1E293B",
    border="#334155",
    on_primary="#FFFFFF",
    sidebar_from="#0A3642",
    sidebar_to="#071F27",
    grade_colors={
        "A": "#4ADE80",
        "B": "#34D399",
        "C": "#FBBF24",
        "D": "#FB923C",
        "F": "#F87171",
    },
    grade_text_colors={
        # Every dark-theme grade fill is light, so all pill text is dark.
        "A": "#0F172A",
        "B": "#0F172A",
        "C": "#0F172A",
        "D": "#0F172A",
        "F": "#0F172A",
    },
    categorical=["#2DD4BF", "#38BDF8", "#A78BFA", "#4ADE80", "#FBBF24", "#F87171", "#94A3B8"],
)

GRADE_ORDER = ["A", "B", "C", "D", "F"]

PLOTLY_TEMPLATE_NAME = "openedx_health"


def is_dark() -> bool:
    """True when the viewer has switched the dark toggle on.

    Reads session state directly rather than taking a parameter so that any
    module can resolve the active theme without threading it through call
    signatures. Safe outside a Streamlit run (returns False).
    """
    try:
        return bool(st.session_state.get(THEME_STATE_KEY, False))
    except Exception:  # noqa: BLE001 - no script run context (tests, tooling)
        return False


def palette() -> Palette:
    """The active palette. Call this inside functions, never at import time."""
    return DARK if is_dark() else LIGHT


# ---------------------------------------------------------------------------
# Plotly
# ---------------------------------------------------------------------------
def _build_plotly_template(p: Palette) -> go.layout.Template:
    template = go.layout.Template()
    template.layout = go.Layout(
        font={"family": "Inter, system-ui, -apple-system, sans-serif", "color": p.text, "size": 13},
        title={"font": {"size": 16, "color": p.text}},
        colorway=p.categorical,
        paper_bgcolor=p.surface_alt,
        plot_bgcolor=p.page,
        margin={"l": 48, "r": 24, "t": 56, "b": 48},
        bargap=0.3,
        xaxis={
            "showgrid": False,
            "gridcolor": p.border,
            "linecolor": "rgba(0,0,0,0)",
            "zerolinecolor": p.border,
            "title": {"font": {"color": p.muted}},
            "tickfont": {"color": p.muted},
        },
        yaxis={
            "showgrid": True,
            "gridcolor": p.border,
            "linecolor": "rgba(0,0,0,0)",
            "zerolinecolor": p.border,
            "title": {"font": {"color": p.muted}},
            "tickfont": {"color": p.muted},
        },
        legend={"bgcolor": "rgba(0,0,0,0)", "bordercolor": p.border, "borderwidth": 0},
        hoverlabel={"bgcolor": p.surface_alt, "bordercolor": p.border, "font": {"color": p.text}},
    )
    return template


def register_plotly_template(p: Palette | None = None) -> None:
    """Install the chart template for a palette and make it the default.

    Must be re-run whenever the theme changes: Plotly resolves the template at
    figure-construction time, so a stale template produces light-theme charts on
    a dark page. ``apply_base_style()`` calls this on every run.
    """
    active = p or palette()
    pio.templates[PLOTLY_TEMPLATE_NAME] = _build_plotly_template(active)
    pio.templates.default = PLOTLY_TEMPLATE_NAME


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def _base_css(p: Palette) -> str:
    """Render the stylesheet for a palette.

    Everything theme-dependent is emitted as a custom property on ``:root``, so
    the rules below are written once and follow whichever palette was passed.
    This replaces the previous approach of shipping both themes and switching a
    ``data-theme`` attribute, which never worked (see the module docstring).
    """
    shadow = (
        "0 1px 2px rgba(0,0,0,.3), 0 4px 12px rgba(0,0,0,.4)"
        if p.is_dark
        else "0 1px 2px rgba(15,23,42,.04), 0 4px 12px rgba(15,23,42,.06)"
    )
    shadow_hi = (
        "0 2px 4px rgba(0,0,0,.4), 0 10px 24px rgba(0,0,0,.5)"
        if p.is_dark
        else "0 2px 4px rgba(15,23,42,.06), 0 10px 24px rgba(15,23,42,.10)"
    )
    hero_gradient = (
        f"linear-gradient(135deg, {p.surface_alt} 0%, #24344B 100%)"
        if p.is_dark
        else f"linear-gradient(135deg, {p.surface_alt} 0%, #FAFCFE 100%)"
    )

    grade_rules = "\n".join(
        f"  .grade-{letter.lower()} {{ background: {p.grade_colors[letter]}; "
        f"color: {p.grade_text_colors[letter]}; }}"
        for letter in GRADE_ORDER
    )

    return f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --color-primary: {p.primary};
    --color-primary-dark: {p.primary_dark};
    --color-accent: {p.accent};
    --color-pass: {p.success};
    --color-warn: {p.warn};
    --color-fail: {p.fail};
    --color-text: {p.text};
    --color-muted: {p.muted};
    --color-page: {p.page};
    --color-surface: {p.surface};
    --color-surface-alt: {p.surface_alt};
    --color-border: {p.border};
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
    --shadow-card: {shadow};
    --shadow-card-hi: {shadow_hi};
  }}

  /* Scope Inter only to content we own. Never use [class*="st-"] or button
     here — Streamlit's emotion CSS applies Material Symbols Rounded to icon
     spans via st-emotion-cache-* classes; a broad selector overrides that and
     renders icons as raw ligature text (e.g. "arrow_drop_down"). */
  html, body, .stMarkdown, .stText, input, textarea, select,
  [data-testid="stMarkdownContainer"],
  [data-testid="stCaptionContainer"] {{
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  }}

  .stApp {{ background-color: var(--color-page); }}

  /* Streamlit's own header is a sibling of the scroll container with its own
     opaque background, so .stApp does not cover it. Left alone it renders as a
     light strip across the top of a dark page. */
  header[data-testid="stHeader"] {{
    background: var(--color-page) !important;
  }}

  /* Main-area form controls. The sidebar has its own treatment further down
     (it sits on the primary gradient in both themes); these are the widgets on
     the page body, which otherwise keep Streamlit's light chrome. */
  [data-testid="stMain"] input,
  [data-testid="stMain"] textarea,
  [data-testid="stMain"] [data-baseweb="select"] > div {{
    background: var(--color-surface-alt);
    color: var(--color-text);
    border-color: var(--color-border);
  }}
  [data-testid="stMain"] input::placeholder,
  [data-testid="stMain"] textarea::placeholder {{
    color: var(--color-muted);
    opacity: 1;
  }}

  .block-container {{ padding-top: 2rem; }}

  /* Typography rhythm */
  h1 {{ font-weight: 700; letter-spacing: -0.02em; font-size: 1.75rem; color: var(--color-text); }}
  h2 {{ font-weight: 600; letter-spacing: -0.015em; font-size: 1.35rem; color: var(--color-text); }}
  h3 {{ font-weight: 600; letter-spacing: -0.01em; font-size: 1.1rem; color: var(--color-text); }}
  h4, h5, h6 {{ color: var(--color-text); }}
  p, li, .stMarkdown {{ color: var(--color-text); }}

  /* Tabular numerals for numeric UI */
  [data-testid="stMetricValue"],
  [data-testid="stMetricDelta"],
  .stCaption,
  [data-testid="stDataFrame"] td {{
    font-feature-settings: 'tnum' 1, 'cv11' 1;
    font-variant-numeric: tabular-nums;
  }}

  /* st.metric — card surface. Fixed min-height + full-height so tiles in a
     grid stay the same size whether or not they carry a delta/help row. */
  div[data-testid="stMetric"] {{
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    padding: 16px 20px;
    border: 1px solid var(--color-border);
    height: 100%;
    min-height: 116px;
    display: flex;
    flex-direction: column;
    justify-content: center;
  }}
  div[data-testid="stMetricLabel"] {{ color: var(--color-muted); font-weight: 500; }}
  div[data-testid="stMetricValue"] {{ color: var(--color-text); font-weight: 700; }}

  /* Tabs */
  button[role="tab"][aria-selected="true"] {{
    color: var(--color-accent) !important;
    font-weight: 600;
    border-bottom: 2px solid var(--color-accent) !important;
  }}

  /* DataFrame */
  div[data-testid="stDataFrame"] {{
    border-radius: var(--radius-md);
    overflow: hidden;
    box-shadow: var(--shadow-card);
    border: 1px solid var(--color-border);
  }}

  /* Sidebar identity */
  section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {p.sidebar_from} 0%, {p.sidebar_to} 100%);
  }}
  /* Text color for sidebar content — scoped to text-bearing elements so we
     don't recolor backgrounds, dots, or icons inside nav items/chips. */
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3,
  section[data-testid="stSidebar"] h4,
  section[data-testid="stSidebar"] h5,
  section[data-testid="stSidebar"] h6,
  section[data-testid="stSidebar"] p,
  section[data-testid="stSidebar"] a,
  section[data-testid="stSidebar"] li,
  section[data-testid="stSidebar"] .stMarkdown {{
    color: {p.on_primary};
  }}
  /* Only colour non-nav spans (e.g. freshness chip text); leave nav link
     spans alone so Material icon glyphs don't bleed over the label. */
  section[data-testid="stSidebar"] span:not([data-testid="stSidebarNavLink"] span):not([data-testid="stSidebarNavLinkContainer"] span) {{
    color: {p.on_primary};
  }}

  /* ── Sidebar navigation links ─────────────────────────────────────────── */
  /* Ensure nav section headers (category labels) are clearly readable */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] p,
  section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] span {{
    color: rgba(255,255,255,0.55) !important;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }}
  /* Nav link buttons: flex row, icon + label side-by-side, no overflow */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"],
  section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {{
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 10px !important;
    padding: 8px 12px !important;
    border-radius: 8px !important;
    color: rgba(255,255,255,0.85) !important;
    text-decoration: none !important;
    overflow: hidden !important;
    white-space: nowrap !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
    background: rgba(255,255,255,0.10) !important;
    color: #FFFFFF !important;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-selected="true"],
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"].active {{
    background: rgba(255,255,255,0.15) !important;
    color: #FFFFFF !important;
  }}
  /* Icon span — fixed width, centred, no text overflow */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span:first-child {{
    flex-shrink: 0;
    width: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}
  /* Label span — takes remaining space, clips cleanly */
  section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span:last-child {{
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: inherit;
  }}
  section[data-testid="stSidebar"] .stCaption,
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
    color: rgba(255,255,255,0.85) !important;
  }}
  /* Sidebar layout rhythm */
  section[data-testid="stSidebar"] .block-container,
  section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    padding-top: 1.25rem;
    padding-left: 1.1rem;
    padding-right: 1.1rem;
  }}
  /* Force breathing room between every direct child block in the sidebar */
  section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{
    margin-bottom: 14px;
  }}
  /* Identity block: wordmark + freshness chip stacked, divider underneath */
  .sidebar-identity {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
  }}
  .sidebar-wordmark {{
    font-weight: 700;
    font-size: 1.1rem;
    line-height: 1.2;
    color: #FFFFFF;
    letter-spacing: -0.01em;
  }}
  .sidebar-section {{
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(255,255,255,0.6);
    margin-top: 6px;
    margin-bottom: 4px;
  }}
  section[data-testid="stSidebar"] hr {{
    border-color: rgba(255,255,255,0.15);
    margin: 20px 0;
  }}
  section[data-testid="stSidebar"] input,
  section[data-testid="stSidebar"] select,
  section[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background: rgba(255,255,255,0.10) !important;
    color: #FFFFFF !important;
    border-color: rgba(255,255,255,0.20) !important;
  }}
  /* Cards */
  .card {{
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    padding: var(--space-6);
    margin-bottom: var(--space-6);
    border: 1px solid var(--color-border);
  }}
  .card-hero {{
    background: {hero_gradient};
    box-shadow: var(--shadow-card-hi);
  }}
  .card-empty {{
    text-align: center;
    padding: 48px 24px;
  }}
  .card-empty .empty-icon {{
    font-size: 48px;
    color: var(--color-muted);
    margin-bottom: 12px;
  }}
  .card-empty h3 {{ margin: 0 0 8px 0; }}
  .card-empty p {{ color: var(--color-muted); margin: 0; }}

  /* Containers (used as cards) */
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-card);
    background: var(--color-surface-alt);
  }}

  .small-muted {{ color: var(--color-muted); font-size: 0.9rem; }}

  .grade-pill {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 28px;
    height: 24px;
    padding: 0 var(--space-2);
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.85rem;
    line-height: 1;
  }}
{grade_rules}

  .status-chip {{
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px var(--space-2);
    border-radius: var(--radius-sm);
    font-size: 0.8rem;
    font-weight: 500;
    border: 1px solid var(--color-border);
  }}
  .status-pass {{ background: {_rgba(p.success, 0.12)}; color: {p.success}; border-color: {_rgba(p.success, 0.3)}; }}
  .status-fail {{ background: {_rgba(p.fail, 0.12)}; color: {p.fail}; border-color: {_rgba(p.fail, 0.3)}; }}
  .status-warn {{ background: {_rgba(p.warn, 0.12)}; color: {p.warn}; border-color: {_rgba(p.warn, 0.3)}; }}
  .status-unknown {{ background: {_rgba(p.muted, 0.08)}; color: var(--color-muted); }}
  /* "No data" is deliberately distinguishable from "unknown" by shape as well
     as colour, so it does not read as a muted pass. */
  .status-nodata {{
    background: transparent;
    color: var(--color-muted);
    border-style: dashed;
    border-color: var(--color-muted);
  }}

  /* Freshness chip (sidebar) */
  .freshness-chip {{
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.18);
    color: #FFFFFF;
    margin: 0;
    width: fit-content;
  }}
  .freshness-dot {{
    width: 8px; height: 8px; border-radius: 999px;
    box-shadow: 0 0 0 3px rgba(255,255,255,0.12);
  }}
  .freshness-fresh .freshness-dot {{ background: #4ADE80; }}
  .freshness-stale .freshness-dot {{ background: #FBBF24; }}
  .freshness-critical .freshness-dot {{ background: #F87171; }}

  /* Focus visibility — WCAG 2.2 SC 2.4.11 / 2.4.7 */
  :focus-visible {{
    outline: 2px solid var(--color-accent) !important;
    outline-offset: 2px !important;
  }}

  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
      animation-duration: 0.001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important;
      scroll-behavior: auto !important;
    }}
  }}
</style>
"""


def apply_base_style() -> None:
    """Inject the active palette's CSS and register the matching chart template.

    Called from every page via ``dashboard.ui.page.page_init``. Resolves the
    theme from session state on each run, so toggling dark mode triggers a rerun
    that re-emits both the stylesheet and the Plotly template.
    """
    active = palette()
    register_plotly_template(active)
    st.markdown(_base_css(active), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def grade_pill(grade: str) -> str:
    """Return an inline grade pill HTML snippet. Always paired with the letter text."""
    grade = (grade or "").strip().upper()
    cls = f"grade-{grade.lower()}" if grade in GRADE_ORDER else ""
    label = grade or "—"
    return f'<span class="grade-pill {cls}" aria-label="Grade {label}">{label}</span>'


def render_repo_pill_list(rows: list[tuple[str, float, str]], *, link_fn=None) -> None:
    """Render a small ranked repo list with grade pills inline.

    `rows` is an iterable of (repo_name, score, grade_letter). If `link_fn` is
    provided, repo names are wrapped in markdown links to `link_fn(repo)`.
    """
    if not rows:
        st.caption("No repositories.")
        return
    lines = []
    for repo, score, grade in rows:
        repo_text = html.escape(str(repo))
        # This list is emitted as raw HTML, so use an <a> tag — markdown link
        # syntax ("[name](url)") is not parsed inside unsafe_allow_html blocks
        # and would render as literal text.
        if link_fn:
            href = html.escape(str(link_fn(repo)), quote=True)
            label = (
                f'<a href="{href}" target="_self" '
                f'style="color:var(--color-accent);text-decoration:none;font-weight:600;">'
                f'{repo_text}</a>'
            )
        else:
            label = repo_text
        score_text = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
        # A long repo name still collides with its own grade pill here (backlog
        # A11). A first attempt at min-width:0 + ellipsis on the name cell pushed
        # the pill and score off-screen entirely at 390px, which is worse than
        # the collision, so the fix is deferred to WP-8 where it can be checked
        # against the mobile baseline.
        lines.append(
            f'<li style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:6px 0;border-bottom:1px solid var(--color-border);">'
            f'<span>{label}</span>'
            f'<span>{grade_pill(grade)} <span class="small-muted">{score_text}</span></span>'
            f'</li>'
        )
    st.markdown(
        f'<ul style="list-style:none;padding-left:0;margin:0;">{"".join(lines)}</ul>',
        unsafe_allow_html=True,
    )


def share_link_block(url: str, *, label: str = "Share link") -> None:
    """Render a share URL as a copyable code block instead of an editable input."""
    st.markdown(f"**{label}**")
    st.code(url, language="text")


def status_chip(status: str, label: str | None = None) -> str:
    """Render a pill with color + text. Color is never the only signal."""
    key = (status or "").strip().lower()
    if key not in {"pass", "fail", "warn", "unknown", "nodata"}:
        key = "unknown"
    text = label or key.upper()
    return f'<span class="status-chip status-{key}">{text}</span>'


@contextmanager
def card(*, hero: bool = False):
    """Context manager that wraps a block in a styled card surface."""
    cls = "card card-hero" if hero else "card"
    st.markdown(f'<div class="{cls}">', unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown('</div>', unsafe_allow_html=True)

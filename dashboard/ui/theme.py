"""Design tokens and shared visual primitives for the dashboard.

Single source of truth for palette, typography scale, Plotly templating, and
small HTML helpers (grade pills). All UI modules import from here rather than
hard-coding colors.
"""
from __future__ import annotations

from contextlib import contextmanager

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Palette (Modernized Open edX, WCAG AA against Surface)
# ---------------------------------------------------------------------------
PRIMARY = "#0F4C5C"
PRIMARY_DARK = "#0A3642"  # ~10% darker for sidebar gradient
ACCENT = "#14B8A6"
PASS = "#15803D"
WARN = "#D97706"
FAIL = "#B91C1C"
TEXT = "#0F172A"
MUTED = "#475569"
PAGE = "#F1F5F9"
SURFACE = "#F8FAFC"
SURFACE_ALT = "#FFFFFF"
BORDER = "#E2E8F0"

GRADE_COLORS = {
    "A": PASS,
    "B": "#16A34A",
    "C": WARN,
    "D": "#EA580C",
    "F": FAIL,
}

GRADE_TEXT_COLORS = {
    "A": "#FFFFFF",
    "B": "#FFFFFF",
    "C": "#111827",
    "D": "#FFFFFF",
    "F": "#FFFFFF",
}

# Sequential/categorical palette for charts that need more than status colors.
CATEGORICAL = [PRIMARY, ACCENT, "#7C3AED", "#0EA5E9", WARN, FAIL, MUTED]

# Status keyword → color, used by tables and badges.
STATUS_COLORS = {
    "pass": PASS,
    "fail": FAIL,
    "warn": WARN,
    "unknown": MUTED,
}

PLOTLY_TEMPLATE_NAME = "openedx_health"


def _build_plotly_template() -> go.layout.Template:
    template = go.layout.Template()
    template.layout = go.Layout(
        font={"family": "Inter, system-ui, -apple-system, sans-serif", "color": TEXT, "size": 13},
        title={"font": {"size": 16, "color": TEXT}},
        colorway=CATEGORICAL,
        paper_bgcolor=SURFACE_ALT,
        plot_bgcolor=PAGE,
        margin={"l": 48, "r": 24, "t": 56, "b": 48},
        bargap=0.3,
        xaxis={
            "showgrid": False,
            "gridcolor": BORDER,
            "linecolor": "rgba(0,0,0,0)",
            "zerolinecolor": BORDER,
            "title": {"font": {"color": MUTED}},
            "tickfont": {"color": MUTED},
        },
        yaxis={
            "showgrid": True,
            "gridcolor": BORDER,
            "linecolor": "rgba(0,0,0,0)",
            "zerolinecolor": BORDER,
            "title": {"font": {"color": MUTED}},
            "tickfont": {"color": MUTED},
        },
        legend={"bgcolor": "rgba(0,0,0,0)", "bordercolor": BORDER, "borderwidth": 0},
        hoverlabel={"bgcolor": SURFACE_ALT, "bordercolor": BORDER, "font": {"color": TEXT}},
    )
    return template


def register_plotly_template() -> None:
    pio.templates[PLOTLY_TEMPLATE_NAME] = _build_plotly_template()
    pio.templates.default = PLOTLY_TEMPLATE_NAME


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
_BASE_CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  :root {{
    --color-primary: {PRIMARY};
    --color-primary-dark: {PRIMARY_DARK};
    --color-accent: {ACCENT};
    --color-pass: {PASS};
    --color-warn: {WARN};
    --color-fail: {FAIL};
    --color-text: {TEXT};
    --color-muted: {MUTED};
    --color-page: {PAGE};
    --color-surface: {SURFACE};
    --color-surface-alt: {SURFACE_ALT};
    --color-border: {BORDER};
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
    --shadow-card: 0 1px 2px rgba(15,23,42,.04), 0 4px 12px rgba(15,23,42,.06);
    --shadow-card-hi: 0 2px 4px rgba(15,23,42,.06), 0 10px 24px rgba(15,23,42,.10);
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

  .block-container {{ padding-top: 2rem; }}

  /* Typography rhythm */
  h1 {{ font-weight: 700; letter-spacing: -0.02em; font-size: 1.75rem; color: var(--color-text); }}
  h2 {{ font-weight: 600; letter-spacing: -0.015em; font-size: 1.35rem; color: var(--color-text); }}
  h3 {{ font-weight: 600; letter-spacing: -0.01em; font-size: 1.1rem; color: var(--color-text); }}

  /* Tabular numerals for numeric UI */
  [data-testid="stMetricValue"],
  [data-testid="stMetricDelta"],
  .stCaption,
  [data-testid="stDataFrame"] td {{
    font-feature-settings: 'tnum' 1, 'cv11' 1;
    font-variant-numeric: tabular-nums;
  }}

  /* st.metric — card surface */
  div[data-testid="stMetric"] {{
    background: var(--color-surface-alt);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    padding: 16px 20px;
    border: 1px solid var(--color-border);
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
    background: linear-gradient(180deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
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
    color: #FFFFFF;
  }}
  /* Only colour non-nav spans (e.g. freshness chip text); leave nav link
     spans alone so Material icon glyphs don't bleed over the label. */
  section[data-testid="stSidebar"] span:not([data-testid="stSidebarNavLink"] span):not([data-testid="stSidebarNavLinkContainer"] span) {{
    color: #FFFFFF;
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
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3 {{
    color: #FFFFFF;
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
    background: linear-gradient(135deg, var(--color-surface-alt) 0%, #FAFCFE 100%);
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
  .grade-a {{ background: {GRADE_COLORS['A']}; color: {GRADE_TEXT_COLORS['A']}; }}
  .grade-b {{ background: {GRADE_COLORS['B']}; color: {GRADE_TEXT_COLORS['B']}; }}
  .grade-c {{ background: {GRADE_COLORS['C']}; color: {GRADE_TEXT_COLORS['C']}; }}
  .grade-d {{ background: {GRADE_COLORS['D']}; color: {GRADE_TEXT_COLORS['D']}; }}
  .grade-f {{ background: {GRADE_COLORS['F']}; color: {GRADE_TEXT_COLORS['F']}; }}

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
  .status-pass {{ background: rgba(21, 128, 61, 0.12); color: var(--color-pass); border-color: rgba(21, 128, 61, 0.3); }}
  .status-fail {{ background: rgba(185, 28, 28, 0.12); color: var(--color-fail); border-color: rgba(185, 28, 28, 0.3); }}
  .status-warn {{ background: rgba(217, 119, 6, 0.12); color: var(--color-warn); border-color: rgba(217, 119, 6, 0.3); }}
  .status-unknown {{ background: rgba(71, 85, 105, 0.08); color: var(--color-muted); }}

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

  /* Dark mode overrides */
  [data-theme="dark"] {{
    --color-page: #0F172A;
    --color-surface: #1E293B;
    --color-surface-alt: #1E293B;
    --color-text: #F1F5F9;
    --color-muted: #94A3B8;
    --color-border: #334155;
    --shadow-card: 0 1px 2px rgba(0,0,0,.3), 0 4px 12px rgba(0,0,0,.4);
    --shadow-card-hi: 0 2px 4px rgba(0,0,0,.4), 0 10px 24px rgba(0,0,0,.5);
  }}
  [data-theme="dark"] .stApp {{ background-color: #0F172A; }}
  [data-theme="dark"] h1,
  [data-theme="dark"] h2,
  [data-theme="dark"] h3,
  [data-theme="dark"] p,
  [data-theme="dark"] .stMarkdown {{ color: #F1F5F9; }}
  [data-theme="dark"] div[data-testid="stMetric"],
  [data-theme="dark"] .card {{
    background: #1E293B;
    border-color: #334155;
  }}
  [data-theme="dark"] div[data-testid="stMetricLabel"] {{ color: #94A3B8; }}
  [data-theme="dark"] div[data-testid="stMetricValue"] {{ color: #F1F5F9; }}
</style>
"""


_DARK_TOGGLE_JS = """
<script>
(function() {
  const params = new URLSearchParams(window.location.search);
  const theme = params.get('__theme_dark') === '1' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  document.body && document.body.setAttribute('data-theme', theme);
})();
</script>
"""


def apply_base_style() -> None:
    """Inject base CSS and register the Plotly template. Idempotent."""
    register_plotly_template()
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    dark = bool(st.session_state.get("theme_dark", False))
    attr = "dark" if dark else "light"
    st.markdown(
        f"<script>document.documentElement.setAttribute('data-theme','{attr}');"
        f"document.body && document.body.setAttribute('data-theme','{attr}');</script>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
def grade_pill(grade: str) -> str:
    """Return an inline grade pill HTML snippet. Always paired with the letter text."""
    grade = (grade or "").strip().upper()
    cls = f"grade-{grade.lower()}" if grade in GRADE_COLORS else ""
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
        label = f"[{repo}]({link_fn(repo)})" if link_fn else repo
        score_text = f"{score:.1f}" if isinstance(score, (int, float)) else str(score)
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
    if key not in {"pass", "fail", "warn", "unknown"}:
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

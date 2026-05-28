"""Design tokens and shared visual primitives for the dashboard.

Single source of truth for palette, typography scale, Plotly templating, and
small HTML helpers (grade pills). All UI modules import from here rather than
hard-coding colors.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---------------------------------------------------------------------------
# Palette (Modernized Open edX, WCAG AA against Surface)
# ---------------------------------------------------------------------------
PRIMARY = "#0F4C5C"
ACCENT = "#14B8A6"
PASS = "#15803D"
WARN = "#D97706"
FAIL = "#B91C1C"
TEXT = "#0F172A"
MUTED = "#475569"
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
        plot_bgcolor=SURFACE_ALT,
        margin={"l": 48, "r": 24, "t": 48, "b": 48},
        xaxis={"gridcolor": BORDER, "linecolor": BORDER, "zerolinecolor": BORDER, "title": {"font": {"color": MUTED}}},
        yaxis={"gridcolor": BORDER, "linecolor": BORDER, "zerolinecolor": BORDER, "title": {"font": {"color": MUTED}}},
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
  :root {{
    --color-primary: {PRIMARY};
    --color-accent: {ACCENT};
    --color-pass: {PASS};
    --color-warn: {WARN};
    --color-fail: {FAIL};
    --color-text: {TEXT};
    --color-muted: {MUTED};
    --color-surface: {SURFACE};
    --color-surface-alt: {SURFACE_ALT};
    --color-border: {BORDER};
    --radius-sm: 6px;
    --radius-md: 10px;
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-6: 24px;
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
    """Inject base CSS and register the Plotly template. Idempotent."""
    register_plotly_template()
    st.markdown(_BASE_CSS, unsafe_allow_html=True)


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

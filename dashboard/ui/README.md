# `dashboard/ui` — UI primitives

This package owns the dashboard's visual layer. Anything color, layout,
or interaction-pattern-related lives here so individual pages stay
focused on data assembly.

## Tokens

All design tokens live in `theme.py` as module-level constants. Pages
**must not** hardcode colors, spacing, or font choices — import the
token instead.

| Token            | Purpose                                  |
|------------------|------------------------------------------|
| `PRIMARY`        | Brand teal, used in axes/headings        |
| `ACCENT`         | Interactive accents, focus outlines      |
| `PASS` / `WARN` / `FAIL` | Status colors (always paired with a text label) |
| `TEXT` / `MUTED` | Foreground text + secondary captions     |
| `SURFACE` / `SURFACE_ALT` | Background fills                 |
| `BORDER`         | Card / divider strokes                   |
| `GRADE_COLORS`   | Per-letter (A–F) palette for pills/bars  |
| `CATEGORICAL`    | Chart series palette (7 hues)            |

Palette: WCAG AA against `SURFACE`; pass/fail also pass deuteranopia
and protanopia simulation when paired with status text.

## Components

| Symbol                       | What it does |
|------------------------------|--------------|
| `apply_base_style()`         | Inject the base stylesheet + register the Plotly template. Call once from `streamlit_app.py`. |
| `grade_pill(letter)`         | Inline HTML pill for an A–F grade. |
| `status_chip(status, label)` | Pass/Fail/Warn/Unknown chip (color + text). |
| `share_link_block(url)`      | Render a share URL as a copyable `st.code` block. |
| `render_repo_pill_list(rows)`| Vertical ranked list of `(repo, score, grade)` with inline pills. |
| `render_kpi_strip(df, baseline=...)` | Four-tile KPI strip; renders deltas when `baseline` is supplied. |
| `render_freshness_banner(...)` | Snapshot-age banner (info/warning/error). |
| `render_sidebar_filters()`   | Cross-page search/archived/tier filters (persisted via `st.session_state`). |
| `charts.grade_histogram`, `category_pass_rate_bar`, `top_failing_bar`, `sparkline` | Themed Plotly figure factories. |

## State

| Session key       | Purpose                                 |
|-------------------|-----------------------------------------|
| `filter_search`   | Sidebar search box                      |
| `filter_archived` | Include-archived checkbox               |
| `filter_tier`     | Tier selector (`all` \| `critical` \| `important` \| `standard`) |

`hydrate_from_query_params()` (called once from `streamlit_app.py`) seeds
these from URL params on first render so deep links survive.

## Conventions

- **Color is never the only signal.** Every status color is paired with
  a label (`status_chip`) or letter (`grade_pill`).
- **Charts use the shared Plotly template** (`PLOTLY_TEMPLATE_NAME`),
  registered as the Plotly default by `apply_base_style()`. Don't set
  `template=` on individual figures.
- **HTML rendering** uses `unsafe_allow_html=True` only inside this
  package. Page-level code must not interpolate user data into HTML
  strings.
- **Focus + reduced-motion** are baked into `_BASE_CSS`. Don't add
  page-level CSS overrides.

## Deployment-aware URLs

`dashboard.lib.share.base_url()` reads `DASHBOARD_BASE_URL` from the
environment, falling back to the Streamlit Community Cloud URL.
`share_link(params)` is the only correct way to build a share URL —
never concatenate `share.streamlit.io` literals.

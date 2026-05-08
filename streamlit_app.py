import streamlit as st
import pandas as pd
import requests
from io import StringIO

CSV_URL = "https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv"

CHECK_GROUPS = {
    "File Existence": [
        "exists.README",
        "exists.Makefile",
        "exists.openedx.yaml",
        "exists.CHANGELOG.rst",
        "exists.commitlint.yml",
        "exists.dependabot.yml",
        "exists.requirements",
        "exists.setup.py",
        "exists.setup.cfg",
        "exists.tox.ini",
        "exists.pylintrc",
        "exists..editorconfig",
        "exists..gitignore",
        "exists..coveragerc",
        "exists..pii_annotations.yml",
    ],
    "CI / Tooling": [
        "dependabot.exists",
        "dependabot.has_ecosystem.pip",
        "dependabot.has_ecosystem.github-actions",
        "dependabot.has_ecosystem.npm",
        "github_actions",
        "renovate.configured",
        "makefile.upgrade",
        "makefile.quality",
        "makefile.quality-python",
        "makefile.test",
        "makefile.test-python",
        "makefile.pip-installed",
        "pinned_python_dependencies",
    ],
    "Docs": [
        "readthedocs_config.exists",
        "docs.build_badge",
    ],
    "README Quality": [
        "readme.getting-help",
        "readme.security",
    ],
}

REPO_COL = "repo_name"

OVERVIEW_COLS = [
    "repo_name",
    "github.description",
    "github.last_push",
    "github.pulls_count",
    "github.fork_count",
    "github.is_archived",
    "github.license",
    "exists.README",
    "exists.openedx.yaml",
    "exists.commitlint.yml",
    "exists.dependabot.yml",
    "dependabot.exists",
    "github_actions",
    "renovate.configured",
    "readthedocs_config.exists",
    "pinned_python_dependencies",
]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Open edX Repo Health",
    page_icon="🏥",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Brand colours: dark teal #00262B, teal #00B2A9, red #E22D2D ── */

/* Branded header card */
.hero {
    background: linear-gradient(135deg, #00262B 0%, #005F59 60%, #00B2A9 100%);
    padding: 1.75rem 2rem 1.5rem;
    border-radius: 0.75rem;
    margin-bottom: 1.75rem;
    color: white;
}
.hero h1 {
    color: white !important;
    font-size: 1.9rem;
    font-weight: 700;
    margin: 0 0 0.35rem;
    letter-spacing: -0.01em;
}
.hero p {
    color: rgba(255,255,255,0.72);
    margin: 0;
    font-size: 0.84rem;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.75rem;
    color: white;
    margin-top: 0.6rem;
}

/* KPI metric cards */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.6rem;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
[data-testid="stMetricLabel"] > div {
    font-size: 0.75rem !important;
    color: #64748b !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] > div {
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: #00262B !important;
}
[data-testid="stMetricDelta"] > div {
    font-size: 0.78rem !important;
}

/* Section divider label */
.section-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #94a3b8;
    margin: 1.25rem 0 0.5rem;
}

/* Tab bar */
[data-testid="stTabs"] button[data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.9rem;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #00B2A9 !important;
    border-bottom: 3px solid #00B2A9 !important;
}

/* Expander chrome */
[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #00262B;
}

/* Status pill helper classes (used via st.markdown) */
.pill-pass {
    display:inline-block;
    background:#dcfce7; color:#166534;
    border-radius:20px; padding:1px 10px;
    font-size:0.78rem; font-weight:600;
}
.pill-fail {
    display:inline-block;
    background:#fee2e2; color:#991b1b;
    border-radius:20px; padding:1px 10px;
    font-size:0.78rem; font-weight:600;
}
.pill-na {
    display:inline-block;
    background:#f1f5f9; color:#64748b;
    border-radius:20px; padding:1px 10px;
    font-size:0.78rem;
}

/* Reduce top padding Streamlit adds */
.block-container { padding-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    r = requests.get(CSV_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    for col in df.columns:
        if df[col].dtype == object:
            try:
                lowered = df[col].dropna().str.lower()
                if set(lowered.unique()).issubset({"true", "false", ""}):
                    df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
            except AttributeError:
                pass
    return df


def bool_to_emoji(val) -> str:
    if val is True:
        return "✅"
    if val is False:
        return "❌"
    return "—"


df = load_data()
timestamp = df["TIMESTAMP"].iloc[0] if "TIMESTAMP" in df.columns else "unknown"
active_df = df[df["github.is_archived"] != True] if "github.is_archived" in df.columns else df
archived_count = len(df) - len(active_df)

# ── Branded header ────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <h1>🏥 Open edX Repository Health Dashboard</h1>
  <p>Tracking repository hygiene across the Open edX ecosystem</p>
  <span class="hero-badge">📅 Data as of {timestamp}</span>
  <span class="hero-badge" style="margin-left:6px;">⏱ Dashboard refreshes every 5 min</span>
</div>
""", unsafe_allow_html=True)

# ── KPI cards ─────────────────────────────────────────────────────────────────
def pct_passing(col: str, base: pd.DataFrame = active_df) -> str:
    if col not in base.columns:
        return "N/A"
    passing = int((base[col] == True).sum())
    total = len(base)
    return f"{round(passing / total * 100)}%" if total else "N/A"

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Repos", len(df))
k2.metric("Active Repos", len(active_df), delta=f"-{archived_count} archived", delta_color="off")
k3.metric("Has openedx.yaml", pct_passing("exists.openedx.yaml"))
k4.metric("GitHub Actions", pct_passing("github_actions"))
k5.metric("Dependabot Active", pct_passing("dependabot.exists"))

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋  All Repos", "🔍  Repo Detail", "🚨  Failing Checks"])

# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab1:
    col_search, col_arch = st.columns([3, 1])
    with col_search:
        search = st.text_input("Filter by repo name", placeholder="e.g. edx-platform")
    with col_arch:
        hide_archived = st.checkbox("Hide archived repos", value=True)

    filtered = df.copy()
    if hide_archived and "github.is_archived" in filtered.columns:
        filtered = filtered[filtered["github.is_archived"] != True]
    if search:
        filtered = filtered[filtered[REPO_COL].str.contains(search, case=False, na=False)]

    display_cols = [c for c in OVERVIEW_COLS if c in filtered.columns]
    display_df = filtered[display_cols].copy()

    # Convert boolean columns to ✅/❌ for colour-coded display
    bool_cols = [c for c in display_cols if display_df[c].dtype == bool or
                 display_df[c].dropna().isin([True, False]).all()]
    for col in bool_cols:
        display_df[col] = display_df[col].apply(bool_to_emoji)

    st.dataframe(display_df, width="stretch", hide_index=True)
    st.caption(f"{len(filtered)} of {len(df)} repositories shown")

# ── Tab 2: Repo Detail ────────────────────────────────────────────────────────
with tab2:
    selected = st.selectbox("Select a repository", sorted(df[REPO_COL].dropna().unique()))
    row = df[df[REPO_COL] == selected].iloc[0]

    sections = {
        "GitHub Metadata": [c for c in df.columns if c.startswith("github.")],
        "File Existence Checks": [c for c in df.columns if c.startswith("exists.")],
        "CI & Tooling": ["github_actions", "renovate.configured", "pinned_python_dependencies"],
        "Dependabot": [c for c in df.columns if c.startswith("dependabot.")],
        "Makefile Targets": [c for c in df.columns if c.startswith("makefile.")],
        "Docs & ReadTheDocs": [c for c in df.columns if c.startswith("docs.") or c.startswith("readthedocs_config.")],
        "README Quality": [c for c in df.columns if c.startswith("readme.")],
        "Dependencies": [c for c in df.columns if c.startswith("dependencies.") or c.startswith("django_packages.")],
        "Travis / tox": [c for c in df.columns if c.startswith("travis") or c.startswith("tox")],
    }

    for section_name, cols in sections.items():
        existing = [c for c in cols if c in df.columns]
        if not existing:
            continue
        expanded = section_name in ("GitHub Metadata", "File Existence Checks", "CI & Tooling")
        with st.expander(section_name, expanded=expanded):
            rows = []
            for c in existing:
                val = row[c]
                if val is True:
                    display = "✅  Pass"
                    status = "pass"
                elif val is False:
                    display = "❌  Fail"
                    status = "fail"
                else:
                    display = f"—  {val}" if pd.notna(val) else "—  N/A"
                    status = "na"
                rows.append({"Check": c, "Status": display, "_status": status})

            section_df = pd.DataFrame(rows)[["Check", "Status"]]
            st.dataframe(section_df, width="stretch", hide_index=True)

# ── Tab 3: Failing Checks ─────────────────────────────────────────────────────
with tab3:
    st.caption("Active (non-archived) repos only. False = check failing.")

    total_active = len(active_df)
    all_rows = []
    for group, cols in CHECK_GROUPS.items():
        for col in cols:
            if col not in active_df.columns:
                continue
            series = active_df[col]
            failing = int((series == False).sum())
            passing = int((series == True).sum())
            unknown = total_active - failing - passing
            pct = round(failing / total_active * 100, 1) if total_active else 0
            # Health indicator
            if pct == 0:
                indicator = "🟢"
            elif pct <= 25:
                indicator = "🟡"
            elif pct <= 60:
                indicator = "🟠"
            else:
                indicator = "🔴"
            all_rows.append({
                "": indicator,
                "Category": group,
                "Check": col,
                "Failing": failing,
                "Passing": passing,
                "Unknown / N/A": unknown,
                "% Failing": pct,
            })

    if all_rows:
        fail_df = pd.DataFrame(all_rows).sort_values("Failing", ascending=False)

        f1, f2 = st.columns([2, 1])
        with f1:
            categories = ["All"] + sorted(fail_df["Category"].unique().tolist())
            cat_filter = st.selectbox("Filter by category", categories)
        with f2:
            only_failing = st.checkbox("Show only checks with failures", value=False)

        if cat_filter != "All":
            fail_df = fail_df[fail_df["Category"] == cat_filter]
        if only_failing:
            fail_df = fail_df[fail_df["Failing"] > 0]

        st.dataframe(fail_df, width="stretch", hide_index=True)

        # Summary KPIs for this tab
        m1, m2, m3 = st.columns(3)
        m1.metric("Active repos analysed", total_active)
        m2.metric("Checks tracked", len(all_rows))
        m3.metric("Checks with 0 failures", int((fail_df["Failing"] == 0).sum()))
    else:
        st.info("No check columns found.")

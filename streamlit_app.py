import streamlit as st
import pandas as pd
import requests
from io import StringIO

CSV_URL = "https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv"

# Columns that are meaningful health checks (boolean pass/fail)
# Grouped by category for the Failing Checks tab
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

# Summary columns shown in the overview table (non-list, non-noisy)
OVERVIEW_COLS = [
    "repo_name",
    "org_name",
    "github.description",
    "github.last_push",
    "github.pulls_count",
    "github.fork_count",
    "github.is_archived",
    "github.is_private",
    "github.default_branch",
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
    "TIMESTAMP",
]


st.set_page_config(page_title="Open edX Repo Health", layout="wide")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    r = requests.get(CSV_URL, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    # Normalise True/False strings that pandas may read as objects
    for col in df.columns:
        if df[col].dtype == object:
            try:
                lowered = df[col].dropna().str.lower()
                if set(lowered.unique()).issubset({"true", "false", ""}):
                    df[col] = df[col].map({"True": True, "False": False, True: True, False: False})
            except AttributeError:
                # Column contains non-string objects (e.g. actual booleans) — skip
                pass
    return df


df = load_data()

st.title("Open edX Repository Health Dashboard")
st.caption(f"Source: openedx/wg-maintenance · Data refreshed: {df['TIMESTAMP'].iloc[0] if 'TIMESTAMP' in df.columns else 'unknown'} · Dashboard cache: 5 min")

tab1, tab2, tab3 = st.tabs(["All Repos", "Repo Detail", "Failing Checks"])

# ── Tab 1: Overview ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Repository Overview")

    col_search, col_archived = st.columns([3, 1])
    with col_search:
        search = st.text_input("Filter by repo name", placeholder="e.g. edx-platform")
    with col_archived:
        hide_archived = st.checkbox("Hide archived repos", value=True)

    filtered = df.copy()
    if hide_archived and "github.is_archived" in filtered.columns:
        filtered = filtered[filtered["github.is_archived"] != True]
    if search:
        filtered = filtered[filtered[REPO_COL].str.contains(search, case=False, na=False)]

    # Show only the curated overview columns that actually exist in the CSV
    display_cols = [c for c in OVERVIEW_COLS if c in filtered.columns]
    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)
    st.caption(f"{len(filtered)} repositories shown")

# ── Tab 2: Repo Detail ───────────────────────────────────────────────────────
with tab2:
    st.subheader("Repository Detail")

    selected = st.selectbox("Select a repository", sorted(df[REPO_COL].dropna().unique()))
    row = df[df[REPO_COL] == selected].iloc[0]

    # Split into sections
    sections = {
        "GitHub Metadata": [c for c in df.columns if c.startswith("github.")],
        "File Existence Checks": [c for c in df.columns if c.startswith("exists.")],
        "Dependabot": [c for c in df.columns if c.startswith("dependabot.")],
        "Makefile Targets": [c for c in df.columns if c.startswith("makefile.")],
        "Dependencies": [c for c in df.columns if c.startswith("dependencies.") or c.startswith("django_packages.")],
        "Docs & ReadTheDocs": [c for c in df.columns if c.startswith("docs.") or c.startswith("readthedocs_config.")],
        "README Quality": [c for c in df.columns if c.startswith("readme.")],
        "CI": ["github_actions", "renovate.configured", "pinned_python_dependencies"],
        "Travis / tox": [c for c in df.columns if c.startswith("travis") or c.startswith("tox")],
    }

    for section_name, cols in sections.items():
        existing_cols = [c for c in cols if c in df.columns]
        if not existing_cols:
            continue
        with st.expander(section_name, expanded=section_name in ("GitHub Metadata", "File Existence Checks", "CI")):
            section_data = row[existing_cols].to_frame(name="Value").reset_index()
            section_data.columns = ["Check", "Value"]
            st.dataframe(section_data, use_container_width=True, hide_index=True)

# ── Tab 3: Failing Checks ────────────────────────────────────────────────────
with tab3:
    st.subheader("Failing Checks Summary")
    st.caption("Count of repositories failing each health check (False = failing). Sorted worst-first.")

    active_df = df[df["github.is_archived"] != True] if "github.is_archived" in df.columns else df
    total_repos = len(active_df)

    all_rows = []
    for group, cols in CHECK_GROUPS.items():
        for col in cols:
            if col not in active_df.columns:
                continue
            series = active_df[col]
            # Count rows where value is explicitly False (failing)
            failing = int((series == False).sum())
            passing = int((series == True).sum())
            unknown = total_repos - failing - passing
            pct = round(failing / total_repos * 100, 1) if total_repos else 0
            all_rows.append({
                "Category": group,
                "Check": col,
                "Failing": failing,
                "Passing": passing,
                "Unknown/N/A": unknown,
                "% Failing": pct,
            })

    if all_rows:
        fail_df = pd.DataFrame(all_rows).sort_values("Failing", ascending=False)

        # Category filter
        categories = ["All"] + sorted(fail_df["Category"].unique().tolist())
        cat_filter = st.selectbox("Filter by category", categories)
        if cat_filter != "All":
            fail_df = fail_df[fail_df["Category"] == cat_filter]

        st.dataframe(fail_df, use_container_width=True, hide_index=True)
        st.metric("Active repos analysed", total_repos)
    else:
        st.info("No check columns found. Verify CSV schema.")

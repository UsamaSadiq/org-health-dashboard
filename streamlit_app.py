from __future__ import annotations

import streamlit as st

from dashboard.lib.config import get_feature_flags
from dashboard.ui import apply_base_style

st.set_page_config(page_title="Open edX Repo Health", layout="wide")
apply_base_style()

pages = [
    st.Page("pages/01_overview.py", title="Overview", icon="📊", default=True),
    st.Page("pages/02_repo_detail.py", title="Repo Detail", icon="🔍"),
    st.Page("pages/03_failing_checks.py", title="Failing Checks", icon="🚨"),
    st.Page("pages/04_needing_attention.py", title="Needing Attention", icon="⚠️"),
    st.Page("pages/05_what_changed.py", title="What Changed", icon="📈"),
    st.Page("pages/06_glossary.py", title="Glossary", icon="📖"),
]

flags = get_feature_flags()
if flags.get("enable_sql_page", False):
    pages.append(st.Page("pages/07_sql.py", title="SQL", icon="🧮"))
if flags.get("enable_badge_links", False):
    pages.append(st.Page("pages/08_badges.py", title="Badges", icon="🏷️"))

pages.append(st.Page("pages/99_healthz.py", title="Healthz", icon="🩺"))

st.navigation(pages).run()

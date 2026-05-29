from __future__ import annotations

import streamlit as st

from dashboard.lib.config import get_feature_flags
from dashboard.ui import apply_base_style, hydrate_from_query_params

st.set_page_config(page_title="Open edX Repo Health", layout="wide")
apply_base_style()
hydrate_from_query_params()

flags = get_feature_flags()

health_pages = [
    st.Page("pages/01_overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("pages/02_repo_detail.py", title="Repo Detail", icon=":material/search:"),
    st.Page("pages/03_failing_checks.py", title="Failing Checks", icon=":material/error:"),
    st.Page("pages/04_needing_attention.py", title="Needing Attention", icon=":material/priority_high:"),
    st.Page("pages/05_what_changed.py", title="What Changed", icon=":material/trending_up:"),
]

ownership_pages = []
if flags.get("enable_maintainer_views", True):
    ownership_pages.append(
        st.Page("pages/09_ownership_views.py", title="Ownership", icon=":material/groups:")
    )

tools_pages = []
if flags.get("enable_sql_page", False):
    tools_pages.append(st.Page("pages/07_sql.py", title="SQL", icon=":material/database:"))
if flags.get("enable_badge_links", False):
    tools_pages.append(st.Page("pages/08_badges.py", title="Badges", icon=":material/military_tech:"))
if flags.get("enable_year_in_review_cards", False) or flags.get("enable_embeddable_score_cards", False):
    tools_pages.append(st.Page("pages/10_cards.py", title="Cards", icon=":material/style:"))

meta_pages = [
    st.Page("pages/06_glossary.py", title="Glossary", icon=":material/menu_book:"),
    st.Page("pages/99_healthz.py", title="Healthz", icon=":material/monitor_heart:"),
]

sections: dict[str, list] = {"Health": health_pages}
if ownership_pages:
    sections["Ownership"] = ownership_pages
if tools_pages:
    sections["Tools"] = tools_pages
sections["Meta"] = meta_pages

st.navigation(sections).run()

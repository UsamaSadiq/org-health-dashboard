from __future__ import annotations

import streamlit as st

from dashboard.lib.config import get_feature_flags

st.set_page_config(page_title="Open edX Repo Health", layout="wide")

# Styling and query-param hydration deliberately live in each page's page_init()
# rather than here. Streamlit serves any file in pages/ by its filename-derived
# URL without this script's configuration taking effect, so anything applied
# here is missing on a direct deep link. See dashboard/ui/page.py.
#
# For the same reason the flag checks below only shape the nav; each optional
# page enforces its own flag via require_feature().
flags = get_feature_flags()

health_pages = [
    st.Page("pages/01_overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("pages/02_repo_detail.py", title="Repo Detail", icon=":material/search:"),
    st.Page("pages/03_failing_checks.py", title="Failing Checks", icon=":material/error:"),
    st.Page("pages/04_needing_attention.py", title="Needing Attention", icon=":material/priority_high:"),
    st.Page("pages/05_what_changed.py", title="What Changed", icon=":material/trending_up:"),
]

ownership_pages = []
# Backlog C4 asked for this section to be hidden when the snapshot carries no
# ownership fields, on the grounds that an empty top-level section reads as a
# broken product. Implemented and reverted: a page omitted from st.navigation()
# stops resolving as a URL, so /ownership_views answered with a "Page not found"
# modal and fell back to Overview. That breaks every previously shared link to
# it, which is a worse outcome for a link recipient than an honest empty page —
# and the cosmetic concern is addressable in the page's own empty state, which
# is what WP-6 did instead.
#
# Genuinely hiding it would mean moving the file out of pages/ so Streamlit's
# routing never sees it. That is a bigger change and needs a decision about
# whether the URL should keep working; see docs/UX_REVIEW_BACKLOG.md C4.
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
    st.Page("pages/06_glossary.py", title="Checks Catalog", icon=":material/menu_book:"),
]

sections: dict[str, list] = {"Health": health_pages}
if ownership_pages:
    sections["Ownership"] = ownership_pages
if tools_pages:
    sections["Tools"] = tools_pages
sections["Meta"] = meta_pages

st.navigation(sections).run()

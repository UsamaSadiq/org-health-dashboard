from __future__ import annotations

import streamlit as st

from dashboard.lib.badge import markdown_badge
from dashboard.data import load_snapshot
from dashboard.lib.share import base_url


def render() -> None:
    st.title("Embeddable Badges")
    st.caption("Phase 2 feature. Generates badge markdown for selected repository.")

    df = load_snapshot()
    if df.empty:
        st.error("No snapshot available.")
        return

    repo = st.selectbox("Repository", sorted(df["repo_name"].astype(str).tolist()))
    badge = markdown_badge(repo, base_url().rstrip("/"))
    st.write("Badge URL")
    st.code(badge.badge_url, language="text")
    st.write("Markdown")
    st.code(badge.markdown, language="markdown")


render()

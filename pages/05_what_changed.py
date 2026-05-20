from __future__ import annotations

import os

import streamlit as st

from dashboard.lib.bulletin import generate_weekly_bulletin
from dashboard.lib.config import get_feature_flags
from dashboard.lib.linking import serialize_state
from dashboard.lib.trends import load_history, summarize_weekly_changes


def render() -> None:
    st.title("What Changed This Week")

    try:
        history = load_history(days=30)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to load history: {exc}")
        return
    if len(history) < 2:
        st.warning("Not enough historical snapshots to compute weekly deltas.")
        return

    latest = history[-1]
    baseline = history[-2]
    changes = summarize_weekly_changes(latest.df, baseline.df)

    st.subheader("Newly failing checks")
    if changes["new_failures"].empty:
        st.success("No newly failing checks.")
    else:
        st.dataframe(changes["new_failures"], use_container_width=True)

    st.subheader("Newly passing checks")
    if changes["new_passes"].empty:
        st.info("No newly passing checks.")
    else:
        st.dataframe(changes["new_passes"], use_container_width=True)

    if get_feature_flags().get("enable_weekly_bulletin_export", True):
        commit_sha = os.getenv("GITHUB_SHA", "local")
        bulletin = generate_weekly_bulletin(
            changes["new_failures"],
            changes["new_passes"],
            dashboard_url="https://share.streamlit.io",
            commit_sha=commit_sha,
        )
        st.subheader("Weekly bulletin export")
        st.code(bulletin, language="markdown")
        st.download_button(
            "Download bulletin markdown",
            data=bulletin.encode("utf-8"),
            file_name="weekly-bulletin.md",
            mime="text/markdown",
        )

    st.text_input(
        "Copy link to this view",
        value=f"https://share.streamlit.io/?{serialize_state({'tab': 'what-changed'})}",
        key="changes_share_link",
    )


render()

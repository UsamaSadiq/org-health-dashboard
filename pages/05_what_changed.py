from __future__ import annotations

import os

import streamlit as st

from dashboard.lib.bulletin import generate_weekly_bulletin
from dashboard.lib.config import get_feature_flags
from dashboard.lib.share import base_url, share_link
from dashboard.data import load_history
from dashboard.lib.trends import summarize_weekly_changes
from dashboard.ui import share_link_block


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
        st.dataframe(changes["new_failures"], width="stretch")

    st.subheader("Newly passing checks")
    if changes["new_passes"].empty:
        st.info("No newly passing checks.")
    else:
        st.dataframe(changes["new_passes"], width="stretch")

    if get_feature_flags().get("enable_weekly_bulletin_export", True):
        commit_sha = os.getenv("GITHUB_SHA", "local")
        bulletin = generate_weekly_bulletin(
            changes["new_failures"],
            changes["new_passes"],
            dashboard_url=base_url().rstrip("/"),
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

    share_link_block(share_link({"tab": "what-changed"}), label="Copy link to this view")


render()

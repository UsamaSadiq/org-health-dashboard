from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.lib.config import get_feature_flags
from dashboard.data import load_my_repos, load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.share import share_link
from dashboard.ui import share_link_block


def _normalize_bucket(value: object) -> str:
    normalized = str(value).strip()
    return normalized if normalized else "Unassigned"


def _ownership_coverage(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    cols = ["ownership.theme", "ownership.squad", "ownership.priority"]
    existing = [col for col in cols if col in df.columns]
    if not existing:
        return 0.0
    populated = pd.Series(False, index=df.index)
    for col in existing:
        populated = populated | df[col].fillna("").astype(str).str.strip().ne("")
    return round(float(populated.mean()) * 100, 2)


def _group_summary(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in df.columns:
        return pd.DataFrame()
    group_df = df.copy()
    group_df[column] = group_df[column].map(_normalize_bucket)
    summary = (
        group_df.groupby(column, as_index=False)
        .agg(
            repo_count=("repo_name", "count"),
            avg_score=("score_composite", "mean"),
            d_or_f=("score_letter", lambda series: int(series.isin(["D", "F"]).sum())),
        )
        .sort_values(["repo_count", "avg_score"], ascending=[False, False])
    )
    summary["avg_score"] = summary["avg_score"].round(2)
    return summary


def render() -> None:
    st.title("Maintainer and Working Group Views")

    if not get_feature_flags().get("enable_maintainer_views", True):
        st.info("Maintainer views are disabled by feature flag.")
        return

    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No data available.")
        return

    coverage = _ownership_coverage(df)
    st.metric("Ownership Coverage", f"{coverage}%")
    if coverage < 20:
        st.warning(
            "Ownership data coverage is below the PRD trigger threshold (20%). "
            "Views remain available for early validation."
        )

    tab_theme, tab_squad, tab_my = st.tabs(["By Theme", "By Squad", "My Repos"])

    with tab_theme:
        theme_summary = _group_summary(df, "ownership.theme")
        if theme_summary.empty:
            st.info("No theme ownership data found.")
        else:
            st.dataframe(theme_summary, width="stretch")

    with tab_squad:
        squad_summary = _group_summary(df, "ownership.squad")
        if squad_summary.empty:
            st.info("No squad ownership data found.")
        else:
            st.dataframe(squad_summary, width="stretch")

    with tab_my:
        if not get_feature_flags().get("enable_my_repos_filter", True):
            st.info("My repos filter is disabled by feature flag.")
        else:
            st.caption(
                "Matches GitHub handle against repo owner from repo_name and ownership/maintainer fields when available."
            )
            handle = st.text_input("GitHub handle", value="", placeholder="e.g. openedx")
            if handle.strip():
                mine = calculate_scores(load_my_repos(handle.strip()))
                if mine.empty:
                    st.info("No repositories matched this handle in ownership fields.")
                else:
                    st.dataframe(
                        mine[["repo_name", "score_composite", "score_letter"]].sort_values("score_composite", ascending=False),
                        width="stretch",
                    )

    share_link_block(
        share_link({"tab": "ownership", "coverage": f"{coverage:.2f}"}),
        label="Copy link to this view",
    )


render()

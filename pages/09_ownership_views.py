from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.lib.config import get_feature_flags
from dashboard.data import load_my_repos, load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.share import share_link
from dashboard.ui import page_init, share_link_block


def _normalize_bucket(value: object) -> str:
    normalized = str(value).strip()
    return normalized if normalized else "Unassigned"


# catalog-info.yaml (spec.owner) is the primary source; the Google-Sheet
# theme/squad/priority columns are a secondary, 2U-only source.
_COVERAGE_COLS = [
    "ownership.owner_name",
    "ownership.owner",
    "ownership.theme",
    "ownership.squad",
    "ownership.priority",
]


def _has_data(df: pd.DataFrame, column: str) -> bool:
    return (
        column in df.columns
        and df[column].fillna("").astype(str).str.strip().ne("").any()
    )


def _ownership_coverage(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    existing = [col for col in _COVERAGE_COLS if col in df.columns]
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
    page_init()
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
    st.caption(
        "Ownership is sourced primarily from each repo's `catalog-info.yaml` "
        "(`spec.owner`, per OEP-55). Theme/Squad come from the working-group "
        "spreadsheet and are only present for orgs that maintain it."
    )
    if coverage < 20:
        st.warning(
            "Ownership data coverage is below the PRD trigger threshold (20%). "
            "Views remain available for early validation."
        )

    # By Owner is primary (catalog-info). Theme/Squad tabs only appear when the
    # secondary spreadsheet columns actually carry data.
    owner_col = next(
        (col for col in ("ownership.owner_name", "ownership.owner") if _has_data(df, col)),
        None,
    )
    tab_labels = ["By Owner"]
    if _has_data(df, "ownership.theme"):
        tab_labels.append("By Theme")
    if _has_data(df, "ownership.squad"):
        tab_labels.append("By Squad")
    tab_labels.append("My Repos")
    tabs = dict(zip(tab_labels, st.tabs(tab_labels)))

    with tabs["By Owner"]:
        if owner_col is None:
            st.info(
                "No owner data found. Populate `catalog-info.yaml` `spec.owner` "
                "in the repositories to enable this view."
            )
        else:
            owner_summary = _group_summary(df, owner_col)
            st.dataframe(owner_summary, width="stretch")

    if "By Theme" in tabs:
        with tabs["By Theme"]:
            st.dataframe(_group_summary(df, "ownership.theme"), width="stretch")

    if "By Squad" in tabs:
        with tabs["By Squad"]:
            st.dataframe(_group_summary(df, "ownership.squad"), width="stretch")

    with tabs["My Repos"]:
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

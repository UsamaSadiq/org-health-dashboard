from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.lib.clock import now_utc
from dashboard.lib.config import get_feature_flags
from dashboard.data import load_config, load_my_repos, load_scored_history, load_scored_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.ordering import rank
from dashboard.lib.share import share_link
from dashboard.lib.stewardship import (
    LIFECYCLE_COL,
    RELEASE_COL,
    at_risk_repos,
    has_column_data,
    production_or_release,
)
from dashboard.ui import empty_state, page_init, repo_table, share_link_block


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
        .pipe(rank, ["repo_count", "avg_score"], ascending=[False, False], tiebreak=column)
    )
    summary["avg_score"] = summary["avg_score"].round(2)
    return summary


def _history_baseline(days: int = 30) -> tuple[pd.DataFrame | None, object]:
    history = load_scored_history(days=days)
    if len(history) < 2:
        return None, None
    return history[0].df, history[0].timestamp


def _render_at_risk(df: pd.DataFrame) -> None:
    rule = load_config("attention_rules").get("rules", {}).get("stewardship_risk", {})
    if not rule.get("enabled", True):
        empty_state(
            "info",
            "The at-risk view is switched off for this deployment.",
            "Enable `stewardship_risk` in `attention_rules.yaml`.",
        )
        return
    baseline, since = _history_baseline()
    risky = at_risk_repos(df, baseline, now=now_utc(), rule=rule)

    st.caption(
        "Repositories owned by `openedx-unmaintained`, a single person, or nobody, "
        "that also show weak activity, no recent push, or a falling score. Ownership "
        "data starts with the 2026-09-24 snapshot, so score changes are shown for "
        "repos with thin ownership today, not changes in who owns them."
    )
    if since is not None:
        st.caption(f"Score change is measured against the {since} snapshot.")

    has_lifecycle = has_column_data(df, LIFECYCLE_COL) or has_column_data(df, RELEASE_COL)
    if has_lifecycle and not risky.empty:
        if st.toggle("Production or in a named release only", value=True):
            risky = risky[production_or_release(risky)]
    elif not has_lifecycle:
        st.caption("Lifecycle and release data are not in this snapshot yet.")

    if risky.empty:
        empty_state(
            "good",
            "No repositories match.",
            "Nothing with thin ownership shows an activity warning under the "
            "`stewardship_risk` rule in `attention_rules.yaml`.",
        )
        return

    risky = rank(risky, ["owner_status", "score_composite"], ascending=[False, True], tiebreak="repo_name")
    repo_table(
        risky,
        columns=[
            "repo_name", "owner_status", "owner", "lifecycle", "release",
            "score_composite", "score_letter", "score_activity", "days_since_push",
            "delta", "reasons", "catalog_link",
        ],
        link_to_detail=True,
        extra_config={
            "catalog_link": st.column_config.LinkColumn("Backstage", display_text="Catalog"),
        },
    )
    st.download_button(
        "Download At-Risk List",
        risky.to_csv(index=False).encode("utf-8"),
        file_name="at-risk-ownership.csv",
        mime="text/csv",
    )


def render() -> None:
    page_init()
    st.title("Maintainer and Working Group Views")

    if not get_feature_flags().get("enable_maintainer_views", True):
        empty_state(
            "info",
            "Maintainer views are switched off for this deployment.",
            "Enable `enable_maintainer_views` in `dashboard/config/feature_flags.yaml`.",
        )
        return

    df = load_scored_snapshot()
    if df.empty:
        empty_state(
            "error",
            "No snapshot available.",
            "The upstream CSV and the local cache are both empty.",
        )
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
            "Ownership data is not yet populated for most repositories, so these "
            "views are mostly empty. To appear here, a repository needs "
            "`spec.owner` set in its `catalog-info.yaml` (OEP-55)."
        )

    # By Owner is primary (catalog-info). Theme/Squad tabs only appear when the
    # secondary spreadsheet columns actually carry data.
    owner_col = next(
        (col for col in ("ownership.owner_name", "ownership.owner") if _has_data(df, col)),
        None,
    )
    tab_labels = ["By Owner"]
    if owner_col is not None:
        tab_labels.append("At Risk")
    if _has_data(df, "ownership.theme"):
        tab_labels.append("By Theme")
    if _has_data(df, "ownership.squad"):
        tab_labels.append("By Squad")
    tab_labels.append("My Repos")
    tabs = dict(zip(tab_labels, st.tabs(tab_labels)))

    with tabs["By Owner"]:
        if owner_col is None:
            empty_state(
                "info",
                "No owner data in this snapshot.",
                "A repository appears here once its `catalog-info.yaml` sets "
                "`spec.owner` (OEP-55). None currently do.",
            )
        else:
            owner_summary = _group_summary(df, owner_col)
            repo_table(owner_summary, empty_message="No owners found.")

    if "At Risk" in tabs:
        with tabs["At Risk"]:
            _render_at_risk(df)

    if "By Theme" in tabs:
        with tabs["By Theme"]:
            repo_table(_group_summary(df, "ownership.theme"), empty_message="No themes found.")

    if "By Squad" in tabs:
        with tabs["By Squad"]:
            repo_table(_group_summary(df, "ownership.squad"), empty_message="No squads found.")

    with tabs["My Repos"]:
        if not get_feature_flags().get("enable_my_repos_filter", True):
            empty_state(
                "info",
                "This view is switched off for this deployment.",
                "Enable `enable_my_repos_filter` in `dashboard/config/feature_flags.yaml`.",
            )
        else:
            st.caption(
                "Matches GitHub handle against repo owner from repo_name and ownership/maintainer fields when available."
            )
            handle = st.text_input("GitHub handle", value="", placeholder="e.g. openedx")
            if handle.strip():
                mine = calculate_scores(load_my_repos(handle.strip()))
                if mine.empty:
                    empty_state(
                        "info",
                        "No repositories matched that handle.",
                        "Ownership fields are largely unpopulated, so most repositories "
                        "cannot be matched to anyone yet.",
                    )
                else:
                    repo_table(
                        rank(mine, "score_composite", ascending=False),
                        columns=["repo_name", "score_composite", "score_letter"],
                        link_to_detail=True,
                        use_progress=True,
                    )

    share_link_block(
        share_link({"tab": "ownership", "coverage": f"{coverage:.2f}"}),
        label="Copy link to this view",
    )


render()

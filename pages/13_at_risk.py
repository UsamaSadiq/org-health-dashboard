from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data import load_config, load_scored_history, load_scored_snapshot
from dashboard.lib.clock import now_utc
from dashboard.lib.config import get_feature_flags
from dashboard.lib.share import share_link
from dashboard.lib.stewardship import (
    LIFECYCLE_COL,
    OWNER_COL,
    RELEASE_COL,
    at_risk_repos,
    has_column_data,
    production_or_release,
)
from dashboard.ui import empty_state, page_init, repo_table, share_link_block


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
        "Repositories waiting for a maintainer (`openedx-unmaintained`), owned by a "
        "single person, or with no owner, that also show weak activity, no recent "
        "push, or a falling score. Deprecated and archived repositories are left out. Ownership "
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
    st.title("At Risk")

    if not get_feature_flags().get("enable_maintainer_views", True):
        empty_state(
            "info",
            "Maintainer views are switched off for this deployment.",
            "Enable `enable_maintainer_views` in `dashboard/config/feature_flags.yaml`.",
        )
        return

    df = load_scored_snapshot()
    if df.empty:
        empty_state("error", "No snapshot available.", "The upstream CSV and the local cache are both empty.")
        return
    if not has_column_data(df, OWNER_COL):
        empty_state(
            "info",
            "No owner data in this snapshot.",
            "A repository is assessed here once its `catalog-info.yaml` sets `spec.owner` (OEP-55).",
        )
        return

    _render_at_risk(df)
    share_link_block(share_link({"tab": "at-risk"}), label="Copy link to this view")


render()

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from dashboard.lib.data import export_json_payload, load_config, load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.schema import TIMESTAMP_COL, parse_snapshot_date
from dashboard.lib.share import share_link
from dashboard.lib.trends import load_history
from dashboard.ui import render_sidebar_filters, share_link_block
from dashboard.ui.banners import render_freshness_banner
from dashboard.ui.charts import category_pass_rate_bar, grade_histogram, top_failing_bar
from dashboard.ui.kpi import render_kpi_strip


CATEGORY_GROUPS = {
    "File Existence": lambda c: c.startswith("exists."),
    "CI / Tooling": lambda c: c in {"github_actions", "renovate.configured", "travis_ci.active", "travis_yml.parsable", "tox_tox_section"},
    "Dependencies": lambda c: c.startswith("dependabot.") or c.startswith("dependencies."),
    "Documentation": lambda c: c in {"readthedocs_config.exists", "docs.build_badge"},
    "README": lambda c: c.startswith("readme."),
}


def _category_pass_rates(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, predicate in CATEGORY_GROUPS.items():
        usable = [c for c in frame.columns if predicate(c)]
        if not usable:
            continue
        values = frame[usable].astype(str).apply(lambda s: s.str.lower())
        pass_count = values.isin(["true", "1", "yes"]).sum().sum()
        total = len(frame) * len(usable)
        rate = (pass_count / total) * 100 if total else 0
        rows.append({"category": name, "pass_rate": round(rate, 2)})
    return pd.DataFrame(rows)


def _top_failing(frame: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    check_cols = [
        col for col in frame.columns
        if "." in col and not col.startswith("github.") and col not in {"repo_name", TIMESTAMP_COL}
    ]
    rows = []
    for col in check_cols:
        is_fail = frame[col].astype(str).str.lower().isin(["false", "0", "no", "fail", "failing"])
        count = int(is_fail.sum())
        if count > 0:
            rows.append({"check": col, "failing": count})
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("failing", ascending=False).head(limit)


def _baseline_frame() -> pd.DataFrame | None:
    """Return the earliest snapshot in the last 7 days, scored, for KPI deltas."""
    try:
        history = load_history(days=7)
    except Exception:
        return None
    if len(history) < 2:
        return None
    return calculate_scores(history[0].df)


def _top_movers(frame: pd.DataFrame) -> pd.DataFrame:
    try:
        history = load_history(days=30)
    except Exception:
        return pd.DataFrame()
    if len(history) < 2:
        return pd.DataFrame()

    baseline = calculate_scores(history[0].df)
    recent = frame[["repo_name", "score_composite"]]
    merged = recent.merge(
        baseline[["repo_name", "score_composite"]].rename(columns={"score_composite": "baseline_score"}),
        on="repo_name",
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame()
    merged["delta"] = (merged["score_composite"] - merged["baseline_score"]).round(2)
    return merged.sort_values("delta", ascending=False)


def render() -> None:
    df = load_snapshot()
    if df.empty:
        st.title("Open edX Repository Health Dashboard")
        st.error("No data available from upstream CSV or local cache.")
        return

    df = calculate_scores(df)
    snapshot_date = (
        parse_snapshot_date(df[TIMESTAMP_COL].iloc[0]) if TIMESTAMP_COL in df.columns else None
    )

    data_cfg = load_config("data_source")
    stale_hours = int(data_cfg.get("stale_threshold_hours", 48))
    critical_hours = int(data_cfg.get("critically_stale_threshold_hours", 168))

    # ------------------------------------------------------------------ header
    st.title("Open edX Repository Health")
    st.caption(
        f"Snapshot {snapshot_date.isoformat() if snapshot_date else 'unknown'} · "
        "drill in via the sidebar nav."
    )
    render_freshness_banner(snapshot_date, stale_hours, critical_hours)

    filters = render_sidebar_filters()
    working = filters.apply(df)
    if working.empty:
        st.warning("No repositories match the current filters.")
        return

    # ----------------------------------------------------------- 1. signals
    baseline = _baseline_frame()
    scoped_baseline = filters.apply(baseline) if baseline is not None else None
    render_kpi_strip(working, baseline=scoped_baseline)

    # ------------------------------------------------------- 2. primary chart
    primary_tab, category_tab, failing_tab = st.tabs(
        ["Grade distribution", "Per-category pass rate", "Top failing checks"]
    )
    with primary_tab:
        st.plotly_chart(grade_histogram(working), use_container_width=True)
    with category_tab:
        category_df = _category_pass_rates(working)
        if category_df.empty:
            st.info("No categorizable check columns in this snapshot.")
        else:
            st.plotly_chart(category_pass_rate_bar(category_df), use_container_width=True)
    with failing_tab:
        fail_df = _top_failing(working)
        if fail_df.empty:
            st.success("No failing checks in the current filter scope.")
        else:
            st.plotly_chart(top_failing_bar(fail_df), use_container_width=True)
            st.caption("Drill down on individual checks in **Failing Checks**.")

    # ---------------------------------------------- 3. ranked tables + movers
    ranked = working[["repo_name", "score_composite", "score_letter"]].sort_values(
        "score_composite", ascending=False
    )

    st.subheader("Highlights")
    hi_left, hi_right = st.columns(2)
    with hi_left:
        st.markdown("**Top 5**")
        st.dataframe(ranked.head(5), use_container_width=True, hide_index=True)
    with hi_right:
        st.markdown("**Bottom 5**")
        st.dataframe(ranked.tail(5).iloc[::-1], use_container_width=True, hide_index=True)

    movers = _top_movers(working)
    if not movers.empty:
        mv_left, mv_right = st.columns(2)
        with mv_left:
            st.markdown("**Biggest gainers (30d)**")
            st.dataframe(
                movers.head(5)[["repo_name", "delta"]],
                use_container_width=True,
                hide_index=True,
            )
        with mv_right:
            st.markdown("**Biggest losers (30d)**")
            st.dataframe(
                movers.tail(5)[["repo_name", "delta"]].sort_values("delta"),
                use_container_width=True,
                hide_index=True,
            )

    # ---------------------------------------- 4. full table (collapsed default)
    with st.expander(f"Full table — {len(ranked)} repos", expanded=False):
        table_with_links = ranked.copy()
        table_with_links["repo_link"] = table_with_links["repo_name"].map(
            lambda repo: share_link({"tab": "detail", "repo": str(repo)})
        )
        st.dataframe(
            table_with_links,
            use_container_width=True,
            hide_index=True,
            column_config={
                "repo_link": st.column_config.LinkColumn("Open in Repo Detail"),
            },
        )

    # --------------------------------------------- 5. share + export footer
    state = {"tab": "overview", **filters.as_query_params()}
    with st.expander("Share & export", expanded=False):
        share_link_block(share_link(state), label="Copy link to this view")

        export_name = f"openedx-health-{datetime.now(timezone.utc).date().isoformat()}"
        dl_left, dl_right = st.columns(2)
        dl_left.download_button(
            "Download CSV",
            data=ranked.to_csv(index=False).encode("utf-8"),
            file_name=f"{export_name}.csv",
            mime="text/csv",
        )
        json_payload = export_json_payload(
            ranked,
            {
                "snapshot_timestamp": snapshot_date.isoformat() if snapshot_date else "unknown",
                "filters": state,
                "scoring_config_version": str(working.get("score_config_version", pd.Series(["unknown"])).iloc[0]),
                "dashboard_version": "1.0.0",
                "data_source_url": data_cfg.get("data_source_url", data_cfg.get("csv_url", "")),
            },
        )
        dl_right.download_button(
            "Download JSON",
            data=json_payload.encode("utf-8"),
            file_name=f"{export_name}.json",
            mime="application/json",
        )


render()

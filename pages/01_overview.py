from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.lib.data import export_json_payload, load_config, load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.schema import TIMESTAMP_COL, parse_snapshot_date
from dashboard.lib.linking import serialize_state
from dashboard.lib.trends import load_history
from dashboard.ui.banners import render_freshness_banner
from dashboard.ui.kpi import render_kpi_strip
from dashboard.ui.charts import grade_histogram


def _filter_frame(df: pd.DataFrame, archived: bool, search: str, tier: str) -> pd.DataFrame:
    filtered = df.copy()
    if "github.is_archived" in filtered.columns and not archived:
        filtered = filtered[filtered["github.is_archived"] != True]  # noqa: E712
    if search:
        filtered = filtered[
            filtered["repo_name"].astype(str).str.contains(search, case=False, na=False)
        ]
    if tier and tier != "all" and "repo_tier" in filtered.columns:
        filtered = filtered[filtered["repo_tier"] == tier]
    return filtered


def _category_pass_rates(frame: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "File Existence": [c for c in frame.columns if c.startswith("exists.")],
        "CI / Tooling": [
            c
            for c in frame.columns
            if c in {"github_actions", "renovate.configured", "travis_ci.active", "travis_yml.parsable", "tox_tox_section"}
        ],
        "Dependencies": [c for c in frame.columns if c.startswith("dependabot.") or c.startswith("dependencies.")],
        "Documentation": [c for c in frame.columns if c in {"readthedocs_config.exists", "docs.build_badge"}],
        "README": [c for c in frame.columns if c.startswith("readme.")],
    }

    rows = []
    for name, cols in groups.items():
        usable = [col for col in cols if col in frame.columns]
        if not usable:
            continue
        values = frame[usable].astype(str).apply(lambda s: s.str.lower())
        pass_count = values.isin(["true", "1", "yes"]).sum().sum()
        total = len(frame) * len(usable)
        rate = (pass_count / total) * 100 if total else 0
        rows.append({"category": name, "pass_rate": round(rate, 2)})
    return pd.DataFrame(rows)


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
    merged["delta"] = merged["score_composite"] - merged["baseline_score"]
    return merged.sort_values("delta", ascending=False)


def render() -> None:
    st.title("Open edX Repository Health Dashboard")

    data_cfg = load_config("data_source")
    stale_hours = int(data_cfg.get("stale_threshold_hours", 48))
    critical_hours = int(data_cfg.get("critically_stale_threshold_hours", 168))

    df = load_snapshot()
    if df.empty:
        st.error("No data available from upstream CSV or local cache.")
        return

    df = calculate_scores(df)
    if TIMESTAMP_COL in df.columns:
        snapshot_date = parse_snapshot_date(df[TIMESTAMP_COL].iloc[0])
    else:
        snapshot_date = None

    render_freshness_banner(snapshot_date, stale_hours, critical_hours)

    search = st.text_input("Search repositories", value="", key="overview_search", help="Filter by repository name.")
    archived = st.checkbox("Include archived", value=False, key="overview_archived")
    tier = st.selectbox("Tier", options=["all", "critical", "important", "standard"], index=0)

    working = _filter_frame(df, archived=archived, search=search, tier=tier)
    if working.empty:
        st.warning("No repositories match the current filters.")
        return

    render_kpi_strip(working)

    st.plotly_chart(grade_histogram(working), use_container_width=True)

    category_df = _category_pass_rates(working)
    if not category_df.empty:
        st.plotly_chart(
            px.bar(category_df, x="category", y="pass_rate", title="Per-category pass rate (%)", range_y=[0, 100]),
            use_container_width=True,
        )

    st.subheader("Top failing checks")
    check_cols = [
        col for col in working.columns if "." in col and not col.startswith("github.") and col not in {"repo_name", TIMESTAMP_COL}
    ]
    failing_counts = []
    for col in check_cols:
        is_fail = working[col].astype(str).str.lower().isin(["false", "0", "no", "fail", "failing"])
        count = int(is_fail.sum())
        if count > 0:
            failing_counts.append({"check": col, "failing": count})

    if failing_counts:
        fail_df = pd.DataFrame(failing_counts).sort_values("failing", ascending=False).head(10)
        st.plotly_chart(
            px.bar(fail_df, x="check", y="failing", title="Top 10 Most Failing Checks"),
            use_container_width=True,
        )

    st.subheader("Best and worst repositories")
    ranked = working[["repo_name", "score_composite", "score_letter"]].sort_values("score_composite", ascending=False)
    col1, col2 = st.columns(2)
    col1.dataframe(ranked.head(5), use_container_width=True)
    col2.dataframe(ranked.tail(5), use_container_width=True)

    movers = _top_movers(working)
    if not movers.empty:
        m1, m2 = st.columns(2)
        m1.dataframe(movers.head(5)[["repo_name", "delta"]], use_container_width=True)
        m2.dataframe(movers.tail(5)[["repo_name", "delta"]].sort_values("delta"), use_container_width=True)

    if st.toggle("Show as table", value=False, key="overview_table"):
        st.dataframe(ranked, use_container_width=True)

    state = {
        "tab": "overview",
        "search": search,
        "archived": str(archived).lower(),
        "tier": tier,
        "view": "table" if st.session_state.get("overview_table") else "charts",
    }
    query = serialize_state(state)
    share_url = f"https://share.streamlit.io/?{query}"
    st.text_input("Copy link to this view", value=share_url, key="overview_share_link")

    export_name = f"openedx-health-{datetime.now(timezone.utc).date().isoformat()}"
    csv_payload = ranked.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv_payload, file_name=f"{export_name}.csv", mime="text/csv")

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
    st.download_button("Download JSON", data=json_payload.encode("utf-8"), file_name=f"{export_name}.json", mime="application/json")

    table_with_links = ranked.copy()
    table_with_links["repo_link"] = table_with_links["repo_name"].map(
        lambda repo: f"https://share.streamlit.io/?tab=detail&repo={quote(str(repo), safe='')}"
    )
    st.dataframe(
        table_with_links,
        use_container_width=True,
        column_config={
            "repo_link": st.column_config.LinkColumn("Repo Detail Link"),
        },
    )


render()

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from rapidfuzz import fuzz

from dashboard.lib.config import get_config, get_feature_flags
from dashboard.lib.data import load_snapshot
from dashboard.lib.linking import github_issue_url, github_pr_compare_url, serialize_state
from dashboard.lib.remediation import get_remediation
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.trends import load_history


def _fuzzy_repo_options(repos: list[str], query: str) -> list[str]:
    if not query:
        return repos
    ranked = sorted(repos, key=lambda name: fuzz.partial_ratio(query.lower(), name.lower()), reverse=True)
    return ranked[:30]


@st.dialog("Raw check output")
def _raw_check_dialog(check_name: str, value: object) -> None:
    st.write(f"Check: {check_name}")
    st.code(str(value), language="text")


def _category_map(columns: list[str]) -> dict[str, list[str]]:
    return {
        "File Existence": [c for c in columns if c.startswith("exists.")],
        "CI / Tooling": [c for c in columns if c in {"github_actions", "renovate.configured", "travis_ci.active", "travis_yml.parsable", "tox_tox_section"}],
        "Dependencies": [c for c in columns if c.startswith("dependabot.") or c.startswith("dependencies.")],
        "Documentation": [c for c in columns if c in {"readthedocs_config.exists", "docs.build_badge"}],
        "README": [c for c in columns if c.startswith("readme.")],
    }


def _category_stats(row: pd.Series, category_cols: list[str]) -> tuple[int, int, int]:
    pass_count = fail_count = na_count = 0
    for col in category_cols:
        value = str(row.get(col, "")).strip().lower()
        if value in {"true", "1", "yes"}:
            pass_count += 1
        elif value in {"false", "0", "no", "fail", "failing"}:
            fail_count += 1
        else:
            na_count += 1
    return pass_count, fail_count, na_count


def _repo_sparkline(repo: str, cols: list[str]) -> pd.DataFrame:
    try:
        history = load_history(days=30)
    except Exception:
        return pd.DataFrame()

    points = []
    for snapshot in history:
        frame = snapshot.df
        if "repo_name" not in frame.columns:
            continue
        subset = frame[frame["repo_name"] == repo]
        if subset.empty:
            continue
        row = subset.iloc[0]
        pass_count, fail_count, _ = _category_stats(row, cols)
        total = pass_count + fail_count
        pass_rate = (pass_count / total) * 100 if total else 0
        points.append({"date": snapshot.timestamp, "pass_rate": round(pass_rate, 2)})
    return pd.DataFrame(points)


def _metric_radar(repo_row: pd.Series) -> go.Figure:
    per_metric = repo_row.get("score_per_metric", {}) or {}
    unavailable = set(repo_row.get("score_unavailable_metrics", []) or [])

    labels = list(per_metric.keys()) + [name for name in unavailable if name not in per_metric]
    if not labels:
        labels = ["no_metrics"]

    values = [per_metric.get(label, 100.0 if label in unavailable else 0.0) for label in labels]
    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            name="Metric score",
        )
    )
    if unavailable:
        fig.add_trace(
            go.Scatterpolar(
                r=[100 if label in unavailable else 0 for label in labels],
                theta=labels,
                mode="lines",
                line={"dash": "dot", "color": "#9ca3af"},
                name="Unavailable metric",
            )
        )
    fig.update_layout(polar={"radialaxis": {"visible": True, "range": [0, 100]}}, showlegend=True)
    return fig


def render() -> None:
    st.title("Repository Detail")

    feature_flags = get_feature_flags()
    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No data available.")
        return

    repos = sorted(df["repo_name"].dropna().astype(str).tolist())
    query_repo = str(st.query_params.get("repo", ""))
    query_compare = str(st.query_params.get("compare", ""))

    search = st.text_input("Find repository", value=query_repo or "", key="detail_search")
    options = _fuzzy_repo_options(repos, search)
    selected = st.selectbox("Repository", options=options, index=0 if options else None)
    compare_value = ""

    if feature_flags.get("enable_compare_mode", True):
        compare_options = [""] + [repo for repo in repos if repo != selected]
        compare_index = compare_options.index(query_compare) if query_compare in compare_options else 0
        compare_value = st.selectbox(
            "Compare with",
            options=compare_options,
            index=compare_index,
        )

    repo_row = df[df["repo_name"] == selected].iloc[0]
    st.subheader(selected)
    c1, c2, c3 = st.columns(3)
    c1.metric("Composite Score", f"{repo_row['score_composite']:.1f}")
    c2.metric("Grade", repo_row["score_letter"])
    c3.metric("Scoring Config", str(repo_row.get("score_config_version", "unknown")))

    detail_query = serialize_state({"tab": "detail", "repo": selected, "compare": compare_value})
    st.text_input("Copy link to this view", value=f"https://share.streamlit.io/?{detail_query}", key="detail_share_link")

    st.plotly_chart(_metric_radar(repo_row), use_container_width=True)

    check_cols = [
        col
        for col in df.columns
        if "." in col and not col.startswith("github.") and not col.startswith("language_bytes.")
    ]
    categories = _category_map(check_cols)

    st.subheader("Per-category mini cards")
    card_cols = st.columns(max(1, len(categories)))
    for idx, (category, cols) in enumerate(categories.items()):
        usable = [col for col in cols if col in df.columns]
        pass_count, fail_count, na_count = _category_stats(repo_row, usable)
        with card_cols[idx]:
            st.markdown(f"**{category}**")
            st.caption(f"Pass: {pass_count} | Fail: {fail_count} | N/A: {na_count}")
            spark = _repo_sparkline(selected, usable)
            if not spark.empty:
                st.plotly_chart(px.line(spark, x="date", y="pass_rate", title="30-day sparkline"), use_container_width=True)

    descriptions = get_config("check_descriptions").get("checks", {})
    pr_cfg = get_config("pr_templates")
    whitelisted = set(pr_cfg.get("whitelist", []))

    for check in sorted(check_cols):
        value = repo_row.get(check)
        failed = str(value).strip().lower() in {"false", "0", "no", "fail", "failing"}
        status = "FAIL" if failed else "PASS"
        short_desc = descriptions.get(check, {}).get("description", "No description available.")
        with st.expander(f"{check} - {status}", expanded=False):
            st.caption(short_desc)
            st.write(f"Status value: {value}")
            if st.button("View raw check output", key=f"raw-{selected}-{check}"):
                _raw_check_dialog(check, value)

            remediation = get_remediation(check)
            if failed and remediation:
                with st.expander("Show remediation", expanded=False):
                    st.write(remediation.description)
                    if remediation.snippet:
                        st.code(remediation.snippet, language="yaml")
                        st.text_area("Copy snippet", remediation.snippet, height=120, key=f"snippet-{selected}-{check}")
                    if remediation.source_url:
                        st.markdown(f"Source: {remediation.source_url}")

                issue_body_template = remediation.issue_body_template or (
                    "This repository fails a health check and needs remediation.\n\n"
                    "Filed via the Open edX Repository Health Dashboard ({dashboard_url}) - "
                    "please review and edit before submitting."
                )
                issue_url = github_issue_url(
                    selected,
                    check,
                    issue_body_template.replace("{dashboard_url}", "https://share.streamlit.io"),
                )
                st.link_button("File issue on this repo", issue_url)

                if feature_flags.get("enable_pr_template_generator", True) and check in whitelisted:
                    template = pr_cfg.get("templates", {}).get(check, {})
                    branch = template.get("branch_prefix", f"chore/{check.replace('.', '-')}")
                    title = template.get("title", f"chore: fix {check}")
                    body = template.get(
                        "body",
                        "Generated by dashboard - please review carefully.",
                    )
                    pr_url = github_pr_compare_url(selected, branch, title, body)
                    st.link_button("Open PR with fix", pr_url)

    if compare_value:
        compare_row = df[df["repo_name"] == compare_value]
        if not compare_row.empty:
            st.subheader("Comparison")
            merged = pd.DataFrame(
                {
                    "metric": ["score_composite", "score_letter", "github.last_push", "github.pulls_count"],
                    selected: [
                        repo_row.get("score_composite"),
                        repo_row.get("score_letter"),
                        repo_row.get("github.last_push"),
                        repo_row.get("github.pulls_count"),
                    ],
                    compare_value: [
                        compare_row.iloc[0].get("score_composite"),
                        compare_row.iloc[0].get("score_letter"),
                        compare_row.iloc[0].get("github.last_push"),
                        compare_row.iloc[0].get("github.pulls_count"),
                    ],
                }
            )
            st.dataframe(merged, use_container_width=True)


render()

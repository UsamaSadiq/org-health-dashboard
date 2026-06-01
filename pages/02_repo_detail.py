from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from rapidfuzz import fuzz

from dashboard.lib.config import get_config, get_feature_flags
from dashboard.data import load_history, load_snapshot
from dashboard.lib.linking import github_issue_url, github_pr_compare_url
from dashboard.lib.remediation import get_remediation
from dashboard.lib.scorecard import fetch_scorecard_result
from dashboard.lib.scoring import calculate_scores, pair_restricted_composite
from dashboard.lib.share import base_url, share_link
from dashboard.ui import grade_pill, share_link_block, status_chip
from dashboard.ui.charts import sparkline


CATEGORY_GROUPS: dict[str, callable] = {
    "File Existence": lambda c: c.startswith("exists."),
    "CI / Tooling": lambda c: c in {"github_actions", "renovate.configured", "travis_ci.active", "travis_yml.parsable", "tox_tox_section"},
    "Dependencies": lambda c: c.startswith("dependabot.") or c.startswith("dependencies."),
    "Documentation": lambda c: c in {"readthedocs_config.exists", "docs.build_badge"},
    "README": lambda c: c.startswith("readme."),
}

PASS_TOKENS = {"true", "1", "yes"}
FAIL_TOKENS = {"false", "0", "no", "fail", "failing"}


def _fuzzy_repo_options(repos: list[str], query: str) -> list[str]:
    if not query:
        return repos
    ranked = sorted(repos, key=lambda name: fuzz.partial_ratio(query.lower(), name.lower()), reverse=True)
    return ranked[:30]


def _classify(value: object) -> str:
    token = str(value).strip().lower()
    if token in PASS_TOKENS:
        return "pass"
    if token in FAIL_TOKENS:
        return "fail"
    return "unknown"


def _category_columns(df: pd.DataFrame) -> dict[str, list[str]]:
    columns = [
        col for col in df.columns
        if "." in col and not col.startswith("github.") and not col.startswith("language_bytes.")
    ]
    return {name: [c for c in columns if predicate(c)] for name, predicate in CATEGORY_GROUPS.items()}


def _category_stats(row: pd.Series, category_cols: list[str]) -> tuple[int, int, int]:
    pass_count = fail_count = na_count = 0
    for col in category_cols:
        bucket = _classify(row.get(col, ""))
        if bucket == "pass":
            pass_count += 1
        elif bucket == "fail":
            fail_count += 1
        else:
            na_count += 1
    return pass_count, fail_count, na_count


@st.cache_data(ttl=600, show_spinner=False)
def _history_for_repo(repo: str) -> list[dict]:
    try:
        history = load_history(days=30)
    except Exception:
        return []
    out = []
    for snapshot in history:
        frame = snapshot.df
        if "repo_name" not in frame.columns:
            continue
        subset = frame[frame["repo_name"] == repo]
        if subset.empty:
            continue
        out.append({"date": snapshot.timestamp, "row": subset.iloc[0]})
    return out


def _repo_sparkline(repo: str, cols: list[str]) -> pd.DataFrame:
    points = []
    for entry in _history_for_repo(repo):
        pass_count, fail_count, _ = _category_stats(entry["row"], cols)
        total = pass_count + fail_count
        if total == 0:
            continue
        points.append({"date": entry["date"], "pass_rate": round((pass_count / total) * 100, 2)})
    return pd.DataFrame(points)


def _metric_radar(repo_row: pd.Series, *, compare_row: pd.Series | None = None, compare_label: str = "") -> go.Figure:
    per_metric = repo_row.get("score_per_metric", {}) or {}
    unavailable = set(repo_row.get("score_unavailable_metrics", []) or [])
    labels = list(per_metric.keys()) + [name for name in unavailable if name not in per_metric]
    if not labels:
        labels = ["no_metrics"]

    values = [per_metric.get(label, 100.0 if label in unavailable else 0.0) for label in labels]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values, theta=labels, fill="toself", name=str(repo_row.get("repo_name", "Selected"))))

    if compare_row is not None:
        compare_metrics = compare_row.get("score_per_metric", {}) or {}
        compare_values = [compare_metrics.get(label, 0.0) for label in labels]
        fig.add_trace(go.Scatterpolar(r=compare_values, theta=labels, fill="toself", name=compare_label or "Compare", opacity=0.5))

    fig.update_layout(polar={"radialaxis": {"visible": True, "range": [0, 100]}}, showlegend=True)
    return fig


def _category_card(category: str, repo: str, row: pd.Series, cols: list[str], *, key_prefix: str) -> dict[str, int]:
    pass_count, fail_count, na_count = _category_stats(row, cols)
    total = pass_count + fail_count
    pass_rate = (pass_count / total) * 100 if total else 0
    with st.container(border=True):
        head_left, head_right = st.columns([3, 2])
        with head_left:
            st.markdown(f"**{category}**")
        with head_right:
            chip = (
                status_chip("pass", f"{pass_rate:.0f}% pass")
                if pass_rate >= 80
                else status_chip("warn", f"{pass_rate:.0f}% pass")
                if pass_rate >= 50
                else status_chip("fail", f"{pass_rate:.0f}% pass")
                if total > 0
                else status_chip("unknown", "no data")
            )
            st.markdown(f"<div style='text-align:right'>{chip}</div>", unsafe_allow_html=True)
        st.caption(f"Pass {pass_count} · Fail {fail_count} · N/A {na_count}")
        spark = _repo_sparkline(repo, cols)
        if not spark.empty and len(spark) >= 2:
            st.plotly_chart(sparkline(spark), width="stretch", key=f"spark-{key_prefix}-{category}")
    return {"pass": pass_count, "fail": fail_count, "na": na_count}


def _delta_badge(current: int, baseline: int, *, lower_is_better: bool = False) -> str:
    delta = current - baseline
    if delta == 0:
        return status_chip("unknown", "—")
    sign = "+" if delta > 0 else ""
    improving = (delta < 0) if lower_is_better else (delta > 0)
    return status_chip("pass" if improving else "fail", f"{sign}{delta}")


def _render_compare_panel(left_row: pd.Series, right_row: pd.Series, df: pd.DataFrame) -> None:
    st.subheader("Side-by-side comparison")
    left_name = str(left_row["repo_name"])
    right_name = str(right_row["repo_name"])

    pair = pair_restricted_composite(left_row, right_row)
    shared_count = len(pair["metrics"])
    own_count_left = len(left_row.get("score_per_metric", {}) or {})
    own_count_right = len(right_row.get("score_per_metric", {}) or {})

    head_left, head_right = st.columns(2)
    with head_left:
        st.markdown(f"#### {left_name}")
        st.markdown(
            grade_pill(str(left_row.get("score_letter", "")))
            + f" &nbsp; **{pair['score_a']:.1f}** &nbsp;"
            + status_chip("unknown", f"{shared_count}/{own_count_left} shared"),
            unsafe_allow_html=True,
        )
    with head_right:
        st.markdown(f"#### {right_name}")
        st.markdown(
            grade_pill(str(right_row.get("score_letter", "")))
            + f" &nbsp; **{pair['score_b']:.1f}** &nbsp;"
            + status_chip("unknown", f"{shared_count}/{own_count_right} shared"),
            unsafe_allow_html=True,
        )

    if shared_count == 0:
        st.warning(
            "These repositories share no available metrics — composite scores "
            "are not directly comparable. Showing each repo's own composite."
        )
    else:
        st.caption(
            f"Composites above are renormalized over the {shared_count} metric(s) "
            f"available on both repos: {', '.join(pair['metrics'])}. "
            f"Pair coverage: {pair['coverage'] * 100:.0f}% of configured weight."
        )

    sub_cols = st.columns(2)
    with sub_cols[0]:
        s_l = left_row.get("score_structural")
        a_l = left_row.get("score_activity")
        st.caption(
            f"Structural: **{s_l:.1f}**" if s_l is not None else "Structural: —"
        )
        st.caption(
            f"Activity (recency): **{a_l:.1f}**" if a_l is not None else "Activity: —"
        )
    with sub_cols[1]:
        s_r = right_row.get("score_structural")
        a_r = right_row.get("score_activity")
        st.caption(
            f"Structural: **{s_r:.1f}**" if s_r is not None else "Structural: —"
        )
        st.caption(
            f"Activity (recency): **{a_r:.1f}**" if a_r is not None else "Activity: —"
        )

    st.plotly_chart(
        _metric_radar(left_row, compare_row=right_row, compare_label=right_name),
        width="stretch",
        key=f"compare-radar-{left_name}-{right_name}",
    )

    categories = _category_columns(df)
    for category, cols in categories.items():
        if not cols:
            continue
        col_left, col_mid, col_right = st.columns([5, 2, 5])
        with col_left:
            left_stats = _category_card(category, left_name, left_row, cols, key_prefix=f"L-{left_name}")
        with col_right:
            right_stats = _category_card(category, right_name, right_row, cols, key_prefix=f"R-{right_name}")
        with col_mid:
            st.markdown("<div style='text-align:center; padding-top: 16px'>", unsafe_allow_html=True)
            st.markdown(f"Pass {_delta_badge(left_stats['pass'], right_stats['pass'])}", unsafe_allow_html=True)
            st.markdown(f"Fail {_delta_badge(left_stats['fail'], right_stats['fail'], lower_is_better=True)}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)


def _render_check_expander(check: str, repo_row: pd.Series, selected_repo: str, *, descriptions: dict, pr_cfg: dict, feature_flags: dict, whitelisted: set[str]) -> None:
    value = repo_row.get(check)
    bucket = _classify(value)
    label_chip = status_chip(bucket, bucket.upper())
    short_desc = descriptions.get(check, {}).get("description", "No description available.")
    header_label = f"{check}"

    with st.expander(header_label, expanded=False):
        st.markdown(label_chip, unsafe_allow_html=True)
        st.caption(short_desc)
        st.code(f"value = {value!r}", language="python")

        remediation = get_remediation(check)
        if bucket == "fail" and remediation:
            st.markdown("**Remediation**")
            st.write(remediation.description)
            if remediation.snippet:
                st.code(remediation.snippet, language="yaml")
            if remediation.source_url:
                st.markdown(f"[Source]({remediation.source_url})")

            issue_body_template = remediation.issue_body_template or (
                "This repository fails a health check and needs remediation.\n\n"
                "Filed via the Open edX Repository Health Dashboard ({dashboard_url}) - "
                "please review and edit before submitting."
            )
            issue_url = github_issue_url(
                selected_repo,
                check,
                issue_body_template.replace("{dashboard_url}", base_url().rstrip("/")),
            )
            action_left, action_right = st.columns(2)
            action_left.link_button("File issue on this repo", issue_url)

            if feature_flags.get("enable_pr_template_generator", True) and check in whitelisted:
                template = pr_cfg.get("templates", {}).get(check, {})
                branch = template.get("branch_prefix", f"chore/{check.replace('.', '-')}")
                title = template.get("title", f"chore: fix {check}")
                body = template.get("body", "Generated by dashboard - please review carefully.")
                pr_url = github_pr_compare_url(selected_repo, branch, title, body)
                action_right.link_button("Open PR with fix", pr_url)


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

    # ----------------------------------------------------------------- header
    pick_left, pick_right = st.columns([3, 3])
    with pick_left:
        search = st.text_input("Find repository", value=query_repo or "", key="detail_search", placeholder="fuzzy match…")
        options = _fuzzy_repo_options(repos, search)
        selected = st.selectbox("Repository", options=options, index=0 if options else None, key="detail_selected")
    compare_value = ""
    with pick_right:
        if feature_flags.get("enable_compare_mode", True):
            compare_options = [""] + [repo for repo in repos if repo != selected]
            compare_index = compare_options.index(query_compare) if query_compare in compare_options else 0
            compare_value = st.selectbox("Compare with", options=compare_options, index=compare_index, key="detail_compare")

    if not selected:
        st.info("Pick a repository to see its detail.")
        return

    repo_row = df[df["repo_name"] == selected].iloc[0]

    # --------------------------------------------------------- repo summary
    available_count = len(repo_row.get("score_per_metric", {}) or {})
    unavailable_count = len(repo_row.get("score_unavailable_metrics", []) or [])
    total_metrics = available_count + unavailable_count
    coverage_pct = float(repo_row.get("score_coverage", 0.0)) * 100

    st.markdown(
        f"## {selected} &nbsp; {grade_pill(str(repo_row.get('score_letter', '')))} &nbsp; "
        + status_chip(
            "warn" if coverage_pct < 80 else "pass",
            f"{available_count}/{total_metrics} metrics ({coverage_pct:.0f}% weight)",
        ),
        unsafe_allow_html=True,
    )
    structural = repo_row.get("score_structural")
    activity = repo_row.get("score_activity")
    sum_a, sum_b, sum_c, sum_d, sum_e = st.columns(5)
    sum_a.metric("Composite", f"{repo_row['score_composite']:.1f}")
    sum_b.metric("Grade", repo_row["score_letter"])
    sum_c.metric("Structural", f"{structural:.1f}" if structural is not None else "—",
                 help="Baseline compliance: README, CI, openedx.yaml, deps.")
    sum_d.metric("Activity", f"{activity:.1f}" if activity is not None else "—",
                 help="Commit recency only — PR response time, release frequency, and contributor signals are not yet collected.")
    sum_e.metric("Scoring config", str(repo_row.get("score_config_version", "unknown")))

    share_link_block(
        share_link({"tab": "detail", "repo": selected, "compare": compare_value}),
        label="Copy link to this view",
    )

    # ------------------------------------------------------- compare mode
    if compare_value:
        compare_row = df[df["repo_name"] == compare_value]
        if not compare_row.empty:
            _render_compare_panel(repo_row, compare_row.iloc[0], df)
            return

    # ------------------------------------------------------- single-repo view
    st.plotly_chart(_metric_radar(repo_row), width="stretch", key=f"radar-{selected}")

    if feature_flags.get("enable_scorecard_panel", False):
        with st.expander("OpenSSF Scorecard parity", expanded=False):
            try:
                scorecard = fetch_scorecard_result(selected)
            except Exception as exc:  # noqa: BLE001
                scorecard = None
                st.warning(f"Unable to fetch Scorecard data: {exc}")
            if scorecard is None:
                st.info("No public OpenSSF Scorecard result found for this repository.")
            else:
                m1, m2 = st.columns(2)
                m1.metric("Scorecard score", f"{scorecard.score:.2f}" if scorecard.score is not None else "n/a")
                m2.metric("Last scorecard date", scorecard.date or "n/a")
                if scorecard.checks:
                    checks_df = pd.DataFrame(
                        [{"check": item.name, "score": item.score, "reason": item.reason} for item in scorecard.checks]
                    )
                    st.dataframe(checks_df.sort_values("check"), width="stretch", hide_index=True)

    # ----------------------------------------------------- category cards
    st.subheader("Category overview")
    categories = _category_columns(df)
    grid_cols = st.columns(min(3, max(1, len(categories))))
    for idx, (category, cols) in enumerate(categories.items()):
        if not cols:
            continue
        with grid_cols[idx % len(grid_cols)]:
            _category_card(category, selected, repo_row, cols, key_prefix=selected)

    # ----------------------------------------------------- check drilldown
    check_cols = [c for cols in categories.values() for c in cols]
    if not check_cols:
        return

    st.subheader("Checks")
    control_left, control_right = st.columns([3, 2])
    with control_left:
        filter_choice = st.radio(
            "Filter",
            options=["Failing only", "All", "Passing", "Unknown"],
            horizontal=True,
            index=0,
            key="detail_filter",
        )
    with control_right:
        category_choice = st.selectbox(
            "Category",
            options=["All"] + [c for c, cols in categories.items() if cols],
            index=0,
            key="detail_category",
        )

    descriptions = get_config("check_descriptions").get("checks", {})
    pr_cfg = get_config("pr_templates")
    whitelisted = set(pr_cfg.get("whitelist", []))

    bucket_for_choice = {"Failing only": "fail", "Passing": "pass", "Unknown": "unknown"}.get(filter_choice)
    visible_checks = []
    for check in sorted(check_cols):
        if category_choice != "All":
            if check not in categories[category_choice]:
                continue
        if bucket_for_choice and _classify(repo_row.get(check)) != bucket_for_choice:
            continue
        visible_checks.append(check)

    st.caption(f"{len(visible_checks)} of {len(check_cols)} checks shown.")
    if not visible_checks:
        st.success("Nothing to show for the current filter.")
        return

    for check in visible_checks:
        _render_check_expander(
            check,
            repo_row,
            selected,
            descriptions=descriptions,
            pr_cfg=pr_cfg,
            feature_flags=feature_flags,
            whitelisted=whitelisted,
        )


render()

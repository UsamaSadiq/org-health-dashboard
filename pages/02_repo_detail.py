from __future__ import annotations

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

from dashboard.lib.config import get_config, get_feature_flags
from dashboard.data import load_scored_history, load_scored_snapshot
from dashboard.lib.linking import github_issue_url, github_pr_compare_url
from dashboard.lib.remediation import get_remediation
from dashboard.lib.schema import humanize_check
from dashboard.lib.scorecard import fetch_scorecard_result
from dashboard.lib.share import base_url, share_link
from dashboard.ui import empty_state, page_init, grade_pill, repo_table, share_link_block, status_chip
from dashboard.ui.charts import metric_score_bar, sparkline


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


def _history_for_repo(repo: str) -> list[dict]:
    """Per-snapshot rows for one repository.

    Deliberately not cached per repo: the underlying history is already cached by
    load_scored_history, and a per-repo layer meant browsing 20 repositories held
    20 slices of the same 30-day window (backlog H6). Filtering a cached frame is
    cheap; storing it 20 times is not.
    """
    try:
        history = load_scored_history(days=30)
    except Exception:  # noqa: BLE001 - absent history is normal
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


def _render_check_expander(check: str, repo_row: pd.Series, selected_repo: str, *, descriptions: dict, pr_cfg: dict, feature_flags: dict, whitelisted: set[str]) -> None:
    value = repo_row.get(check)
    bucket = _classify(value)
    label_chip = status_chip(bucket, bucket.upper())
    short_desc = descriptions.get(check, {}).get("description", "No description available.")
    # Status and a readable title in the *collapsed* header: previously every row
    # showed only the raw column name, so learning a check's state meant opening
    # it. A styled chip cannot go here (expander labels take limited markdown), so
    # the state is a text marker, which also keeps colour from being the only signal.
    marker = {"pass": "PASS", "fail": "FAIL"}.get(bucket, "—")
    header_label = f"`{marker}`  {humanize_check(check, descriptions)}"

    with st.expander(header_label, expanded=False):
        st.markdown(label_chip, unsafe_allow_html=True)
        st.caption(f"`{check}` · {short_desc}")
        # A Python repr ("value = 'False'") leaked the implementation. Show the
        # value plainly, and say so when absent rather than printing None/nan.
        rendered = str(value).strip()
        st.markdown(
            f"**Value:** `{rendered}`"
            if rendered and rendered.lower() != "nan"
            else "**Value:** _not recorded_"
        )

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
    page_init()
    st.title("Repository Detail")

    feature_flags = get_feature_flags()
    df = load_scored_snapshot()
    if df.empty:
        empty_state(
            "error",
            "No snapshot available.",
            "The upstream CSV and the local cache are both empty.",
        )
        return

    repos = sorted(df["repo_name"].dropna().astype(str).tolist())
    query_repo = str(st.query_params.get("repo", ""))

    # ----------------------------------------------------------------- header
    search = st.text_input("Find repository", value=query_repo or "", key="detail_search", placeholder="fuzzy match…")
    options = _fuzzy_repo_options(repos, search)
    selected = st.selectbox("Repository", options=options, index=0 if options else None, key="detail_selected")

    if not selected:
        empty_state(
            "info",
            "Pick a repository to see its detail.",
            "Type part of a name above, or arrive here from a link on Overview.",
        )
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
    category_measured = repo_row.get("score_category_measured_weight", {}) or {}

    def _subscore(value: object, category: str, base_help: str) -> tuple[str, str]:
        """Format a sub-score, refusing to look confident when it isn't.

        Activity renders a hard 100.0 on the live snapshot while four of its five
        metrics have no column at all, which implies the same confidence as a
        fully-measured Structural score sitting next to it. Below a majority of
        measured weight the number is withheld rather than dressed with a
        footnote nobody reads.
        """
        fraction = float(category_measured.get(category, 1.0) or 0.0)
        if value is None:
            return "—", f"{base_help} Not computable from this snapshot."
        if fraction < 0.5:
            return (
                "—",
                f"{base_help} Withheld: only {fraction:.0%} of this category's "
                f"weight is measured, so the number would be mostly the fixed "
                f"default of 50.",
            )
        suffix = "" if fraction > 0.999 else f" {fraction:.0%} of this category's weight is measured."
        return f"{float(value):.1f}", base_help + suffix

    struct_text, struct_help = _subscore(
        structural, "structural", "Baseline compliance: README, CI, openedx.yaml, deps."
    )
    act_text, act_help = _subscore(
        activity,
        "activity",
        "Commit recency, PR response time, PR closure ratio, release frequency and contributor signals.",
    )

    sum_a, sum_b, sum_c, sum_d = st.columns(4)
    sum_a.metric("Composite", f"{repo_row['score_composite']:.1f}")
    sum_b.metric("Grade", repo_row["score_letter"])
    sum_c.metric("Structural", struct_text, help=struct_help)
    sum_d.metric("Activity", act_text, help=act_help)

    share_link_block(
        share_link({"tab": "detail", "repo": selected}),
        label="Copy link to this view",
    )

    # ------------------------------------------------------- single-repo view
    st.plotly_chart(
        metric_score_bar(repo_row), width="stretch", key=f"metrics-{selected}",
        config={"displayModeBar": False},
    )
    st.caption(
        f"Scoring config {repo_row.get('score_config_version', 'unknown')} · "
        "bars show each metric's contribution; unmeasured metrics are marked."
    )

    if feature_flags.get("enable_scorecard_panel", False):
        with st.expander("OpenSSF Scorecard parity", expanded=False):
            try:
                scorecard = fetch_scorecard_result(selected)
            except Exception as exc:  # noqa: BLE001
                scorecard = None
                st.warning(f"Unable to fetch Scorecard data: {exc}")
            if scorecard is None:
                empty_state(
                    "info",
                    "No public OpenSSF Scorecard result for this repository.",
                    "Scorecard publishes results only for repositories it has scanned.",
                )
            else:
                m1, m2 = st.columns(2)
                m1.metric("Scorecard score", f"{scorecard.score:.2f}" if scorecard.score is not None else "n/a")
                m2.metric("Last scorecard date", scorecard.date or "n/a")
                if scorecard.checks:
                    checks_df = pd.DataFrame(
                        [{"check": item.name, "score": item.score, "reason": item.reason} for item in scorecard.checks]
                    )
                    repo_table(checks_df.sort_values("check"))

    # ----------------------------------------------------- category cards
    st.header("Category overview")
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

    st.header("Checks")
    control_left, control_right = st.columns([3, 2])
    with control_left:
        filter_choice = st.radio(
            "Filter",
            options=["Failing", "Passing", "Unknown", "All"],
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

    bucket_for_choice = {"Failing": "fail", "Passing": "pass", "Unknown": "unknown"}.get(filter_choice)
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
        empty_state(
            "info",
            "No checks match this filter.",
            "Switch the filter to All, or pick a different category.",
        )
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

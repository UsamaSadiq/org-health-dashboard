from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from dashboard.data import load_config, load_snapshot
from dashboard.lib.remediation import missing_remediation_checks

PASS_TOKENS = {"true", "1", "yes"}
FAIL_TOKENS = {"false", "0", "no", "fail", "failing"}


def _is_check_col(name: str) -> bool:
    return "." in name and not name.startswith("github.") and not name.startswith("language_bytes.")


def _score_map() -> dict[str, dict]:
    """Map each scoring column to its metric name, weight and weight-share."""
    metrics = load_config("scoring").get("metrics", {})
    total_weight = sum(float(cfg.get("weight", 0)) for cfg in metrics.values()) or 1.0
    mapping: dict[str, dict] = {}
    for metric_name, cfg in metrics.items():
        column = cfg.get("column")
        if not column:
            continue
        weight = float(cfg.get("weight", 0))
        mapping[column] = {
            "metric": metric_name,
            "weight": weight,
            "weight_pct": round(weight / total_weight * 100, 1),
            "status": cfg.get("status", "unavailable"),
        }
    return mapping


def _coverage(series: pd.Series) -> tuple[float, float]:
    """Return (populated %, pass %) for a check column."""
    values = series.fillna("").astype(str).str.strip()
    populated = values.ne("")
    populated_pct = round(float(populated.mean()) * 100, 1) if len(values) else 0.0
    lowered = values.str.lower()
    passes = lowered.isin(PASS_TOKENS)
    fails = lowered.isin(FAIL_TOKENS)
    denom = int((passes | fails).sum())
    pass_pct = round(int(passes.sum()) / denom * 100, 1) if denom else None
    return populated_pct, pass_pct


def _render_check(check: str, *, descriptions: dict, score_map: dict, df: pd.DataFrame,
                  missing_desc: set, missing_remediation: set) -> None:
    info = descriptions.get(check, {})
    title = info.get("title") or check
    with st.expander(f"**{title}**  ·  `{check}`"):
        st.write(info.get("description", "_No description entry yet._"))

        score = score_map.get(check)
        if score:
            flag = "✓ computable" if score["status"] == "computable" else "○ not yet collected"
            st.markdown(
                f"**Feeds score:** `{score['metric']}` — weight {score['weight_pct']}% ({flag})"
            )
        else:
            st.caption("Not part of the composite score (informational check).")

        meta_parts = []
        if info.get("chaoss_metric"):
            meta_parts.append(f"CHAOSS: {info['chaoss_metric']}")
        if info.get("scorecard_check"):
            meta_parts.append(f"Scorecard: {info['scorecard_check']}")
        if info.get("source_url"):
            meta_parts.append(f"[Source]({info['source_url']})")
        if meta_parts:
            st.caption(" · ".join(meta_parts))

        if check in df.columns:
            populated_pct, pass_pct = _coverage(df[check])
            cols = st.columns(2)
            cols[0].metric("Org coverage (populated)", f"{populated_pct}%")
            cols[1].metric("Pass rate", f"{pass_pct}%" if pass_pct is not None else "—")

        gaps = []
        if check in missing_desc:
            gaps.append("missing description")
        if check in missing_remediation:
            gaps.append("no remediation entry")
        if gaps:
            st.caption(":warning: Config gaps: " + ", ".join(gaps))


def _render_candidates() -> None:
    candidates = load_config("check_candidates").get("candidates", [])
    if not candidates:
        return
    st.header("Suggested candidate checks")
    st.caption(
        "Proposed additions to the health suite, informed by current community "
        "standards (CHAOSS, OpenSSF Scorecard). Not yet implemented."
    )
    proposed = [c for c in candidates if c.get("status") == "proposed"]
    phase2 = [c for c in candidates if c.get("status") == "phase-2"]

    if proposed:
        st.subheader("Near-term (local-file checks, zero API)")
        for c in proposed:
            with st.expander(f"**{c['name']}**"):
                st.write(c.get("rationale", ""))
                if c.get("feasibility"):
                    st.caption(f"How: {c['feasibility']}")
                meta = [f"CHAOSS: {c['chaoss_metric']}"] if c.get("chaoss_metric") else []
                if c.get("scorecard_check"):
                    meta.append(f"Scorecard: {c['scorecard_check']}")
                if meta:
                    st.caption(" · ".join(meta))

    if phase2:
        st.subheader("Phase 2 (need GitHub API / admin scope)")
        for c in phase2:
            with st.expander(f"**{c['name']}**"):
                st.write(c.get("rationale", ""))
                if c.get("feasibility"):
                    st.caption(f"How: {c['feasibility']}")


def render() -> None:
    st.title("Checks Catalog")
    st.caption(
        "Every health check currently collected, what it measures, whether it "
        "feeds the composite score, and how the org is doing on it."
    )

    descriptions = load_config("check_descriptions").get("checks", {})
    groups = load_config("check_groups").get("groups", [])
    score_map = _score_map()
    df = load_snapshot()
    check_columns = sorted([col for col in df.columns if _is_check_col(col)]) if not df.empty else []

    if not check_columns:
        st.warning("No check columns detected in snapshot.")
        _render_candidates()
        return

    missing_desc = {c for c in check_columns if c not in descriptions}
    missing_remediation = set(missing_remediation_checks(check_columns))
    scored = [c for c in check_columns if c in score_map]

    c1, c2, c3 = st.columns(3)
    c1.metric("Checks collected", len(check_columns))
    c2.metric("Feeding the score", len(scored))
    c3.metric("Missing descriptions", len(missing_desc))

    grouped_seen: set[str] = set()
    for group in groups:
        group_name = group.get("name", "Ungrouped")
        explicit = set(group.get("explicit", []))
        pattern = group.get("pattern")

        grouped_checks = [
            check for check in check_columns
            if check in explicit or (pattern and re.match(pattern, check))
        ]
        if not grouped_checks:
            continue

        st.header(group_name)
        for check in grouped_checks:
            grouped_seen.add(check)
            _render_check(
                check, descriptions=descriptions, score_map=score_map, df=df,
                missing_desc=missing_desc, missing_remediation=missing_remediation,
            )

    ungrouped = [c for c in check_columns if c not in grouped_seen]
    if ungrouped:
        st.header("Other checks")
        for check in ungrouped:
            _render_check(
                check, descriptions=descriptions, score_map=score_map, df=df,
                missing_desc=missing_desc, missing_remediation=missing_remediation,
            )

    _render_candidates()


render()

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from dashboard.lib.data import load_config, load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.schema import parse_last_push_utc
from dashboard.lib.share import share_link
from dashboard.ui import share_link_block


def _repo_tier(repo: str, tiers: dict) -> str:
    for tier in ["critical", "important", "standard"]:
        for configured in tiers.get(tier, []):
            if repo == configured or repo.endswith("/" + configured):
                return tier
    return "standard"


def render() -> None:
    st.title("Repos Needing Attention")

    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No data available.")
        return

    rules = load_config("attention_rules").get("rules", {})
    tiers_cfg = load_config("tiers")
    selected_tier = st.selectbox("Tier filter", ["all", "critical", "important", "standard"])

    now = datetime.now(timezone.utc)
    rows = []
    for _, row in df.iterrows():
        repo = str(row.get("repo_name", ""))
        tier = _repo_tier(repo, tiers_cfg)
        if selected_tier != "all" and tier != selected_tier:
            continue

        reasons: list[str] = []
        if rules.get("critical_low_grade", {}).get("enabled") and tier == "critical" and row.get("score_letter") in {"D", "F"}:
            reasons.append("critical tier with D/F grade")

        if rules.get("important_many_fails", {}).get("enabled") and tier == "important":
            fails = sum(
                str(row.get(col, "")).strip().lower() in {"false", "0", "no", "fail", "failing"}
                for col in df.columns
                if "." in col and not col.startswith("github.")
            )
            if fails >= int(rules.get("important_many_fails", {}).get("minimum_failing_checks", 5)):
                reasons.append("important tier with 5+ failing checks")

        if rules.get("no_commits_90d", {}).get("enabled"):
            last_push = parse_last_push_utc(row.get("github.last_push"))
            if last_push and (now - last_push).days >= int(rules.get("no_commits_90d", {}).get("days_without_commit", 90)):
                reasons.append("no commits in 90+ days")

        if rules.get("legacy_ci_signal", {}).get("enabled"):
            travis_col = rules.get("legacy_ci_signal", {}).get("travis_ci_active_column", "travis_ci.active")
            gha_col = rules.get("legacy_ci_signal", {}).get("github_actions_column", "github_actions")
            travis_active = str(row.get(travis_col, "")).strip().lower() in {"true", "1", "yes"}
            gha_active = str(row.get(gha_col, "")).strip().lower() in {"true", "1", "yes"}
            if travis_active and not gha_active:
                reasons.append("legacy CI signal: travis active but github_actions false")

        if reasons:
            rows.append(
                {
                    "repo_name": repo,
                    "tier": tier,
                    "score_composite": row.get("score_composite"),
                    "score_letter": row.get("score_letter"),
                    "reasons": "; ".join(reasons),
                }
            )

    if not rows:
        st.success("No repositories currently match the attention rules.")
        return

    result = pd.DataFrame(rows).sort_values(["tier", "score_composite"], ascending=[True, True])
    result = result.copy()
    result["repo_link"] = result["repo_name"].map(
        lambda repo: share_link({"tab": "detail", "repo": str(repo)})
    )
    st.dataframe(
        result,
        use_container_width=True,
        column_config={"repo_link": st.column_config.LinkColumn("Repo Detail Link")},
    )
    share_link_block(
        share_link({"tab": "needing-attention", "tier": selected_tier}),
        label="Copy link to this view",
    )

    st.download_button(
        "Download Attention List",
        result.to_csv(index=False).encode("utf-8"),
        file_name="needing-attention.csv",
        mime="text/csv",
    )


render()

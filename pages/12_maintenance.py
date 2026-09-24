from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data import load_config, load_maintenance
from dashboard.lib import maintenance
from dashboard.lib.share import share_link
from dashboard.ui import empty_state, page_init, repo_table, share_link_block

STATE_LABELS = {"failing": "Job failing", "not_landing": "PRs not merged", "healthy": "Healthy"}
WAVE_LABELS = {"not_started": "Not started", "pr_open": "PR open", "done": "Done", "not_applicable": "Not applicable"}

UPGRADE_COLUMNS = {
    "state_label": st.column_config.TextColumn("State", width="small"),
    "reason": st.column_config.TextColumn("Why"),
    "runs": st.column_config.TextColumn("Failed runs", width="small"),
    "last_merged": st.column_config.TextColumn("Last requirements PR merged"),
    "workflow_url": st.column_config.LinkColumn("Workflow", display_text="Runs"),
}
OPEN_PR_COLUMNS = {
    "pr_age_days": st.column_config.NumberColumn("Open for (days)", width="small"),
    "pr_url": st.column_config.LinkColumn("Migration PR", display_text=r"/pull/(\d+)$"),
    "pr_title": st.column_config.TextColumn("PR title", width="large"),
}
NOT_STARTED_COLUMNS = {
    "gaps": st.column_config.TextColumn("Still to do", width="large"),
}
REDUNDANT_COLUMNS = {
    "bot_pr_url": st.column_config.LinkColumn("Bot PR", display_text=r"/pull/(\d+)$"),
    "superseded_by_url": st.column_config.LinkColumn("Superseded by", display_text=r"/pull/(\d+)$"),
    "superseded_by_merged": st.column_config.TextColumn("Merged"),
    "confidence": st.column_config.TextColumn("Confidence"),
}


def _generated(payload: dict) -> str:
    return str(payload["metadata"].get("generated_at", ""))[:16].replace("T", " ") + " UTC"


def _missing(what: str) -> None:
    empty_state(
        "info",
        f"No {what} data yet.",
        "It is published daily by the collect-maintenance workflow; check back after its next run.",
    )


def _render_upgrade_jobs() -> None:
    payload = load_maintenance(maintenance.UPGRADE_JOBS)
    if payload is None:
        _missing("upgrade-job")
        return
    frame = pd.DataFrame(payload["records"])
    states = payload["metadata"].get("states", {})
    st.caption(
        "Each repo's weekly `upgrade-python-requirements.yml` job, from repo-tools' "
        f"`check_requirements_failures`. Collected {_generated(payload)}."
    )
    columns = st.columns(3)
    for column, state in zip(columns, STATE_LABELS):
        column.metric(STATE_LABELS[state], states.get(state, 0))
    st.caption(
        "Job failing: half or more of the last 10 runs failed, so no upgrade PR is produced. "
        "PRs not merged: the job works, but no requirements PR has been merged for 4+ weeks."
    )
    show_healthy = st.toggle("Include healthy repos", value=False)
    if not show_healthy:
        frame = frame[frame["state"] != "healthy"]
    frame = frame.assign(
        state_label=frame["state"].map(STATE_LABELS),
        runs=frame["github.upgrade_job_runs_failed"].astype(str) + " / " + frame["github.upgrade_job_runs_total"].astype(str),
        last_merged=frame["github.requirements_pr_last_merged"].fillna("never"),
    )
    repo_table(
        frame,
        columns=["repo_name", "state_label", "reason", "runs", "last_merged", "workflow_url"],
        extra_config=UPGRADE_COLUMNS,
        height=420,
        empty_message="No repos in these states.",
    )


def _render_wave(wave_id: str, wave: dict) -> None:
    payload = load_maintenance(maintenance.wave_file(wave_id))
    if payload is None:
        _missing(f"{wave['title']} wave")
        return
    summary = payload["metadata"].get("summary", {})
    st.markdown(f"**{wave['title']}**" + (f" · [tracking epic]({wave['epic']})" if wave.get("epic") else ""))
    st.progress(
        summary.get("percent_done", 0) / 100,
        text=f"{summary.get('done', 0)} of {summary.get('applicable', 0)} repos done ({summary.get('percent_done', 0)}%)",
    )
    columns = st.columns(3)
    for column, status in zip(columns, ("done", "pr_open", "not_started")):
        column.metric(WAVE_LABELS[status], summary.get(status, 0))
    st.caption(f"Done means: {_done_rule(wave)}. Collected {_generated(payload)}.")
    frame = pd.DataFrame(payload["records"])

    st.subheader("Open migration PRs, oldest first")
    open_prs = frame[frame["status"] == "pr_open"].sort_values("pr_age_days", ascending=False)
    repo_table(
        open_prs,
        columns=["repo_name", "pr_age_days", "pr_url", "pr_title"],
        extra_config=OPEN_PR_COLUMNS,
        height=380,
        empty_message="No migration PRs open.",
    )

    st.subheader("Not started")
    not_started = frame[frame["status"] == "not_started"]
    not_started = not_started.assign(
        gaps=[_gaps(missing, leftover) for missing, leftover in zip(not_started["missing"], not_started["leftover"])]
    )
    repo_table(
        not_started,
        columns=["repo_name", "gaps"],
        extra_config=NOT_STARTED_COLUMNS,
        height=380,
        empty_message="Every applicable repo has started.",
    )


def _done_rule(wave: dict) -> str:
    done = wave.get("done") or {}
    parts = []
    if done.get("present"):
        parts.append("has " + ", ".join(f"`{path}`" for path in done["present"]))
    if done.get("absent"):
        parts.append("no " + ", ".join(f"`{path}`" for path in done["absent"]))
    return "; ".join(parts)


def _gaps(missing: list, leftover: list) -> str:
    parts = [f"add {path}" for path in missing or []] + [f"remove {path}" for path in leftover or []]
    return ", ".join(parts)


def _render_redundant_prs() -> None:
    payload = load_maintenance(maintenance.REDUNDANT_PRS)
    if payload is None:
        _missing("redundant-PR")
        return
    meta = payload["metadata"]
    st.caption(
        "Bot campaign PRs made redundant by a later human campaign in the same repo. "
        f"Dry run: nothing has been closed. Collected {_generated(payload)}."
    )
    columns = st.columns(2)
    columns[0].metric("Redundant", meta.get("redundant", 0))
    columns[1].metric("Bot campaign PRs checked", meta.get("bot_prs_checked", 0))
    if not payload["records"]:
        empty_state("good", "No redundant bot PRs found.", "")
        return
    repo_table(
        pd.DataFrame(payload["records"]),
        columns=["repo_name", "bot_pr_url", "superseded_by_url", "superseded_by_merged", "confidence"],
        extra_config=REDUNDANT_COLUMNS,
        height=420,
    )


def render() -> None:
    page_init()
    st.title("Maintenance")
    st.caption(
        "Routine upkeep across the org: whether automated requirement upgrades land, how far "
        "platform-wide upgrade waves have reached, and bot PRs that are no longer needed. "
        "Collected daily from public GitHub data; read-only."
    )
    wave_configs = load_config("waves").get("waves", {})
    labels = ["Upgrade jobs"] + [f"Wave: {wave['title']}" for wave in wave_configs.values()] + ["Redundant PRs"]
    tabs = st.tabs(labels)
    with tabs[0]:
        _render_upgrade_jobs()
    for tab, (wave_id, wave) in zip(tabs[1:-1], wave_configs.items()):
        with tab:
            _render_wave(wave_id, wave)
    with tabs[-1]:
        _render_redundant_prs()

    share_link_block(share_link({"tab": "maintenance"}), label="Copy link to this view")


render()

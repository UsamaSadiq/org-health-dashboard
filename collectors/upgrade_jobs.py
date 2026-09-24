"""Pilot A: health of each repo's weekly requirements-upgrade job.

Collection is delegated to repo-tools' ``check_requirements_failures`` (pinned in
``requirements-collectors.txt``); this module only runs it and interprets its CSV.

The tool's "last requirements PR" counts a PR merged into any branch, so a date
alone can look healthy while every run fails (openedx/ccx-keys, 2026-09-24). A job
is therefore judged on its recent failure share as well as on the date.
"""
from __future__ import annotations

import csv
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

TOOL = "check_requirements_failures"
SOURCE = "repo-tools check_requirements_failures (edx-repo-tools, see requirements-collectors.txt)"
EXPECTED_COLUMNS = (
    "Repository",
    "Total Runs",
    "Failed Runs",
    "Success Runs",
    "Last PR Date",
    "PR Number",
    "PR URL",
    "Last Release Date",
    "Release Version",
)
FAILURE_SHARE_LIMIT = 0.5
STALE_WEEKS = 4


def run_tool(org: str, out_dir: Path, repos: list[str] | None = None) -> Path:
    command = [TOOL, "--org", org, "--output-path", str(out_dir)]
    for repo in repos or []:
        command += ["--repo", repo]
    subprocess.run(command, check=True)
    return max(out_dir.glob(f"requirements_check_{org}_*.csv"))


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = [column for column in EXPECTED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{TOOL} output is missing columns {missing}; its format changed.")
        return list(reader)


def _int(value: str) -> int:
    return int(value) if value and value.strip().isdigit() else 0


def _date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10]) if value and value.strip() else None
    except ValueError:
        return None


def _weeks_since(day: date | None, today: date) -> int | None:
    return (today - day).days // 7 if day else None


def _broken_reasons(failed: int, total: int, weeks: int | None) -> list[str]:
    reasons = []
    if total and failed / total >= FAILURE_SHARE_LIMIT:
        reasons.append(f"{failed} of the last {total} runs failed")
    if weeks is None:
        reasons.append("no requirements PR ever merged")
    elif weeks >= STALE_WEEKS:
        reasons.append(f"no requirements PR merged in {weeks} weeks")
    return reasons


def to_record(row: dict[str, str], *, org: str, today: date) -> dict[str, Any]:
    total, failed = _int(row["Total Runs"]), _int(row["Failed Runs"])
    last_merged = _date(row["Last PR Date"])
    last_release = _date(row["Last Release Date"])
    weeks = _weeks_since(last_merged, today)
    reasons = _broken_reasons(failed, total, weeks)
    return {
        "repo_name": f"{org}/{row['Repository']}",
        "github.upgrade_job_runs_total": total,
        "github.upgrade_job_runs_failed": failed,
        "github.upgrade_job_runs_success": _int(row["Success Runs"]),
        "github.requirements_pr_last_merged": last_merged.isoformat() if last_merged else None,
        "github.requirements_pr_url": row.get("PR URL") or None,
        "weeks_since_requirements_pr": weeks,
        "last_release_date": last_release.isoformat() if last_release else None,
        "last_release_version": row.get("Release Version") or None,
        "broken": bool(reasons),
        "broken_reasons": reasons,
        "workflow_url": f"https://github.com/{org}/{row['Repository']}/actions/workflows/upgrade-python-requirements.yml",
    }


def records(rows: list[dict[str, str]], *, org: str, today: date) -> list[dict[str, Any]]:
    built = [to_record(row, org=org, today=today) for row in rows]
    return sorted(built, key=lambda record: (not record["broken"], record["repo_name"]))

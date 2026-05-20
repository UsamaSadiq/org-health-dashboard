from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any

import pandas as pd
import requests

from dashboard.lib.config import get_config
from dashboard.lib.schema import REPO_COL, TIMESTAMP_COL, parse_snapshot_date


@dataclass(frozen=True)
class Snapshot:
    timestamp: date
    df: pd.DataFrame


def load_history(days: int | None = None) -> list[Snapshot]:
    """Load historical CSV snapshots from GitHub commit history."""
    cfg = get_config("data_source")
    history_repo = cfg.get("history_repo", "openedx/wg-maintenance")
    history_path = cfg.get("history_path", "dashboards/dashboard_main.csv")
    history_days = int(days or cfg.get("history_days", 90))

    owner, repo = history_repo.split("/", 1)
    commits_url = (
        f"https://api.github.com/repos/{owner}/{repo}/commits"
        f"?path={history_path}&per_page={min(history_days, 100)}"
    )
    response = requests.get(commits_url, timeout=30)
    response.raise_for_status()
    commits = response.json()

    snapshots: list[Snapshot] = []
    for commit in commits:
        sha = commit.get("sha")
        if not sha:
            continue
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{history_path}"
        raw_response = requests.get(raw_url, timeout=30)
        if raw_response.status_code != 200:
            continue

        df = pd.read_csv(StringIO(raw_response.text))
        if df.empty or TIMESTAMP_COL not in df.columns:
            continue

        stamp = parse_snapshot_date(df[TIMESTAMP_COL].iloc[0])
        if stamp is None:
            continue

        snapshots.append(Snapshot(timestamp=stamp, df=df))

    snapshots.sort(key=lambda snapshot: snapshot.timestamp)
    return snapshots


def summarize_weekly_changes(current: pd.DataFrame, previous: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return newly-failing and newly-passing checks since previous snapshot."""
    if current.empty or previous.empty or REPO_COL not in current.columns or REPO_COL not in previous.columns:
        return {"new_failures": pd.DataFrame(), "new_passes": pd.DataFrame()}

    shared_checks = [
        col
        for col in current.columns
        if col in previous.columns and _looks_like_check_column(col)
    ]
    if not shared_checks:
        return {"new_failures": pd.DataFrame(), "new_passes": pd.DataFrame()}

    current_indexed = current.set_index(REPO_COL)
    previous_indexed = previous.set_index(REPO_COL)
    common_repos = current_indexed.index.intersection(previous_indexed.index)

    new_failures: list[dict[str, Any]] = []
    new_passes: list[dict[str, Any]] = []

    for repo in common_repos:
        for check in shared_checks:
            now_fail = _is_failing(current_indexed.at[repo, check])
            before_fail = _is_failing(previous_indexed.at[repo, check])
            if now_fail and not before_fail:
                new_failures.append({"repo_name": repo, "check": check})
            if before_fail and not now_fail:
                new_passes.append({"repo_name": repo, "check": check})

    return {
        "new_failures": pd.DataFrame(new_failures),
        "new_passes": pd.DataFrame(new_passes),
    }


def _looks_like_check_column(name: str) -> bool:
    return "." in name and not name.startswith("github.") and not name.startswith("language_bytes.")


def _is_failing(value: Any) -> bool:
    as_str = str(value).strip().lower()
    if as_str in {"false", "0", "no", "fail", "failing"}:
        return True
    return False
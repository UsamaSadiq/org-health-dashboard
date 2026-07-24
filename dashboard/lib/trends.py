from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from dashboard.lib.config import DASHBOARD_DIR, get_config
from dashboard.lib.schema import REPO_COL, TIMESTAMP_COL, parse_snapshot_date

logger = logging.getLogger(__name__)

_HISTORY_CACHE = DASHBOARD_DIR.parent / ".cache" / "dashboard_data" / "history.csv"


@dataclass(frozen=True)
class Snapshot:
    timestamp: date
    df: pd.DataFrame


def _history_url(cfg: dict[str, Any]) -> str:
    """Raw URL of the pre-computed history file on the data repo's main branch."""
    explicit = cfg.get("history_csv_url")
    if explicit:
        return str(explicit)
    history_repo = cfg.get("history_repo", "openedx/wg-maintenance")
    history_file = cfg.get("history_file", "dashboards/dashboard_history.csv")
    return f"https://raw.githubusercontent.com/{history_repo}/main/{history_file}"


def _fetch_history_frame(cfg: dict[str, Any]) -> pd.DataFrame | None:
    """Fetch the single pre-computed history file, caching it for offline fallback.

    Makes exactly one HTTP request to the same static-file host as the main
    snapshot — no GitHub API calls at runtime (the locked architecture forbids
    them; unauthenticated API access is rate-limited on Streamlit Cloud).
    """
    url = _history_url(cfg)
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text))
        try:
            _HISTORY_CACHE.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(_HISTORY_CACHE, index=False)
        except OSError as exc:  # caching is best-effort
            logger.warning("Could not cache history file: %s", exc)
        return frame
    except Exception as exc:  # noqa: BLE001 - resilience by design
        logger.warning("History fetch failed, trying local cache: %s", exc)
        if _HISTORY_CACHE.exists():
            return pd.read_csv(_HISTORY_CACHE)
    return None


def load_history(days: int | None = None) -> list[Snapshot]:
    """Load historical snapshots from a single pre-computed history file.

    The history file accumulates one block of rows per snapshot date, each row
    carrying its own ``TIMESTAMP``. We fetch that one file and split it by
    ``TIMESTAMP`` into per-date snapshots — replacing the previous approach that
    enumerated GitHub commit history and downloaded one CSV per commit at
    runtime. Returns an empty list when no history is available (callers already
    treat < 2 snapshots as "no trend data").
    """
    cfg = get_config("data_source")
    history_days = int(days or cfg.get("history_days", 90))

    frame = _fetch_history_frame(cfg)
    if frame is None or frame.empty or TIMESTAMP_COL not in frame.columns:
        return []

    snapshots: list[Snapshot] = []
    for _, group in frame.groupby(TIMESTAMP_COL, sort=False):
        stamp = parse_snapshot_date(group[TIMESTAMP_COL].iloc[0])
        if stamp is None:
            continue
        snapshots.append(Snapshot(timestamp=stamp, df=group.reset_index(drop=True)))

    snapshots.sort(key=lambda snapshot: snapshot.timestamp)
    if history_days and snapshots:
        cutoff = snapshots[-1].timestamp - timedelta(days=history_days)
        snapshots = [snapshot for snapshot in snapshots if snapshot.timestamp >= cutoff]
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
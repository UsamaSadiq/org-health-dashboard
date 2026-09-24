"""Read the score files published by the build-scores workflow.

Every reader returns ``None`` (or scores locally) rather than raising, so a
missing, stale or incompatible file degrades to runtime scoring instead of an
error page. A file is only used when it was built from the same snapshot date
and the same ``scoring.yaml`` version the app is running with.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import requests

from dashboard.lib import fixtures
from dashboard.lib.config import get_config
from dashboard.lib.schema import REPO_COL, TIMESTAMP_COL
from dashboard.lib.scores_export import SCHEMA_VERSION, SCORE_PREFIX
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.trends import Snapshot

logger = logging.getLogger(__name__)


def current_config_version() -> str:
    return str(get_config("scoring").get("version", "unknown"))


def fetch_payload(url: str | None) -> dict[str, Any] | None:
    if not url or fixtures.is_active():
        return None
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001 - fall back to runtime scoring
        logger.warning("Pre-computed scores unavailable at %s: %s", url, exc)
        return None


def is_compatible(payload: dict[str, Any] | None, config_version: str) -> bool:
    if not payload:
        return False
    metadata = payload.get("metadata", {})
    return (
        metadata.get("schema_version") == SCHEMA_VERSION
        and metadata.get("config_version") == config_version
    )


def merge_scores(raw: pd.DataFrame, records: list[dict[str, Any]]) -> pd.DataFrame | None:
    if raw.empty or REPO_COL not in raw.columns or not records:
        return None
    scores = pd.DataFrame(records)
    if REPO_COL not in scores.columns or scores[REPO_COL].duplicated().any():
        return None
    if not set(raw[REPO_COL]).issubset(set(scores[REPO_COL])):
        return None

    indexed = scores.set_index(REPO_COL)
    score_columns = [col for col in indexed.columns if col.startswith(SCORE_PREFIX)]
    merged = raw.copy()
    for column in score_columns:
        merged[column] = raw[REPO_COL].map(indexed[column])
    return merged


def _snapshot_date(raw: pd.DataFrame) -> str | None:
    if raw.empty or TIMESTAMP_COL not in raw.columns:
        return None
    return str(raw[TIMESTAMP_COL].iloc[0])


def scored_snapshot(raw: pd.DataFrame, payload: dict[str, Any] | None) -> pd.DataFrame:
    if is_compatible(payload, current_config_version()):
        if payload["metadata"].get("snapshot_timestamp") == _snapshot_date(raw):
            merged = merge_scores(raw, payload.get("records", []))
            if merged is not None:
                return merged
    return calculate_scores(raw)


def scored_history(raw_history: list[Snapshot], payload: dict[str, Any] | None) -> list[Snapshot]:
    records_by_date: dict[str, list[dict[str, Any]]] = {}
    if is_compatible(payload, current_config_version()):
        records_by_date = {
            snapshot["timestamp"]: snapshot.get("records", [])
            for snapshot in payload.get("snapshots", [])
        }

    def score(snapshot: Snapshot) -> pd.DataFrame:
        merged = merge_scores(snapshot.df, records_by_date.get(snapshot.timestamp.isoformat(), []))
        return merged if merged is not None else calculate_scores(snapshot.df)

    return [Snapshot(timestamp=snapshot.timestamp, df=score(snapshot)) for snapshot in raw_history]

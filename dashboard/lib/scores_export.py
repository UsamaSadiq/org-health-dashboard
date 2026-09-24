"""Pre-computed score files, so readers never run scoring themselves.

The payloads carry only identity columns and the ``score_*`` columns that
``calculate_scores`` adds; the raw check columns stay in the upstream CSVs.
Serialised through ``DataFrame.to_json`` so missing values become ``null``:
``json.dumps`` would emit a bare ``NaN``, which browsers and DuckDB reject.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd

from dashboard.lib.schema import REPO_COL, TIMESTAMP_COL
from dashboard.lib.trends import Snapshot

SCHEMA_VERSION = 1
SCORE_PREFIX = "score_"
IDENTITY_COLUMNS = (REPO_COL, TIMESTAMP_COL)


def score_records(scored: pd.DataFrame) -> list[dict[str, Any]]:
    columns = [col for col in IDENTITY_COLUMNS if col in scored.columns]
    columns += [col for col in scored.columns if col.startswith(SCORE_PREFIX)]
    return json.loads(scored[columns].to_json(orient="records"))


def _config_version(scored: pd.DataFrame) -> str | None:
    column = f"{SCORE_PREFIX}config_version"
    if scored.empty or column not in scored.columns:
        return None
    return str(scored[column].iloc[0])


def _snapshot_timestamp(scored: pd.DataFrame) -> str | None:
    if scored.empty or TIMESTAMP_COL not in scored.columns:
        return None
    return str(scored[TIMESTAMP_COL].iloc[0])


def _metadata(scored: pd.DataFrame, *, generated_at: datetime, source_url: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "source_url": source_url,
        "snapshot_timestamp": _snapshot_timestamp(scored),
        "config_version": _config_version(scored),
    }


def build_snapshot_payload(
    scored: pd.DataFrame, *, generated_at: datetime, source_url: str
) -> dict[str, Any]:
    return {
        "metadata": _metadata(scored, generated_at=generated_at, source_url=source_url),
        "records": score_records(scored),
    }


def build_history_payload(
    scored_history: list[Snapshot], *, generated_at: datetime, source_url: str
) -> dict[str, Any]:
    latest = scored_history[-1].df if scored_history else pd.DataFrame()
    return {
        "metadata": _metadata(latest, generated_at=generated_at, source_url=source_url),
        "snapshots": [
            {"timestamp": snapshot.timestamp.isoformat(), "records": score_records(snapshot.df)}
            for snapshot in scored_history
        ],
    }


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from dashboard.lib.config import DASHBOARD_DIR, get_config
from dashboard.lib.schema import LAST_PUSH_COL, REPO_COL, TIMESTAMP_COL, soft_assert_columns
from dashboard.lib.trends import Snapshot, load_history as load_trend_history

logger = logging.getLogger(__name__)

DEFAULT_CSV_URL = (
    "https://raw.githubusercontent.com/openedx/wg-maintenance/main/dashboards/dashboard_main.csv"
)
CACHE_DIR = DASHBOARD_DIR.parent / ".cache" / "dashboard_data"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_file_path() -> Path:
    return CACHE_DIR / f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"


def _latest_cache_file() -> Path | None:
    files = sorted(CACHE_DIR.glob("snapshot_*.csv"))
    return files[-1] if files else None


def _validate_snapshot(df: pd.DataFrame, cfg: dict[str, Any]) -> tuple[bool, list[str]]:
    expected = [REPO_COL, TIMESTAMP_COL, LAST_PUSH_COL]
    missing = soft_assert_columns(df.columns, expected)
    is_empty = df.empty
    row_min = int(cfg.get("expected_min_rows", 1))
    col_min = int(cfg.get("expected_min_columns", 1))

    valid = (
        not is_empty
        and REPO_COL in df.columns
        and TIMESTAMP_COL in df.columns
        and len(df) >= row_min
        and len(df.columns) >= col_min
    )
    return valid, missing


def _fetch_snapshot_dataframe(cfg: dict[str, Any]) -> pd.DataFrame:
    csv_url = cfg.get("csv_url", DEFAULT_CSV_URL)
    response = requests.get(csv_url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(pd.io.common.StringIO(response.text))


def _save_cache(df: pd.DataFrame) -> None:
    df.to_csv(_cache_file_path(), index=False)


def _load_from_cache() -> pd.DataFrame:
    latest = _latest_cache_file()
    if latest is None:
        return pd.DataFrame()
    return pd.read_csv(latest)


def load_snapshot() -> pd.DataFrame:
    """Fetch current snapshot with schema checks and fallback to last-known-good."""
    cfg = get_config("data_source")
    fallback_enabled = bool(cfg.get("fallback_to_last_known_good", True))
    try:
        df = _fetch_snapshot_dataframe(cfg)
        valid, missing = _validate_snapshot(df, cfg)
        if not valid:
            logger.warning(
                "Snapshot failed integrity checks (rows=%s cols=%s missing=%s)",
                len(df),
                len(df.columns),
                missing,
            )
            if fallback_enabled:
                cached = _load_from_cache()
                if not cached.empty:
                    return cached
        _save_cache(df)
        return df
    except Exception as exc:  # noqa: BLE001 - resilience by design
        logger.warning("CSV fetch failed, attempting cached snapshot: %s", exc)
        if fallback_enabled:
            cached = _load_from_cache()
            if not cached.empty:
                return cached
    return pd.DataFrame()


def load_history(days: int | None = None) -> list[Snapshot]:
    """Load historical snapshots through the trends module."""
    return load_trend_history(days=days)


def load_my_repos(handle: str) -> pd.DataFrame:
    """Filter snapshot by ownership columns for a GitHub handle."""
    df = load_snapshot()
    if df.empty:
        return df

    handle_value = _normalize_handle(handle)
    if not handle_value:
        return pd.DataFrame()

    mask = pd.Series(False, index=df.index)

    if REPO_COL in df.columns:
        owner_series = df[REPO_COL].astype(str).str.split("/", n=1).str[0]
        mask = mask | owner_series.map(lambda value: _normalize_handle(value) == handle_value)

    owner_cols = [
        "owner",
        "maintainers",
        "ownership.owner",
        "ownership.owner_name",
        "ownership.squad",
        "ownership.theme",
    ]
    for col in owner_cols:
        if col in df.columns:
            mask = mask | df[col].map(lambda value: _value_matches_handle(value, handle_value))

    return df[mask]


def _normalize_handle(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized.lstrip("@")


def _value_matches_handle(value: object, handle: str) -> bool:
    if not handle:
        return False
    text = _normalize_handle(value)
    if not text:
        return False
    if text == handle:
        return True

    tokens = [token.lstrip("@") for token in re.split(r"[^a-zA-Z0-9_.-]+", text) if token]
    return handle in tokens


def load_config(name: str) -> dict[str, Any]:
    """Load configuration by section name."""
    return get_config(name)


def export_json_payload(
    df: pd.DataFrame,
    metadata: dict[str, Any],
) -> str:
    """Create JSON export with metadata and records."""
    payload = {
        "metadata": metadata,
        "records": df.to_dict(orient="records"),
    }
    return json.dumps(payload, ensure_ascii=False)

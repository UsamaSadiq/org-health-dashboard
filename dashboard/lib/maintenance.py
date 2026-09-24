"""Read the files published by the collect-maintenance workflow.

Same contract as ``precomputed.py``: one static-file GET per file (or the pinned
fixture directory), ``None`` on any problem so the page can show an empty state
instead of failing.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from dashboard.lib import fixtures
from dashboard.lib.config import get_config

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
UPGRADE_JOBS = "upgrade_jobs.json"
REDUNDANT_PRS = "redundant_prs.json"
FIXTURE_SUBDIR = "maintenance"


def wave_file(wave_id: str) -> str:
    return f"waves/{wave_id}.json"


def _valid(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and (payload.get("metadata") or {}).get("schema_version") == SCHEMA_VERSION
        and isinstance(payload.get("records"), list)
    )


def load(relative_path: str) -> dict[str, Any] | None:
    directory = fixtures.fixture_dir()
    try:
        if directory is not None:
            payload = json.loads((directory / FIXTURE_SUBDIR / relative_path).read_text(encoding="utf-8"))
        else:
            base = get_config("data_source").get("maintenance_base_url")
            if not base:
                return None
            response = requests.get(f"{base.rstrip('/')}/{relative_path}", timeout=30)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 - the page shows an empty state instead
        logger.warning("Maintenance file %s unavailable: %s", relative_path, exc)
        return None
    return payload if _valid(payload) else None

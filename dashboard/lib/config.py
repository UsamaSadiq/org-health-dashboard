from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

import yaml

from dashboard.lib.schema import validate_config_data

logger = logging.getLogger(__name__)

LIB_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = LIB_DIR.parent
CONFIG_DIR = DASHBOARD_DIR / "config"
ORG_CONFIG_DIR = CONFIG_DIR / "openedx"


def read_config_file(path: str | Path) -> dict:
    """Read and parse a YAML config file from dashboard/config."""
    raw_path = Path(path)
    config_path = raw_path if raw_path.is_absolute() else DASHBOARD_DIR / raw_path

    try:
        with config_path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}
    except Exception as exc:  # noqa: BLE001 - deliberate resilience
        logger.warning("Failed to read config at %s: %s", config_path, exc)
        return {}


@lru_cache(maxsize=32)
def get_config(section: str, org: str = "openedx") -> dict:
    """Get configuration by section name from org config directory."""
    path = CONFIG_DIR / org / f"{section}.yaml"
    if path.exists():
        payload = read_config_file(path)
        validate_config_data(section, payload, strict=False)
        return payload
    return {}


@lru_cache(maxsize=1)
def get_feature_flags() -> dict:
    """Load feature flags from root config file.

    When the environment variable DASHBOARD_ENABLE_ALL_FEATURES is set to
    "true" (case-insensitive), every known flag is forced to True regardless
    of the YAML values. Intended for local development and per-client
    feature previews.
    """
    root_flags = CONFIG_DIR / "feature_flags.yaml"
    payload = read_config_file(root_flags) if root_flags.exists() else {}
    validate_config_data("feature_flags", payload, strict=False)

    if os.environ.get("DASHBOARD_ENABLE_ALL_FEATURES", "").strip().lower() == "true":
        payload = {key: True for key in payload}

    return payload

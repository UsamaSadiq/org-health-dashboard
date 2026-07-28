import streamlit as st
import pandas as pd
from typing import Any
from dashboard.lib.trends import Snapshot
from dashboard.lib.data import (
    export_json_payload,
    load_config,
    load_history as _load_history,
    load_my_repos as _load_my_repos,
    load_snapshot as _load_snapshot,
)
from dashboard.lib.tiers import annotate_tiers

@st.cache_data(ttl=300)
def load_snapshot() -> pd.DataFrame:
    """Fetch current snapshot with schema checks and fallback to last-known-good (cached).

    Tier annotation happens here, once, rather than in each consumer: the
    sidebar's Tier filter reads a ``repo_tier`` column that the upstream CSV does
    not provide, so without this the control silently matched nothing.
    """
    return annotate_tiers(_load_snapshot())

@st.cache_data(ttl=86400)
def load_history(days: int | None = None) -> list[Snapshot]:
    """Load historical snapshots from the pre-computed history file (cached)."""
    return _load_history(days=days)

def load_my_repos(handle: str) -> pd.DataFrame:
    """Filter snapshot by ownership columns for a GitHub handle."""
    return _load_my_repos(handle)

__all__ = [
    "export_json_payload",
    "load_config",
    "load_history",
    "load_my_repos",
    "load_snapshot",
]

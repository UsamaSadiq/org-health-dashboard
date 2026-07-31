"""Cached data access for the Streamlit layer.

Everything a page needs should come from here, already scored. The pattern this
replaces was ``calculate_scores(load_snapshot())`` written out in each of the
seven pages, which meant:

- **Scoring ran uncached on every interaction.** ``calculate_scores`` iterates
  rows in Python over a 171 x 111 frame, so it was repeated on every keystroke in
  a search box and every tab switch.
- **Overview loaded history three times per render.** ``_baseline_frame``,
  ``_top_movers`` and ``kpi._load_org_avg_history`` each fetched it and re-scored
  independently; the third re-scored *every* snapshot in the window.

The scored variants below are the supported entry points. ``load_snapshot`` and
``load_history`` remain for the few callers that genuinely want raw frames (the
Checks Catalog counts columns; healthz only reads a timestamp).

Cache TTLs are deliberately aligned. The snapshot was 300s while history was
86400s, so for up to a day after a pipeline run the KPI tiles and their deltas
disagreed about which snapshot was current.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.lib.data import (
    export_json_payload,
    has_ownership_data,
    load_config,
    load_history as _load_history,
    load_my_repos as _load_my_repos,
    load_snapshot as _load_snapshot,
)
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.tiers import annotate_tiers
from dashboard.lib.trends import Snapshot

# One TTL for both the snapshot and the history that is compared against it.
CACHE_TTL_SECONDS = 300


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_snapshot() -> pd.DataFrame:
    """Current snapshot, tier-annotated but unscored.

    Tier annotation happens here, once, rather than in each consumer: the
    sidebar's Tier filter reads a ``repo_tier`` column that the upstream CSV does
    not provide, so without this the control silently matched nothing.
    """
    return annotate_tiers(_load_snapshot())


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Scoring repositories…")
def load_scored_snapshot() -> pd.DataFrame:
    """Current snapshot, tier-annotated and scored. Prefer this in pages.

    The spinner is deliberate: on a cold cache this pays for a CSV fetch plus a
    full scoring pass, and the previous silence made that read as a hung page.
    """
    return calculate_scores(load_snapshot())


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_history(days: int | None = None) -> list[Snapshot]:
    """Historical snapshots from the pre-computed history file, unscored."""
    return _load_history(days=days)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading history…")
def load_scored_history(days: int | None = None) -> list[Snapshot]:
    """Historical snapshots with scores applied, computed once per window.

    Returns new ``Snapshot`` objects rather than mutating the cached raw ones —
    ``st.cache_data`` hands out references, and scoring them in place would
    corrupt the unscored cache entry for every other caller.
    """
    return [
        Snapshot(timestamp=snapshot.timestamp, df=calculate_scores(snapshot.df))
        for snapshot in load_history(days=days)
    ]


def load_my_repos(handle: str) -> pd.DataFrame:
    """Filter snapshot by ownership columns for a GitHub handle."""
    return _load_my_repos(handle)


__all__ = [
    "CACHE_TTL_SECONDS",
    "export_json_payload",
    "has_ownership_data",
    "load_config",
    "load_history",
    "load_my_repos",
    "load_scored_history",
    "load_scored_snapshot",
    "load_snapshot",
]

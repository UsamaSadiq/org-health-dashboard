"""Repository tier classification, applied once per snapshot.

``FilterState.apply`` has always filtered on a ``repo_tier`` column, but nothing
ever created one and the upstream CSV does not carry it (checked: 111 columns, no
``repo_tier``). So the sidebar's Tier control was a no-op — selecting
``critical`` returned all 171 repositories, silently. The only tier logic in the
codebase lived as a private helper inside ``pages/04_needing_attention.py``,
where it was recomputed per row and invisible to every other page.

This module is the single source of that classification, so the filter, the
attention rules, and any future grouping all agree.

**Matching.** ``tiers.yaml`` entries may be written either fully qualified
(``openedx/edx-platform``) or bare (``edx-platform``). Both forms match, because
the config is hand-maintained and requiring the org prefix would be a silent
foot-gun. Order matters: ``critical`` wins over ``important`` over ``standard``,
so a repository listed twice gets its most severe tier.

**Coverage caveat.** ``tiers.yaml`` currently classifies 4 of 171 repositories,
so almost everything falls through to ``standard`` and any tier-scoped rule is
effectively inert. :func:`tier_counts` exists so the UI can show that rather than
implying a curated classification exists.
"""
from __future__ import annotations

import pandas as pd

from dashboard.lib.config import get_config
from dashboard.lib.schema import REPO_COL

TIER_COL = "repo_tier"

# Most severe first: the first match wins.
TIER_ORDER = ["critical", "important", "standard"]

DEFAULT_TIER = "standard"


def _lookup(tiers_config: dict) -> dict[str, str]:
    """Flatten the config into {name -> tier}, keeping the most severe match.

    Both the fully-qualified and bare forms of each entry are registered, so a
    later lookup is a dict hit rather than a scan over every configured name for
    every row.
    """
    mapping: dict[str, str] = {}
    for tier in TIER_ORDER:
        for entry in tiers_config.get(tier) or []:
            name = str(entry).strip()
            if not name:
                continue
            for key in {name, name.split("/")[-1]}:
                # setdefault, so a name listed in two tiers keeps the first
                # (most severe) one.
                mapping.setdefault(key, tier)
    return mapping


def repo_tier(repo: str, tiers_config: dict | None = None) -> str:
    """Tier for a single repository name. Unlisted repositories are standard."""
    mapping = _lookup(tiers_config if tiers_config is not None else get_config("tiers"))
    name = str(repo).strip()
    return mapping.get(name) or mapping.get(name.split("/")[-1]) or DEFAULT_TIER


def annotate_tiers(df: pd.DataFrame, tiers_config: dict | None = None) -> pd.DataFrame:
    """Return ``df`` with a ``repo_tier`` column added.

    Called from the cached snapshot loader so every page sees the column and the
    sidebar filter has something real to filter on. Returns the frame unchanged
    when it is empty or has no repository column, rather than raising — a missing
    snapshot is already handled by each page's empty state.
    """
    if df.empty or REPO_COL not in df.columns:
        return df

    mapping = _lookup(tiers_config if tiers_config is not None else get_config("tiers"))
    if not mapping:
        # No configuration at all: still add the column so downstream filtering
        # and grouping work without special-casing its absence.
        out = df.copy()
        out[TIER_COL] = DEFAULT_TIER
        return out

    def _classify(value: object) -> str:
        name = str(value).strip()
        return mapping.get(name) or mapping.get(name.split("/")[-1]) or DEFAULT_TIER

    out = df.copy()
    out[TIER_COL] = out[REPO_COL].map(_classify)
    return out


def tier_counts(df: pd.DataFrame) -> dict[str, int]:
    """Repositories per tier, in severity order, including empty tiers.

    Empty tiers are kept so the UI can show ``critical (0)`` — an absent option
    reads as "no such thing", whereas a zero reads as "nothing classified yet",
    which is the actual state of ``tiers.yaml``.
    """
    if df.empty or TIER_COL not in df.columns:
        return {tier: 0 for tier in TIER_ORDER}
    counts = df[TIER_COL].value_counts()
    return {tier: int(counts.get(tier, 0)) for tier in TIER_ORDER}

"""Guards for WP-3: the Tier filter must actually filter.

``FilterState.apply`` filtered on a ``repo_tier`` column that nothing created and
that the upstream CSV does not contain, so the sidebar's Tier control silently
returned every repository. A no-op control is worse than a missing one: it makes
the user believe they have narrowed the view.
"""
from __future__ import annotations

import pandas as pd

from dashboard.lib.tiers import (
    DEFAULT_TIER,
    TIER_COL,
    TIER_ORDER,
    annotate_tiers,
    repo_tier,
    tier_counts,
)
from dashboard.ui.filters import FilterState

CONFIG = {
    "critical": ["openedx/edx-platform", "xblock"],
    "important": ["openedx/edx-notes-api"],
    "standard": [],
}


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "repo_name": [
                "openedx/edx-platform",
                "openedx/xblock",
                "openedx/edx-notes-api",
                "openedx/something-else",
            ]
        }
    )


def test_fully_qualified_and_bare_config_entries_both_match() -> None:
    """tiers.yaml is hand-maintained and mixes both forms."""
    assert repo_tier("openedx/edx-platform", CONFIG) == "critical"
    # "xblock" is configured bare but appears fully qualified in the snapshot.
    assert repo_tier("openedx/xblock", CONFIG) == "critical"
    assert repo_tier("openedx/edx-notes-api", CONFIG) == "important"


def test_unlisted_repositories_fall_back_to_standard() -> None:
    assert repo_tier("openedx/never-heard-of-it", CONFIG) == DEFAULT_TIER


def test_most_severe_tier_wins_when_a_repo_is_listed_twice() -> None:
    duplicated = {"critical": ["openedx/a"], "important": ["openedx/a"], "standard": ["openedx/a"]}
    assert repo_tier("openedx/a", duplicated) == "critical"


def test_annotate_tiers_adds_the_column_every_page_relies_on() -> None:
    out = annotate_tiers(_frame(), CONFIG)
    assert TIER_COL in out.columns
    assert list(out[TIER_COL]) == ["critical", "critical", "important", DEFAULT_TIER]


def test_annotate_tiers_adds_the_column_even_with_no_config() -> None:
    """Downstream filtering must not need to special-case a missing column."""
    out = annotate_tiers(_frame(), {})
    assert TIER_COL in out.columns
    assert set(out[TIER_COL]) == {DEFAULT_TIER}


def test_annotate_tiers_tolerates_an_empty_snapshot() -> None:
    empty = pd.DataFrame()
    assert annotate_tiers(empty, CONFIG).empty
    # A frame with no repo column is returned untouched rather than raising.
    other = pd.DataFrame({"unrelated": [1, 2]})
    assert TIER_COL not in annotate_tiers(other, CONFIG).columns


def test_tier_filter_actually_narrows_the_frame() -> None:
    """The regression itself: this returned all rows before annotate_tiers existed."""
    annotated = annotate_tiers(_frame(), CONFIG)

    every = FilterState(search="", include_archived=True, tier="all").apply(annotated)
    critical = FilterState(search="", include_archived=True, tier="critical").apply(annotated)

    assert len(every) == 4
    assert len(critical) == 2
    assert len(critical) < len(every)
    assert set(critical["repo_name"]) == {"openedx/edx-platform", "openedx/xblock"}


def test_tier_counts_reports_zero_tiers_rather_than_omitting_them() -> None:
    """"critical (0)" is honest; a missing option implies no such tier exists."""
    counts = tier_counts(annotate_tiers(_frame(), CONFIG))
    assert counts == {"critical": 2, "important": 1, "standard": 1}
    assert list(counts) == TIER_ORDER

    # Unannotated frames report zeros instead of raising.
    assert tier_counts(pd.DataFrame()) == {tier: 0 for tier in TIER_ORDER}


def test_repo_tier_column_is_not_mistaken_for_a_check_column() -> None:
    """Pages detect check columns by the presence of a dot in the name.

    ``repo_tier`` has none, so adding it to every snapshot cannot leak into the
    failing-checks tables, the catalog, or the per-category grouping.
    """
    assert "." not in TIER_COL

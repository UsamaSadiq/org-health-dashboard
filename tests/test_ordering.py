"""Ties must resolve identically everywhere, or rankings are not rankings."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.lib.ordering import bottom, rank, top

# Four repos on two distinct scores: every ordering question here is a tie.
TIED = pd.DataFrame(
    {
        "repo_name": ["openedx/zebra", "openedx/alpha", "openedx/mike", "openedx/beta"],
        "score_composite": [93.3, 93.3, 50.0, 93.3],
    }
)


def test_ties_break_alphabetically_on_repo_name():
    result = rank(TIED, "score_composite", ascending=False)

    assert list(result["repo_name"]) == [
        "openedx/alpha",
        "openedx/beta",
        "openedx/zebra",
        "openedx/mike",
    ]


def test_order_is_independent_of_input_order():
    """The defect this module exists for.

    Two machines built the same frame in different row orders and pandas'
    unstable sort surfaced a different "Top 5" on each.
    """
    shuffled = TIED.iloc[[2, 0, 3, 1]].reset_index(drop=True)

    assert list(rank(TIED, "score_composite", ascending=False)["repo_name"]) == list(
        rank(shuffled, "score_composite", ascending=False)["repo_name"]
    )


def test_top_is_deterministic_where_nlargest_was_not():
    shuffled = TIED.iloc[::-1].reset_index(drop=True)

    assert list(top(TIED, "score_composite", 2)["repo_name"]) == ["openedx/alpha", "openedx/beta"]
    assert list(top(shuffled, "score_composite", 2)["repo_name"]) == [
        "openedx/alpha",
        "openedx/beta",
    ]


def test_bottom_returns_worst_first():
    result = bottom(TIED, "score_composite", 2)

    assert list(result["repo_name"]) == ["openedx/mike", "openedx/alpha"]
    assert list(result["score_composite"]) == [50.0, 93.3]


def test_tiebreak_direction_does_not_flip_with_the_primary_key():
    """Ascending and descending must select the same rows at a tie boundary.

    If the tiebreak flipped with the primary key, "the bottom 3 reversed" would
    quietly be a different set of repos from "the top 3".
    """
    ascending = rank(TIED, "score_composite", ascending=True)
    descending = rank(TIED, "score_composite", ascending=False)

    assert list(ascending["repo_name"]) == ["openedx/mike", "openedx/alpha", "openedx/beta", "openedx/zebra"]
    assert list(descending["repo_name"]) == ["openedx/alpha", "openedx/beta", "openedx/zebra", "openedx/mike"]


def test_multi_column_sort_appends_the_tiebreak_last():
    frame = pd.DataFrame(
        {
            "repo_name": ["openedx/c", "openedx/a", "openedx/b"],
            "tier": ["critical", "critical", "important"],
            "score_composite": [40.0, 40.0, 10.0],
        }
    )

    result = rank(frame, ["tier", "score_composite"], ascending=[True, True])

    assert list(result["repo_name"]) == ["openedx/a", "openedx/c", "openedx/b"]


def test_explicit_tiebreak_column_is_honoured():
    frame = pd.DataFrame({"check": ["b.check", "a.check"], "failing": [7, 7]})

    assert list(top(frame, "failing", 2, tiebreak="check")["check"]) == ["a.check", "b.check"]


def test_missing_tiebreak_column_raises_rather_than_sorting_partially():
    """Silently skipping an absent tiebreak gives back the non-total order the
    module exists to prevent, and the caller cannot tell. Failing Checks shipped
    exactly that: no repo_name in the frame, so its checks ranked by CSV column
    order while Overview ranked the same checks alphabetically."""
    frame = pd.DataFrame({"value": [3, 1, 2]})

    with pytest.raises(KeyError, match="repo_name"):
        rank(frame, "value")


def test_tiebreak_none_is_the_explicit_opt_out():
    frame = pd.DataFrame({"value": [3, 1, 2]})

    assert list(rank(frame, "value", tiebreak=None)["value"]) == [1, 2, 3]


def test_bottom_and_a_reversed_top_select_the_same_repos_at_a_tie_boundary():
    """The Overview defect: reversing a descending rank also reverses its
    tiebreak, so a tie straddling the cut selects the alphabetically last of the
    tied repos instead of the first."""
    frame = pd.DataFrame(
        {
            "repo_name": [f"openedx/{c}" for c in "abcdef"],
            "score_composite": [1.0, 2.0, 3.0, 3.0, 3.0, 3.0],
        }
    )

    naive = list(rank(frame, "score_composite", ascending=False).tail(3)["repo_name"][::-1])
    correct = list(bottom(frame, "score_composite", 3)["repo_name"])

    assert correct == ["openedx/a", "openedx/b", "openedx/c"]
    assert naive == ["openedx/a", "openedx/b", "openedx/f"]
    assert naive != correct


def test_empty_frame_passes_through():
    empty = pd.DataFrame({"repo_name": [], "score_composite": []})

    assert rank(empty, "score_composite").empty
    assert top(empty, "score_composite", 5).empty


def test_index_is_reset_so_position_carries_no_stale_meaning():
    result = rank(TIED, "score_composite", ascending=False)

    assert list(result.index) == [0, 1, 2, 3]

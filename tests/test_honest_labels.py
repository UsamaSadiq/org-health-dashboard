"""Guards for WP-6: labels must describe what the data actually is.

Each of these was a case of the UI asserting something the underlying data did
not support: a "30d" caption over whatever history happened to exist, "losers"
that were really the smallest gains, a weekly bulletin carrying a dev placeholder,
and a top-level nav section for a page with nothing in it.
"""
from __future__ import annotations

import pandas as pd

from dashboard.lib.bulletin import generate_weekly_bulletin
from dashboard.lib.data import has_ownership_data

EMPTY = pd.DataFrame()


def test_bulletin_omits_the_commit_line_for_a_local_run() -> None:
    """GITHUB_SHA is unset locally, so "Commit: local" was reaching Slack."""
    for placeholder in ("local", "LOCAL", " unknown ", "none"):
        body = generate_weekly_bulletin(EMPTY, EMPTY, "https://example.test", placeholder)
        assert "Commit:" not in body, f"placeholder {placeholder!r} leaked into the bulletin"


def test_bulletin_keeps_the_commit_line_for_a_real_build() -> None:
    body = generate_weekly_bulletin(EMPTY, EMPTY, "https://example.test", "a1b2c3d")
    assert "Commit: a1b2c3d" in body


def test_bulletin_still_names_the_dashboard() -> None:
    """Dropping provenance must not drop attribution."""
    body = generate_weekly_bulletin(EMPTY, EMPTY, "https://example.test", "local")
    assert "https://example.test" in body
    assert "Open edX Repository Health Dashboard" in body


def test_ownership_section_is_hidden_when_no_repo_carries_ownership_data() -> None:
    """The live snapshot has no owner columns, so the section was always empty.

    Its own page body read "No owner data found", which is a worse first
    impression than the section not being there.
    """
    assert has_ownership_data(EMPTY) is False
    # Columns absent entirely: the live case.
    assert has_ownership_data(pd.DataFrame({"repo_name": ["a"]})) is False
    # Present but blank, which is also the live case for theme/squad/priority.
    assert has_ownership_data(pd.DataFrame({"ownership.theme": ["", "   ", None]})) is False


def test_ownership_section_appears_as_soon_as_any_field_is_populated() -> None:
    """Gating on data must not become gating it off permanently."""
    for column in ("ownership.owner", "ownership.owner_name", "ownership.squad"):
        assert has_ownership_data(pd.DataFrame({column: ["axim"]})) is True, column


def test_losers_are_declines_not_the_smallest_gains() -> None:
    """The A6 bug: sort descending then tail() mislabels gains as losses.

    Reproduced against the same selection logic the page uses, since the page
    computes movers from history that is not available in a unit test.
    """
    movers = pd.DataFrame(
        {
            "repo_name": ["a", "b", "c", "d"],
            # Everything improved, by varying amounts.
            "delta": [40.0, 30.0, 20.0, 5.0],
        }
    )

    old_losers = movers.sort_values("delta", ascending=False).tail(2)
    assert (old_losers["delta"] > 0).all(), "fixture should reproduce the old bug"

    gainers = movers[movers["delta"] > 0].nlargest(5, "delta")
    losers = movers[movers["delta"] < 0].nsmallest(5, "delta")

    assert len(gainers) == 4
    assert losers.empty, "no repository declined, so the losers list must be empty"


def test_losers_are_ordered_worst_first_when_declines_exist() -> None:
    movers = pd.DataFrame(
        {"repo_name": ["a", "b", "c"], "delta": [10.0, -5.0, -18.0]}
    )
    losers = movers[movers["delta"] < 0].nsmallest(5, "delta")
    assert list(losers["repo_name"]) == ["c", "b"]
    assert list(losers["delta"]) == [-18.0, -5.0]

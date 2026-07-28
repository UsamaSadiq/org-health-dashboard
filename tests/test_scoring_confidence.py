"""Guards for WP-4: a fallback 50 must be distinguishable from a real 50.

``default_when_missing`` is 50 for every metric in ``scoring.yaml``. Before this
metadata existed, a metric backed by no data at all produced exactly the same
output as one that genuinely scored 50, and nothing downstream could tell them
apart. That is how the org gauge came to present "70.3 / Grade B" off a snapshot
where four of nine metrics have no column at all.

This module pins the three-way distinction (measured / defaulted / unavailable)
and, just as importantly, that adding it did not move a single grade.
"""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.lib.scoring import (
    CONFIDENCE_DEFAULTED,
    CONFIDENCE_MEASURED,
    CONFIDENCE_UNAVAILABLE,
    calculate_scores,
)

# github.last_push backs commit_recency, the one metric that is both computable
# and present in every snapshot, so it is the cheapest way to exercise all three
# confidence states.
PUSH_COL = "github.last_push"


def _frame(push_value: object) -> pd.DataFrame:
    return pd.DataFrame({"repo_name": ["openedx/example"], PUSH_COL: [push_value]})


def test_a_real_value_is_measured() -> None:
    scored = calculate_scores(_frame("2026-07-20 10:00:00"), as_of=pd.Timestamp("2026-07-21"))
    row = scored.iloc[0]
    assert row["score_metric_confidence"]["commit_recency"] == CONFIDENCE_MEASURED
    assert "commit_recency" not in row["score_defaulted_metrics"]


def test_a_present_but_blank_value_is_defaulted_not_measured() -> None:
    """The distinction that did not exist before.

    The column is in the snapshot, so the metric is *not* "unavailable"; but its
    value is unusable, so its 50 is a fallback rather than a measurement.
    """
    scored = calculate_scores(_frame(None))
    row = scored.iloc[0]

    assert row["score_metric_confidence"]["commit_recency"] == CONFIDENCE_DEFAULTED
    assert "commit_recency" in row["score_defaulted_metrics"]
    # Crucially: not conflated with the column being absent.
    assert "commit_recency" not in row["score_unavailable_metrics"]


def test_an_unparseable_value_is_also_defaulted() -> None:
    scored = calculate_scores(_frame("not-a-date"))
    row = scored.iloc[0]
    assert row["score_metric_confidence"]["commit_recency"] == CONFIDENCE_DEFAULTED


def test_an_absent_column_is_unavailable_not_defaulted() -> None:
    """No column means excluded from the average, not scored at 50."""
    scored = calculate_scores(pd.DataFrame({"repo_name": ["openedx/example"]}))
    row = scored.iloc[0]

    assert row["score_metric_confidence"]["commit_recency"] == CONFIDENCE_UNAVAILABLE
    assert "commit_recency" in row["score_unavailable_metrics"]
    assert "commit_recency" not in row["score_defaulted_metrics"]


def test_every_configured_metric_gets_a_confidence_verdict() -> None:
    """No metric may be silently absent from the confidence map."""
    scored = calculate_scores(_frame("2026-07-20 10:00:00"))
    row = scored.iloc[0]

    confidence = row["score_metric_confidence"]
    accounted = (
        set(row["score_per_metric"]) | set(row["score_unavailable_metrics"])
    )
    assert set(confidence) == accounted
    assert set(confidence.values()) <= {
        CONFIDENCE_MEASURED,
        CONFIDENCE_DEFAULTED,
        CONFIDENCE_UNAVAILABLE,
    }


def test_measured_weight_is_never_above_coverage() -> None:
    """coverage counts present columns; measured_weight counts usable values.

    A blank value in a present column lowers the second but not the first, which
    is exactly the flattery this WP removes.
    """
    blank = calculate_scores(_frame(None)).iloc[0]
    assert blank["score_measured_weight"] <= blank["score_coverage"]
    assert blank["score_measured_weight"] < blank["score_coverage"], (
        "a blank value should reduce measured_weight below coverage"
    )


def test_category_measured_weight_exposes_a_confident_but_unmeasured_subscore() -> None:
    """The B3 case, in numbers.

    On the live snapshot, Activity renders a hard 100.0 while only ~23% of its
    weight is measured, because four of its five metrics have no column. The UI
    needs that fraction to mark the tile.
    """
    scored = calculate_scores(_frame("2026-07-20 10:00:00"))
    row = scored.iloc[0]

    fractions = row["score_category_measured_weight"]
    assert "activity" in fractions
    assert 0.0 < fractions["activity"] < 1.0
    # A category that is fully measured must report 1.0, not something rounded off.
    assert all(0.0 <= value <= 1.0 for value in fractions.values())


@pytest.mark.parametrize(
    "push_value,expected_confidence",
    [
        ("2026-07-20 10:00:00", CONFIDENCE_MEASURED),
        (None, CONFIDENCE_DEFAULTED),
        ("", CONFIDENCE_DEFAULTED),
    ],
)
def test_confidence_round_trip(push_value: object, expected_confidence: str) -> None:
    scored = calculate_scores(_frame(push_value))
    assert scored.iloc[0]["score_metric_confidence"]["commit_recency"] == expected_confidence


def test_adding_confidence_metadata_did_not_move_any_score() -> None:
    """This WP is additive. A changed grade would be a silent regression.

    Boolean handlers are the risk: an unrecognised token now reports as
    defaulted, and it would have been easy to also change its *score* while
    touching that branch.
    """
    frame = pd.DataFrame(
        {
            "repo_name": ["a", "b", "c"],
            PUSH_COL: ["2026-07-20 10:00:00", None, "2020-01-01 00:00:00"],
            # An unrecognised boolean token: defaulted, but still scored 50.
            "github_actions": ["true", "maybe", "false"],
        }
    )
    scored = calculate_scores(frame, as_of=pd.Timestamp("2026-07-21"))

    row = scored.iloc[1]
    assert row["score_metric_confidence"]["ci_status"] == CONFIDENCE_DEFAULTED
    assert row["score_per_metric"]["ci_status"] == 50.0

    # Explicit false is a measured zero, not a default.
    last = scored.iloc[2]
    assert last["score_metric_confidence"]["ci_status"] == CONFIDENCE_MEASURED
    assert last["score_per_metric"]["ci_status"] == 0.0

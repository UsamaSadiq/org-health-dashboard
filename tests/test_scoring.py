from datetime import date

import pandas as pd

from dashboard.lib.scoring import calculate_scores


def _sample_frame(**overrides) -> pd.DataFrame:
    row = {
        "repo_name": "openedx/edx-platform",
        "TIMESTAMP": "2026-05-15",
        "github.last_push": "2026-05-15 00:00:00",
        "github_actions": True,
        "exists.openedx.yaml": True,
        "dependabot.exists": True,
        "renovate.configured": False,
        "readme.getting-help": True,
        "readme.security": True,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_calculate_scores_adds_expected_columns():
    scored = calculate_scores(_sample_frame())
    for col in (
        "score_composite",
        "score_letter",
        "score_per_metric",
        "score_per_metric_weight",
        "score_unavailable_metrics",
        "score_coverage",
    ):
        assert col in scored.columns
    assert scored.iloc[0]["score_letter"] in {"A", "B", "C", "D", "F"}
    coverage = scored.iloc[0]["score_coverage"]
    assert 0.0 < coverage <= 1.0


def test_commit_recency_uses_snapshot_date_not_wall_clock():
    """Re-scoring the same snapshot later must not drift the recency component."""
    df = _sample_frame()
    snapshot_when_fresh = calculate_scores(df, as_of=date(2026, 5, 16))
    snapshot_a_year_later = calculate_scores(df, as_of=date(2027, 5, 16))
    fresh = snapshot_when_fresh.iloc[0]["score_per_metric"]["commit_recency"]
    later = snapshot_a_year_later.iloc[0]["score_per_metric"]["commit_recency"]
    assert fresh > later, "commit_recency must degrade as reference time advances"

    df_with_timestamp = _sample_frame()
    scored_via_timestamp = calculate_scores(df_with_timestamp)
    assert (
        scored_via_timestamp.iloc[0]["score_per_metric"]["commit_recency"]
        == snapshot_when_fresh.iloc[0]["score_per_metric"]["commit_recency"]
    )


def test_structural_and_activity_subscores_emitted():
    scored = calculate_scores(_sample_frame())
    row = scored.iloc[0]
    # Sample data only populates structural metrics (commit_recency is activity);
    # both sub-scores should be present and floats in [0, 100].
    assert row["score_structural"] is not None
    assert row["score_activity"] is not None
    assert 0 <= row["score_structural"] <= 100
    assert 0 <= row["score_activity"] <= 100
    # Composite must lie within the convex hull of the two sub-scores
    # (since each is a weighted-average partition of the available set).
    lo = min(row["score_structural"], row["score_activity"])
    hi = max(row["score_structural"], row["score_activity"])
    assert lo - 0.01 <= row["score_composite"] <= hi + 0.01


def test_letter_grade_boundary_is_half_open():
    """A 79.5 score must land in B, not fall through to F."""
    from dashboard.lib.scoring import _get_letter_grade

    grades = {"A": [80, 100], "B": [60, 79], "C": [40, 59], "D": [20, 39], "F": [0, 19]}
    assert _get_letter_grade(79.5, grades) == "B"
    assert _get_letter_grade(80.0, grades) == "A"
    assert _get_letter_grade(0.0, grades) == "F"

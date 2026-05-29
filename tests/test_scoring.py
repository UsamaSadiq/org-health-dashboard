from datetime import date

import pandas as pd

from dashboard.lib.scoring import calculate_scores, pair_restricted_composite


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


def test_pair_restricted_composite_renormalizes_over_intersection():
    scored = calculate_scores(_sample_frame())
    row_a = scored.iloc[0]

    # Build a synthetic second row with a different available metric set.
    row_b = row_a.copy()
    row_b["score_per_metric"] = {"ci_status": 100.0, "openedx_yaml_compliance": 0.0}
    row_b["score_per_metric_weight"] = {"ci_status": 0.10, "openedx_yaml_compliance": 0.10}
    row_b["score_composite"] = 50.0

    result = pair_restricted_composite(row_a, row_b)
    assert set(result["metrics"]) <= set(row_a["score_per_metric"].keys()) & set(row_b["score_per_metric"].keys())
    assert 0 <= result["coverage"] <= 1.0
    assert 0 <= result["score_a"] <= 100
    assert 0 <= result["score_b"] <= 100


def test_letter_grade_boundary_is_half_open():
    """A 79.5 score must land in B, not fall through to F."""
    from dashboard.lib.scoring import _get_letter_grade

    grades = {"A": [80, 100], "B": [60, 79], "C": [40, 59], "D": [20, 39], "F": [0, 19]}
    assert _get_letter_grade(79.5, grades) == "B"
    assert _get_letter_grade(80.0, grades) == "A"
    assert _get_letter_grade(0.0, grades) == "F"

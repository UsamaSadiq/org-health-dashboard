"""The Scoring page's explanation is derived from scoring.yaml, never hardcoded."""
from __future__ import annotations

import pandas as pd
import pytest

from dashboard.lib import scoring_method
from dashboard.lib.config import get_config


@pytest.mark.parametrize(
    "cfg, expected",
    [
        (
            {"parse_rule": "threshold_days", "thresholds": [{"days": 30, "score": 80}, {"days": 7, "score": 100}]},
            "≤ 7 days → 100; ≤ 30 days → 80; older → 0",
        ),
        (
            {"parse_rule": "threshold_max_seconds", "thresholds": [{"max": 86400, "score": 100}, {"max": 259200, "score": 80}]},
            "≤ 1 day → 100; ≤ 3 days → 80; slower → 0",
        ),
        (
            {"parse_rule": "threshold_numeric", "thresholds": [{"min": 0, "score": 20}, {"min": 0.8, "score": 100}]},
            "≥ 0.8 → 100; ≥ 0 → 20",
        ),
        ({"parse_rule": "boolean"}, scoring_method.FIXED_RULES["boolean"]),
    ],
    ids=["days", "seconds", "numeric", "boolean"],
)
def test_rule_text(cfg, expected):
    assert scoring_method.rule_text(cfg) == expected


def test_letter_bands_are_ordered_best_first():
    config = {"letter_grades": {"F": [0, 19], "A": [80, 100], "C": [40, 59]}}

    bands = scoring_method.letter_bands(config)

    assert [band["grade"] for band in bands] == ["A", "C", "F"]
    assert bands[0] == {"grade": "A", "from": 80, "to": 100}


def test_metric_rows_follow_the_live_config():
    config = get_config("scoring")

    rows = scoring_method.metric_rows(config, pd.DataFrame())

    assert [row["metric"] for row in rows] == [name.replace("_", " ") for name in config["metrics"]]
    assert sum(row["weight_pct"] for row in rows) == pytest.approx(100.0, abs=0.5)


def test_weight_share_is_normalised():
    config = {"metrics": {"a": {"weight": 3}, "b": {"weight": 1}}}

    rows = scoring_method.metric_rows(config, pd.DataFrame())

    assert [row["weight_pct"] for row in rows] == [75.0, 25.0]


def test_measured_and_defaulted_shares_come_from_confidence():
    config = {"metrics": {"a": {"weight": 1}}}
    scored = pd.DataFrame(
        {
            "score_metric_confidence": [
                {"a": "measured"},
                {"a": "measured"},
                {"a": "defaulted"},
                {"a": "unavailable"},
            ]
        }
    )

    row = scoring_method.metric_rows(config, scored)[0]

    assert row["measured_pct"] == 50.0
    assert row["defaulted_pct"] == 25.0


def test_empty_snapshot_has_no_coverage_numbers():
    row = scoring_method.metric_rows({"metrics": {"a": {"weight": 1}}}, pd.DataFrame())[0]

    assert row["measured_pct"] is None
    assert row["defaulted_pct"] is None


def test_provisional_and_limitation_flags_are_carried():
    config = {"metrics": {"a": {"weight": 1, "provisional": True, "limitation": "note"}}}

    row = scoring_method.metric_rows(config, pd.DataFrame())[0]

    assert row["provisional"] is True
    assert row["limitation"] == "note"

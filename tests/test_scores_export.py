"""Pre-computed score files must match what the app computes at runtime."""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from dashboard.lib import scores_export
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.tiers import annotate_tiers
from dashboard.lib.trends import Snapshot

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "data"
GENERATED_AT = datetime(2026, 9, 24, tzinfo=timezone.utc)
SOURCE_URL = "https://example.test/dashboard_main.csv"


@pytest.fixture(scope="module")
def scored_fixture() -> pd.DataFrame:
    return calculate_scores(annotate_tiers(pd.read_csv(FIXTURE_DIR / "dashboard_main.csv")))


def test_records_round_trip_to_the_runtime_scores(scored_fixture):
    payload = scores_export.build_snapshot_payload(
        scored_fixture, generated_at=GENERATED_AT, source_url=SOURCE_URL
    )
    records = json.loads(scores_export.dumps(payload))["records"]

    assert len(records) == len(scored_fixture)
    for record, (_, row) in zip(records, scored_fixture.iterrows()):
        assert record["repo_name"] == row["repo_name"]
        assert record["score_letter"] == row["score_letter"]
        assert record["score_composite"] == pytest.approx(row["score_composite"])
        assert record["score_per_metric"] == pytest.approx(row["score_per_metric"])
        assert record["score_metric_confidence"] == row["score_metric_confidence"]


def test_records_carry_identity_and_score_columns_only(scored_fixture):
    record = scores_export.score_records(scored_fixture)[0]

    assert {"repo_name", "TIMESTAMP"} <= record.keys()
    assert all(key in {"repo_name", "TIMESTAMP"} or key.startswith("score_") for key in record)


def test_missing_values_serialise_as_null_not_nan():
    scored = pd.DataFrame(
        {"repo_name": ["a"], "TIMESTAMP": ["2026-09-23"], "score_structural": [math.nan]}
    )
    payload = scores_export.build_snapshot_payload(
        scored, generated_at=GENERATED_AT, source_url=SOURCE_URL
    )

    text = scores_export.dumps(payload)

    assert "NaN" not in text
    assert json.loads(text)["records"][0]["score_structural"] is None


def test_metadata_describes_the_snapshot(scored_fixture):
    metadata = scores_export.build_snapshot_payload(
        scored_fixture, generated_at=GENERATED_AT, source_url=SOURCE_URL
    )["metadata"]

    assert metadata == {
        "schema_version": scores_export.SCHEMA_VERSION,
        "generated_at": "2026-09-24T00:00:00+00:00",
        "source_url": SOURCE_URL,
        "snapshot_timestamp": str(scored_fixture["TIMESTAMP"].iloc[0]),
        "config_version": str(scored_fixture["score_config_version"].iloc[0]),
    }


def test_history_payload_keeps_snapshot_order(scored_fixture):
    history = [
        Snapshot(timestamp=date(2026, 9, 1), df=scored_fixture.head(2)),
        Snapshot(timestamp=date(2026, 9, 2), df=scored_fixture.head(3)),
    ]

    payload = scores_export.build_history_payload(
        history, generated_at=GENERATED_AT, source_url=SOURCE_URL
    )

    assert [snap["timestamp"] for snap in payload["snapshots"]] == ["2026-09-01", "2026-09-02"]
    assert [len(snap["records"]) for snap in payload["snapshots"]] == [2, 3]


def test_empty_history_has_no_snapshot_metadata():
    payload = scores_export.build_history_payload([], generated_at=GENERATED_AT, source_url=SOURCE_URL)

    assert payload["snapshots"] == []
    assert payload["metadata"]["snapshot_timestamp"] is None

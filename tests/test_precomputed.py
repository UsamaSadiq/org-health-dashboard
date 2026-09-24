"""Pre-computed scores are used only when they match; otherwise the app scores locally."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from dashboard.lib import precomputed, scores_export
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.tiers import annotate_tiers
from dashboard.lib.trends import Snapshot

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "data"
GENERATED_AT = datetime(2026, 9, 24, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return annotate_tiers(pd.read_csv(FIXTURE_DIR / "dashboard_main.csv"))


@pytest.fixture(scope="module")
def expected(raw) -> pd.DataFrame:
    return calculate_scores(raw)


def _payload(scored: pd.DataFrame) -> dict:
    payload = scores_export.build_snapshot_payload(scored, generated_at=GENERATED_AT, source_url="x")
    return json.loads(scores_export.dumps(payload))


def _poisoned(payload: dict) -> dict:
    """Same payload with every letter replaced, to tell merged output from local scoring."""
    records = [{**record, "score_letter": "Z"} for record in payload["records"]]
    return {**payload, "records": records}


def test_matching_file_reproduces_runtime_scoring(raw, expected):
    result = precomputed.scored_snapshot(raw, _payload(expected))

    pd.testing.assert_frame_equal(result, expected)


def test_matching_file_is_used_instead_of_scoring(raw, expected):
    result = precomputed.scored_snapshot(raw, _poisoned(_payload(expected)))

    assert set(result["score_letter"]) == {"Z"}


@pytest.mark.parametrize(
    "change",
    [
        {"config_version": "0.0"},
        {"snapshot_timestamp": "1999-01-01"},
        {"schema_version": 999},
    ],
    ids=["config-version", "snapshot-date", "schema-version"],
)
def test_mismatched_metadata_falls_back_to_local_scoring(raw, expected, change):
    payload = _poisoned(_payload(expected))
    payload["metadata"] = {**payload["metadata"], **change}

    result = precomputed.scored_snapshot(raw, payload)

    pd.testing.assert_frame_equal(result, expected)


def test_missing_file_falls_back_to_local_scoring(raw, expected):
    pd.testing.assert_frame_equal(precomputed.scored_snapshot(raw, None), expected)


def test_file_missing_a_repo_falls_back_to_local_scoring(raw, expected):
    payload = _poisoned(_payload(expected))
    payload["records"] = payload["records"][1:]

    pd.testing.assert_frame_equal(precomputed.scored_snapshot(raw, payload), expected)


def test_merge_does_not_mutate_the_raw_frame(raw, expected):
    before = raw.copy()

    precomputed.merge_scores(raw, _payload(expected)["records"])

    pd.testing.assert_frame_equal(raw, before)


def test_history_uses_matching_snapshots_and_scores_the_rest(raw, expected):
    first, second = raw.head(3), raw.head(4)
    history = [
        Snapshot(timestamp=pd.Timestamp("2026-09-01").date(), df=first),
        Snapshot(timestamp=pd.Timestamp("2026-09-02").date(), df=second),
    ]
    payload = scores_export.build_history_payload(
        [Snapshot(timestamp=history[0].timestamp, df=calculate_scores(first))],
        generated_at=GENERATED_AT,
        source_url="x",
    )
    payload = json.loads(scores_export.dumps(payload))
    payload["snapshots"][0]["records"] = [
        {**record, "score_letter": "Z"} for record in payload["snapshots"][0]["records"]
    ]

    result = precomputed.scored_history(history, payload)

    assert set(result[0].df["score_letter"]) == {"Z"}
    pd.testing.assert_frame_equal(result[1].df, calculate_scores(second))


def test_fixture_runs_never_fetch(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DATA_FIXTURE", str(FIXTURE_DIR))

    assert precomputed.fetch_payload("https://example.test/scores.json") is None

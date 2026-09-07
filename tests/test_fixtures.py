"""The pinned-data contract, and the checked-in fixture itself."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dashboard.lib import fixtures

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "data"


def test_unset_env_means_live_fetching(monkeypatch):
    monkeypatch.delenv(fixtures.FIXTURE_DIR_ENV, raising=False)

    assert not fixtures.is_active()
    assert fixtures.fixture_dir() is None
    assert fixtures.snapshot_path() is None
    assert fixtures.history_path() is None


def test_configured_directory_resolves_both_files(monkeypatch):
    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(FIXTURE_DIR))

    assert fixtures.is_active()
    assert fixtures.snapshot_path() == FIXTURE_DIR / "dashboard_main.csv"
    assert fixtures.history_path() == FIXTURE_DIR / "dashboard_history.csv"


def test_directory_that_does_not_exist_raises(monkeypatch, tmp_path):
    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(tmp_path / "nope"))

    with pytest.raises(ValueError, match=fixtures.FIXTURE_DIR_ENV):
        fixtures.fixture_dir()


def test_incomplete_fixture_directory_raises_rather_than_falling_back(monkeypatch, tmp_path):
    """A half-populated fixture must not silently become a live fetch.

    Falling back would render live data under a pinned baseline, so the gate
    would fail with a diff that looks like a UI regression and is not one.
    """
    (tmp_path / "dashboard_main.csv").write_text("repo_name\n", encoding="utf-8")
    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(tmp_path))

    assert fixtures.snapshot_path() is not None
    with pytest.raises(FileNotFoundError, match="dashboard_history.csv"):
        fixtures.history_path()


def test_snapshot_loads_from_fixture_without_network(monkeypatch):
    """load_snapshot must not touch requests when a fixture is configured."""
    from dashboard.lib import data

    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(FIXTURE_DIR))

    def explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("fixture mode must not make an HTTP request")

    monkeypatch.setattr(data.requests, "get", explode)

    df = data.load_snapshot()
    assert not df.empty
    assert df["TIMESTAMP"].nunique() == 1


def test_history_loads_from_fixture_without_network(monkeypatch):
    from dashboard.lib import trends

    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(FIXTURE_DIR))

    def explode(*args, **kwargs):  # pragma: no cover - only runs on regression
        raise AssertionError("fixture mode must not make an HTTP request")

    monkeypatch.setattr(trends.requests, "get", explode)

    snapshots = trends.load_history()
    assert len(snapshots) >= 2, "the visual baseline needs history for trend features"
    assert snapshots == sorted(snapshots, key=lambda s: s.timestamp)


def test_fixture_load_does_not_write_the_last_known_good_cache(monkeypatch, tmp_path):
    """Pinned data must never become the fallback a later live run reads."""
    from dashboard.lib import data

    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(FIXTURE_DIR))
    cache_file = tmp_path / "last_known_good.csv"
    monkeypatch.setattr(data, "_LAST_KNOWN_GOOD", cache_file)

    data.load_snapshot()

    assert not cache_file.exists()


def test_checked_in_fixture_still_satisfies_the_snapshot_integrity_checks():
    """The fixture must pass the same validation the live snapshot does.

    A fixture that failed validation would render the app's degraded state, and
    the baselines would silently encode that rather than the real dashboard.
    """
    from dashboard.lib.config import get_config
    from dashboard.lib.data import _validate_snapshot

    df = pd.read_csv(FIXTURE_DIR / "dashboard_main.csv", low_memory=False)
    valid, missing = _validate_snapshot(df, get_config("data_source"))

    assert valid, f"fixture snapshot fails integrity checks; missing={missing}"
    assert not missing


def test_checked_in_fixture_covers_every_scored_metric():
    """Every scoring metric must be present, or the baselines encode a
    score-coverage state that no longer matches production."""
    from dashboard.lib.config import get_config

    df = pd.read_csv(FIXTURE_DIR / "dashboard_main.csv", nrows=1, low_memory=False)
    metrics = get_config("scoring").get("metrics", {})

    absent = [
        cfg["column"]
        for cfg in metrics.values()
        if isinstance(cfg, dict) and cfg.get("column") and cfg["column"] not in df.columns
    ]
    assert not absent, f"fixture is missing scored columns: {absent}"

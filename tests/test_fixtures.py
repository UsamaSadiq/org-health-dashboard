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


def test_misconfigured_fixture_reaches_the_caller_through_load_snapshot(monkeypatch, tmp_path):
    """The raise must survive load_snapshot's broad `except Exception`.

    That handler exists to keep the dashboard up through an upstream outage. It
    used to swallow "your fixture path is wrong" too, and then serve
    `.cache/last_known_good.csv` — so a contributor with a warm cache and a typo
    in the path got a green-looking `--mode baseline` run whose PNGs were
    rendered from their own stale machine-local data. CI, with no cache, then
    rendered the empty state and failed with a whole-page diff that reads as a
    total UI regression.
    """
    from dashboard.lib import data

    # A warm cache is what made the old behaviour silent rather than merely wrong.
    cache_file = tmp_path / "last_known_good.csv"
    cache_file.write_text("repo_name,TIMESTAMP\nopenedx/x,2026-08-31\n", encoding="utf-8")
    monkeypatch.setattr(data, "_LAST_KNOWN_GOOD", cache_file)

    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(tmp_path / "typo"))
    with pytest.raises(ValueError, match=fixtures.FIXTURE_DIR_ENV):
        data.load_snapshot()

    # Same for a directory that exists but is missing the snapshot file.
    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(tmp_path))
    with pytest.raises(FileNotFoundError, match="dashboard_main.csv"):
        data.load_snapshot()


def test_fixture_run_never_reads_the_cache_even_when_the_fixture_is_invalid(monkeypatch, tmp_path):
    """A pinned run must not substitute cache data for fixture data by any path,
    including the failed-integrity-check branch."""
    from dashboard.lib import data

    cache_file = tmp_path / "last_known_good.csv"
    cache_file.write_text("repo_name,TIMESTAMP\nopenedx/cached,2026-01-01\n", encoding="utf-8")
    monkeypatch.setattr(data, "_LAST_KNOWN_GOOD", cache_file)

    # A fixture that parses but fails the row/column minimums.
    fixture_dir = tmp_path / "thin"
    fixture_dir.mkdir()
    (fixture_dir / "dashboard_main.csv").write_text(
        "repo_name,TIMESTAMP\nopenedx/thin,2026-08-31\n", encoding="utf-8"
    )
    (fixture_dir / "dashboard_history.csv").write_text("repo_name,TIMESTAMP\n", encoding="utf-8")
    monkeypatch.setenv(fixtures.FIXTURE_DIR_ENV, str(fixture_dir))

    df = data.load_snapshot()

    assert list(df["repo_name"]) == ["openedx/thin"], "cache leaked into a pinned run"


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

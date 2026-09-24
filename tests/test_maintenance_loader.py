"""The Maintenance page's loader: fixture files, validation, graceful absence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dashboard.lib import maintenance

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def pinned(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DATA_FIXTURE", str(FIXTURE_DIR))


@pytest.mark.parametrize(
    "relative_path", [maintenance.UPGRADE_JOBS, maintenance.REDUNDANT_PRS, maintenance.wave_file("uv_pyproject")]
)
def test_fixture_files_load_and_validate(pinned, relative_path):
    payload = maintenance.load(relative_path)

    assert payload is not None
    assert payload["metadata"]["schema_version"] == maintenance.SCHEMA_VERSION
    assert payload["records"]


def test_missing_file_returns_none(pinned):
    assert maintenance.load("waves/does_not_exist.json") is None


def test_wrong_schema_version_is_rejected(tmp_path, monkeypatch):
    (tmp_path / "maintenance").mkdir()
    (tmp_path / "maintenance" / "upgrade_jobs.json").write_text(
        json.dumps({"metadata": {"schema_version": 99}, "records": []}), encoding="utf-8"
    )
    monkeypatch.setenv("DASHBOARD_DATA_FIXTURE", str(tmp_path))

    assert maintenance.load(maintenance.UPGRADE_JOBS) is None

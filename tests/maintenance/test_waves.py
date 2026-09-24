"""Pilot B: wave progress per repo, from top-level paths and open PRs."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from collectors import waves
from dashboard.lib.config import get_config

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
MIGRATED = {"uv.lock", "pyproject.toml", "tox.ini", "Makefile", ".github", "README.rst"}
LEGACY = {"setup.py", "setup.cfg", "requirements", "tox.ini", "Makefile"}
FRONTEND = {"package.json", "src", ".nvmrc"}


@pytest.fixture(scope="module")
def uv_wave() -> dict:
    return get_config("waves")["waves"]["uv_pyproject"]


def _pr(repo: str, title: str, created: str, url: str = "https://github.com/x/pull/1") -> dict:
    return {"repository": {"nameWithOwner": repo}, "title": title, "createdAt": created, "url": url}


def test_migrated_repo_is_done(uv_wave):
    record = waves.repo_status("openedx/XBlock", MIGRATED, uv_wave, None, now=NOW)

    assert record["status"] == waves.DONE
    assert record["missing"] == [] and record["leftover"] == []


def test_legacy_repo_without_pr_is_not_started_and_lists_gaps(uv_wave):
    record = waves.repo_status("openedx/old", LEGACY, uv_wave, None, now=NOW)

    assert record["status"] == waves.NOT_STARTED
    assert record["missing"] == ["uv.lock", "pyproject.toml"]
    assert record["leftover"] == ["setup.py", "setup.cfg", "requirements"]


def test_legacy_repo_with_open_pr_reports_age(uv_wave):
    pr = _pr("openedx/ccx-keys", "feat: modernize to uv + pyproject.toml", "2026-07-27T14:04:44Z")

    record = waves.repo_status("openedx/ccx-keys", LEGACY, uv_wave, pr, now=NOW)

    assert record["status"] == waves.PR_OPEN
    assert record["pr_age_days"] == 58


def test_half_migrated_repo_is_not_done(uv_wave):
    record = waves.repo_status("openedx/half", {"pyproject.toml", "setup.py", "requirements"}, uv_wave, None, now=NOW)

    assert record["status"] == waves.NOT_STARTED
    assert record["missing"] == ["uv.lock"]


def test_non_python_repo_is_not_applicable(uv_wave):
    record = waves.repo_status("openedx/frontend-app-x", FRONTEND, uv_wave, None, now=NOW)

    assert record["status"] == waves.NOT_APPLICABLE
    assert record["missing"] == []


def test_matching_prs_keeps_the_oldest_per_repo_and_filters_titles(uv_wave):
    prs = [
        _pr("openedx/a", "build: move to uv", "2026-09-01T00:00:00Z", "u2"),
        _pr("openedx/a", "feat: pyproject.toml migration", "2026-08-01T00:00:00Z", "u1"),
        _pr("openedx/b", "fix: uvicorn bump", "2026-08-01T00:00:00Z", "u3"),
    ]

    matched = waves.matching_prs(prs, uv_wave)

    assert set(matched) == {"openedx/a"}
    assert matched["openedx/a"]["url"] == "u1"


def test_summary_excludes_not_applicable_from_progress():
    records = [{"status": waves.DONE}, {"status": waves.NOT_STARTED}, {"status": waves.NOT_APPLICABLE}]

    counts = waves.summary(records)

    assert counts["applicable"] == 2
    assert counts["percent_done"] == 50


def test_ordering_puts_unstarted_then_oldest_prs_first():
    records = [
        {"repo_name": "d", "status": waves.DONE, "pr_age_days": None},
        {"repo_name": "p1", "status": waves.PR_OPEN, "pr_age_days": 5},
        {"repo_name": "p2", "status": waves.PR_OPEN, "pr_age_days": 50},
        {"repo_name": "n", "status": waves.NOT_STARTED, "pr_age_days": None},
    ]

    assert [record["repo_name"] for record in waves.ordered(records)] == ["n", "p2", "p1", "d"]


def test_allowed_leftover_does_not_block_done(uv_wave):
    paths = MIGRATED | {"requirements"}

    assert waves.repo_status("openedx/repo-tools", paths, uv_wave, None, now=NOW)["status"] == waves.DONE
    assert waves.repo_status("openedx/other", paths, uv_wave, None, now=NOW)["status"] == waves.NOT_STARTED

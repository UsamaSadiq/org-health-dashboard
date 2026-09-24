"""Pilot A: interpreting check_requirements_failures output."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from collectors import publish, upgrade_jobs

FIXTURE = Path(__file__).parent / "fixtures" / "requirements_check_openedx_sample.csv"
TODAY = date(2026, 9, 24)


@pytest.fixture(scope="module")
def by_repo() -> dict[str, dict]:
    rows = upgrade_jobs.read_rows(FIXTURE)
    return {record["repo_name"]: record for record in upgrade_jobs.records(rows, org="openedx", today=TODAY)}


def test_all_runs_failing_is_failing_even_with_a_fresh_pr_date(by_repo):
    record = by_repo["openedx/ccx-keys"]

    assert record["state"] == upgrade_jobs.FAILING
    assert record["reason"] == "10 of the last 10 runs failed"
    assert record["weeks_since_requirements_pr"] == 0


def test_healthy_job_without_merges_is_not_landing(by_repo):
    record = by_repo["openedx/stale-repo"]

    assert record["state"] == upgrade_jobs.NOT_LANDING
    assert record["reason"] == "no requirements PR merged in 12 weeks"


def test_never_merged_is_not_landing(by_repo):
    assert by_repo["openedx/never-merged"]["reason"] == "no requirements PR ever merged"


def test_recent_merge_with_few_failures_is_healthy():
    row = {
        "Repository": "ok", "Total Runs": "10", "Failed Runs": "4", "Success Runs": "6",
        "Last PR Date": "2026-09-20", "PR URL": "", "Last Release Date": "", "Release Version": "",
    }

    record = upgrade_jobs.to_record(row, org="openedx", today=TODAY)

    assert record["state"] == upgrade_jobs.HEALTHY
    assert record["reason"] == ""


def test_counts_by_state(by_repo):
    assert upgrade_jobs.counts(list(by_repo.values())) == {"failing": 1, "not_landing": 3, "healthy": 0}


def test_record_fields(by_repo):
    record = by_repo["openedx/edx-rest-api-client"]

    assert record["github.upgrade_job_runs_total"] == 10
    assert record["github.upgrade_job_runs_failed"] == 2
    assert record["github.requirements_pr_last_merged"] == "2026-05-08"
    assert record["last_release_date"] == "2026-09-21"
    assert record["last_release_version"] == "v7.1.0"
    assert record["workflow_url"].endswith("/openedx/edx-rest-api-client/actions/workflows/upgrade-python-requirements.yml")


def test_failing_then_not_landing_then_healthy(by_repo):
    rows = upgrade_jobs.read_rows(FIXTURE)
    ordered = upgrade_jobs.records(rows, org="openedx", today=TODAY)

    ranks = [upgrade_jobs.STATE_ORDER.index(record["state"]) for record in ordered]
    assert ranks == sorted(ranks)


def test_changed_tool_output_fails_loudly(tmp_path):
    changed = tmp_path / "changed.csv"
    changed.write_text("Repository,Runs\nx,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="format changed"):
        upgrade_jobs.read_rows(changed)


def test_published_payload_round_trips_as_strict_json(tmp_path, by_repo):
    target = tmp_path / "upgrade_jobs.json"
    content = publish.payload(
        list(by_repo.values()),
        generated_at=datetime(2026, 9, 24, tzinfo=timezone.utc),
        source=upgrade_jobs.SOURCE,
        repos_checked=4,
    )

    publish.write(target, content)

    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["metadata"]["schema_version"] == publish.SCHEMA_VERSION
    assert loaded["metadata"]["repos_checked"] == 4
    assert len(loaded["records"]) == 4

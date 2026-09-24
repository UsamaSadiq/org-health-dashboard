"""Pilot C close step: explicit repos only, re-check before closing."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from collectors import closing

ROOT = Path(__file__).resolve().parents[2]
RECORDS = [
    {"repo_name": "openedx/a", "bot_pr_number": 1, "superseded_by_url": "https://x/2", "superseded_by_title": "pin", "confidence": "c"},
    {"repo_name": "openedx/b", "bot_pr_number": 3, "superseded_by_url": "https://x/4", "superseded_by_title": "pin", "confidence": "c"},
]


def test_plan_keeps_only_allowed_repos():
    assert [record["repo_name"] for record in closing.plan(RECORDS, {"openedx/b"})] == ["openedx/b"]


def test_apply_closes_open_prs_and_skips_changed_ones():
    calls = []

    closed, skipped = closing.apply(
        RECORDS,
        is_still_open=lambda repo, number: repo == "openedx/a",
        close_with_comment=lambda repo, number, comment: calls.append((repo, number, comment)),
    )

    assert [record["repo_name"] for record in closed] == ["openedx/a"]
    assert [record["repo_name"] for record in skipped] == ["openedx/b"]
    assert calls == [("openedx/a", 1, closing.COMMENT.format(url="https://x/2", title="pin"))]


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    source = tmp_path / "redundant_prs.json"
    source.write_text(json.dumps({"metadata": {}, "records": RECORDS}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, "scripts/close_redundant_prs.py", "--input", str(source), *args],
        cwd=ROOT, env={"PYTHONPATH": str(ROOT), "PATH": ""}, capture_output=True, text=True,
    )


def test_cli_dry_run_changes_nothing(tmp_path):
    result = _run(tmp_path)

    assert result.returncode == 0
    assert "Dry run: 2 PR(s) would be closed" in result.stdout


def test_cli_apply_without_repo_refuses(tmp_path):
    result = _run(tmp_path, "--apply")

    assert result.returncode == 2
    assert "refusing" in result.stdout

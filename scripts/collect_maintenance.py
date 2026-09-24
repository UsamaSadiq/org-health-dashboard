#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from collectors import publish, upgrade_jobs
from dashboard.lib.clock import now_utc

ORG = "openedx"
UPGRADE_JOBS_FILE = "upgrade_jobs.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect maintenance signals into files the dashboard reads.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repo", action="append", default=[], help="Limit to these repos (bare names); default is the whole org.")
    return parser.parse_args()


def collect_upgrade_jobs(out_dir: Path, repos: list[str]) -> int:
    generated_at = now_utc()
    with tempfile.TemporaryDirectory() as tmp:
        rows = upgrade_jobs.read_rows(upgrade_jobs.run_tool(ORG, Path(tmp), repos))
    records = upgrade_jobs.records(rows, org=ORG, today=generated_at.date())
    if not records:
        print("No upgrade-job records; not writing.")
        return 1
    broken = sum(record["broken"] for record in records)
    content = publish.payload(
        records,
        generated_at=generated_at,
        source=upgrade_jobs.SOURCE,
        repos_checked=len(records),
        repos_broken=broken,
    )
    publish.write(out_dir / UPGRADE_JOBS_FILE, content)
    print(f"Upgrade jobs: {len(records)} repos, {broken} broken")
    return 0


def main() -> int:
    args = _parse_args()
    return collect_upgrade_jobs(args.out_dir, args.repo)


if __name__ == "__main__":
    sys.exit(main())

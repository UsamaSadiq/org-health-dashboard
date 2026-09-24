#!/usr/bin/env python3
"""Close bot PRs listed in redundant_prs.json. Dry run unless --apply is given.

Run manually, under the caller's own GitHub identity; never scheduled.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from collectors import closing, github


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Path to redundant_prs.json")
    parser.add_argument("--repo", action="append", default=[], help="owner/name allowed to be touched; repeat per repo")
    parser.add_argument("--apply", action="store_true", help="Actually comment and close; default only prints the plan")
    return parser.parse_args()


def _is_still_open(repo: str, number: int) -> bool:
    return (github.gh_json("pr", "view", str(number), "--repo", repo, "--json", "state") or {}).get("state") == "OPEN"


def _close_with_comment(repo: str, number: int, comment: str) -> None:
    subprocess.run(["gh", "pr", "close", str(number), "--repo", repo, "--comment", comment], check=True)


def main() -> int:
    args = _parse_args()
    if args.apply and not args.repo:
        print("--apply needs at least one --repo; refusing to touch every listed repo.")
        return 2
    records = json.loads(args.input.read_text(encoding="utf-8"))["records"]
    planned = closing.plan(records, set(args.repo)) if args.repo else records
    for record in planned:
        print(f"{record['repo_name']}#{record['bot_pr_number']}: superseded by {record['superseded_by_url']} ({record['confidence']})")
    if not args.apply:
        print(f"Dry run: {len(planned)} PR(s) would be closed. Nothing was changed.")
        return 0
    closed, skipped = closing.apply(planned, is_still_open=_is_still_open, close_with_comment=_close_with_comment)
    print(f"Closed {len(closed)}; skipped {len(skipped)} no longer open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

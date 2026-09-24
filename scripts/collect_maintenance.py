#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from collectors import github, publish, redundant_prs, upgrade_jobs, waves
from dashboard.lib.clock import now_utc
from dashboard.lib.config import get_config

ORG = "openedx"
UPGRADE_JOBS_FILE = "upgrade_jobs.json"
WAVES_DIR = "waves"
REDUNDANT_PRS_FILE = "redundant_prs.json"
TREE_WORKERS = 8
COLLECTORS = ("upgrade_jobs", "waves", "redundant_prs")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect maintenance signals into files the dashboard reads.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repo", action="append", default=[], help="Limit to these repos (bare names); default is the whole org.")
    parser.add_argument("--collector", action="append", choices=COLLECTORS, help="Run only these collectors; default is all.")
    return parser.parse_args()


def collect_upgrade_jobs(out_dir: Path, repos: list[str]) -> int:
    generated_at = now_utc()
    with tempfile.TemporaryDirectory() as tmp:
        rows = upgrade_jobs.read_rows(upgrade_jobs.run_tool(ORG, Path(tmp), repos))
    records = upgrade_jobs.records(rows, org=ORG, today=generated_at.date())
    if not records:
        print("No upgrade-job records; not writing.")
        return 1
    states = upgrade_jobs.counts(records)
    content = publish.payload(
        records,
        generated_at=generated_at,
        source=upgrade_jobs.SOURCE,
        repos_checked=len(records),
        states=states,
    )
    publish.write(out_dir / UPGRADE_JOBS_FILE, content)
    print(f"Upgrade jobs: {len(records)} repos, {states}")
    return 0


def _repo_trees(repos: list[dict]) -> dict[str, set[str]]:
    def tree(repo: dict) -> tuple[str, set[str]]:
        return repo["full_name"], github.top_level_paths(repo["full_name"], repo["default_branch"])

    with ThreadPoolExecutor(max_workers=TREE_WORKERS) as pool:
        return dict(pool.map(tree, repos))


def collect_waves(out_dir: Path, repo_filter: list[str]) -> int:
    generated_at = now_utc()
    repos = [repo for repo in github.org_repos(ORG) if not repo_filter or repo["name"] in repo_filter]
    if not repos:
        print("No repositories found; not writing waves.")
        return 1
    trees = _repo_trees(repos)
    for wave_id, wave in get_config("waves").get("waves", {}).items():
        prs = [pr for term in wave["pull_requests"]["search_terms"] for pr in github.search_open_prs(ORG, term)]
        open_prs = waves.matching_prs(prs, wave)
        records = waves.ordered(
            [
                waves.repo_status(name, paths, wave, open_prs.get(name), now=generated_at)
                for name, paths in trees.items()
            ]
        )
        content = publish.payload(
            records,
            generated_at=generated_at,
            source="GitHub repository contents and PR search",
            wave_id=wave_id,
            title=wave["title"],
            epic=wave.get("epic"),
            summary=waves.summary(records),
        )
        publish.write(out_dir / WAVES_DIR / f"{wave_id}.json", content)
        print(f"Wave {wave_id}: {waves.summary(records)}")
    return 0


def collect_redundant_prs(out_dir: Path, repo_filter: list[str]) -> int:
    generated_at = now_utc()
    found, checked = [], 0
    for campaign_id, campaign in get_config("campaign_supersession").get("campaigns", {}).items():
        bot_prs = [
            pr for pr in github.search_open_prs_by_author(ORG, campaign["bot_author"], campaign["bot_title_prefix"])
            if pr["title"].startswith(campaign["bot_title_prefix"])
            and (not repo_filter or pr["repository"]["nameWithOwner"].split("/", 1)[1] in repo_filter)
        ]
        checked += len(bot_prs)
        for bot_pr in bot_prs:
            repo = bot_pr["repository"]["nameWithOwner"]
            human_pr = redundant_prs.superseding_pr(
                bot_pr, github.merged_prs(repo, campaign["human_search"]), campaign["human_title_regex"]
            )
            if human_pr:
                found.append(
                    redundant_prs.record(campaign_id, bot_pr, human_pr, github.merge_state(repo, bot_pr["number"]))
                )
    content = publish.payload(
        redundant_prs.ordered(found),
        generated_at=generated_at,
        source="GitHub PR search; dry run, nothing closed",
        bot_prs_checked=checked,
        redundant=len(found),
    )
    publish.write(out_dir / REDUNDANT_PRS_FILE, content)
    print(f"Redundant PRs: {len(found)} of {checked} open bot campaign PRs")
    return 0


def main() -> int:
    args = _parse_args()
    selected = args.collector or list(COLLECTORS)
    runners = {
        "upgrade_jobs": collect_upgrade_jobs,
        "waves": collect_waves,
        "redundant_prs": collect_redundant_prs,
    }
    results = [runners[name](args.out_dir, args.repo) for name in selected]
    return max(results)


if __name__ == "__main__":
    sys.exit(main())

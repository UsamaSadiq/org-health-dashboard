"""Pilot C: bot campaign PRs made redundant by a later human campaign (dry run).

A bot PR counts as redundant when a merged PR in the same repo matches the
campaign's human title and was merged after the bot PR was opened. A bot PR that
now conflicts with the default branch is reported with higher confidence.
Nothing here closes anything; see scripts/close_redundant_prs.py.
"""
from __future__ import annotations

import re
from typing import Any

CONFLICTING = "conflicts with default branch"
SUPERSEDED = "superseded; still mergeable"


def superseding_pr(bot_pr: dict[str, Any], merged: list[dict[str, Any]], human_title_regex: str) -> dict[str, Any] | None:
    pattern = re.compile(human_title_regex, re.IGNORECASE)
    later = [
        pr for pr in merged
        if pattern.search(pr.get("title", "")) and (pr.get("mergedAt") or "") > bot_pr["createdAt"]
    ]
    return min(later, key=lambda pr: pr["mergedAt"]) if later else None


def record(campaign_id: str, bot_pr: dict[str, Any], human_pr: dict[str, Any], merge_state: str) -> dict[str, Any]:
    return {
        "repo_name": bot_pr["repository"]["nameWithOwner"],
        "campaign": campaign_id,
        "bot_pr_number": bot_pr["number"],
        "bot_pr_url": bot_pr["url"],
        "bot_pr_title": bot_pr["title"],
        "bot_pr_created": bot_pr["createdAt"][:10],
        "superseded_by_url": human_pr["url"],
        "superseded_by_title": human_pr["title"],
        "superseded_by_merged": human_pr["mergedAt"][:10],
        "merge_state": merge_state,
        "confidence": CONFLICTING if merge_state == "DIRTY" else SUPERSEDED,
    }


def ordered(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: (item["confidence"] != CONFLICTING, item["repo_name"]))

"""Plan and apply closing of redundant bot PRs listed by the Pilot C collector.

Only ``apply`` writes to GitHub, and only for repos the caller names explicitly.
Every PR is re-checked right before closing; anything that changed is skipped.
"""
from __future__ import annotations

from typing import Any, Callable

COMMENT = "Superseded by {url} ({title}), which pinned the same workflows. Closing as redundant."


def plan(records: list[dict[str, Any]], allowed_repos: set[str]) -> list[dict[str, Any]]:
    return [record for record in records if record["repo_name"] in allowed_repos]


def apply(
    planned: list[dict[str, Any]],
    *,
    is_still_open: Callable[[str, int], bool],
    close_with_comment: Callable[[str, int, str], None],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    closed, skipped = [], []
    for record in planned:
        repo, number = record["repo_name"], record["bot_pr_number"]
        if not is_still_open(repo, number):
            skipped.append(record)
            continue
        close_with_comment(repo, number, COMMENT.format(url=record["superseded_by_url"], title=record["superseded_by_title"]))
        closed.append(record)
    return closed, skipped

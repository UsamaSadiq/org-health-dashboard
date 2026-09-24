"""Minimal read-only GitHub access through the ``gh`` CLI (authenticated by GH_TOKEN)."""
from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any

RETRIES = 3
SEARCH_PAUSE_SECONDS = 2.5


def gh_json(*args: str) -> Any:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(RETRIES):
        try:
            result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
            return json.loads(result.stdout or "null")
        except subprocess.CalledProcessError as error:
            last_error = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gh {' '.join(args)} failed: {last_error.stderr if last_error else ''}")


def org_repos(org: str) -> list[dict[str, Any]]:
    pages = gh_json("api", f"orgs/{org}/repos", "--paginate", "--slurp")
    return [repo for page in pages for repo in page if not repo.get("archived")]


def top_level_paths(full_name: str, ref: str) -> set[str]:
    try:
        entries = gh_json("api", f"repos/{full_name}/contents/?ref={ref}")
    except RuntimeError:
        return set()
    return {entry["name"] for entry in entries or []}


def search_open_prs(org: str, term: str) -> list[dict[str, Any]]:
    time.sleep(SEARCH_PAUSE_SECONDS)
    return gh_json(
        "search", "prs", "--owner", org, "--state", "open", "--limit", "1000",
        "--json", "repository,title,url,createdAt", "--", f"{term} in:title",
    ) or []


def search_open_prs_by_author(org: str, author: str, title: str) -> list[dict[str, Any]]:
    time.sleep(SEARCH_PAUSE_SECONDS)
    return gh_json(
        "search", "prs", "--owner", org, "--state", "open", "--author", author, "--limit", "1000",
        "--json", "repository,title,url,number,createdAt", "--", f"{_search_words(title)} in:title",
    ) or []


def merged_prs(full_name: str, search: str) -> list[dict[str, Any]]:
    return gh_json(
        "pr", "list", "--repo", full_name, "--state", "merged", "--limit", "20",
        "--search", f"{_search_words(search)} in:title", "--json", "number,title,url,mergedAt,author",
    ) or []


def merge_state(full_name: str, number: int) -> str:
    return (gh_json("pr", "view", str(number), "--repo", full_name, "--json", "mergeStateStatus") or {}).get(
        "mergeStateStatus", "UNKNOWN"
    )


def _search_words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())

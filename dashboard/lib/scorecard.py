from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class ScorecardCheck:
    name: str
    score: float | None
    reason: str


@dataclass(frozen=True)
class ScorecardResult:
    score: float | None
    date: str
    repo: str
    checks: list[ScorecardCheck]


def _parse_repo(repo_name: str) -> tuple[str, str] | None:
    if not repo_name or "/" not in repo_name:
        return None
    owner, repo = repo_name.split("/", 1)
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        return None
    return owner, repo


def fetch_scorecard_result(repo_name: str, timeout: int = 8) -> ScorecardResult | None:
    parsed = _parse_repo(repo_name)
    if parsed is None:
        return None

    owner, repo = parsed
    url = f"https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}"

    response = requests.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()

    payload = response.json() or {}
    checks = [
        ScorecardCheck(
            name=str(item.get("name", "")),
            score=item.get("score"),
            reason=str(item.get("reason", "")),
        )
        for item in payload.get("checks", [])
        if item.get("name")
    ]
    return ScorecardResult(
        score=payload.get("score"),
        date=str(payload.get("date", "")),
        repo=repo_name,
        checks=checks,
    )

from __future__ import annotations

from dataclasses import dataclass

from dashboard.lib.config import get_config


@dataclass(frozen=True)
class RemediationEntry:
    check: str
    title: str
    description: str
    source_url: str
    snippet: str | None
    applies_to_tiers: list[str]
    chaoss_metric: str | None
    scorecard_check: str | None
    issue_body_template: str | None


def load_remediation_map() -> dict[str, RemediationEntry]:
    config = get_config("remediation")
    checks = config.get("checks", {})
    entries: dict[str, RemediationEntry] = {}

    for check_name, raw in checks.items():
        entries[check_name] = RemediationEntry(
            check=check_name,
            title=str(raw.get("title", check_name)),
            description=str(raw.get("description", "")),
            source_url=str(raw.get("source_url", "")),
            snippet=raw.get("snippet"),
            applies_to_tiers=list(raw.get("applies_to_tiers", [])),
            chaoss_metric=raw.get("chaoss_metric"),
            scorecard_check=raw.get("scorecard_check"),
            issue_body_template=raw.get("issue_body_template"),
        )
    return entries


def get_remediation(check_name: str) -> RemediationEntry | None:
    return load_remediation_map().get(check_name)


def missing_remediation_checks(checks_in_snapshot: list[str]) -> list[str]:
    configured = set(load_remediation_map().keys())
    return sorted([check for check in checks_in_snapshot if check not in configured])
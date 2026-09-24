"""Pilot C: bot campaign PRs superseded by a later human campaign."""
from __future__ import annotations

from dashboard.lib.config import get_config
from collectors import redundant_prs

REGEX = get_config("campaign_supersession")["campaigns"]["action_sha_pinning"]["human_title_regex"]
BOT = {
    "repository": {"nameWithOwner": "openedx/pytest-repo-health"},
    "number": 374,
    "url": "https://github.com/openedx/pytest-repo-health/pull/374",
    "title": "chore: Update Github action package versions with SHA commit",
    "createdAt": "2026-05-15T10:00:00Z",
}


def _merged(title: str, merged_at: str, url: str = "https://github.com/openedx/pytest-repo-health/pull/375") -> dict:
    return {"title": title, "mergedAt": merged_at, "url": url}


def test_later_human_campaign_supersedes_the_bot_pr():
    human = _merged("chore: pin github actions workflows to full commit SHAs", "2026-05-30T09:00:00Z")

    assert redundant_prs.superseding_pr(BOT, [human], REGEX) == human


def test_human_pr_merged_before_the_bot_pr_does_not_count():
    earlier = _merged("chore: pin github actions workflows to full commit shas", "2026-01-12T09:00:00Z")

    assert redundant_prs.superseding_pr(BOT, [earlier], REGEX) is None


def test_unrelated_merged_pr_does_not_count():
    other = _merged("fix: bump actions/checkout", "2026-06-01T00:00:00Z")

    assert redundant_prs.superseding_pr(BOT, [other], REGEX) is None


def test_earliest_superseding_merge_is_chosen():
    first = _merged("chore: pin github actions workflows to full commit shas", "2026-05-30T00:00:00Z", "u1")
    second = _merged("chore: pin github action workflows to full commit sha", "2026-06-10T00:00:00Z", "u2")

    assert redundant_prs.superseding_pr(BOT, [second, first], REGEX)["url"] == "u1"


def test_conflicting_bot_pr_gets_higher_confidence_and_sorts_first():
    human = _merged("chore: pin github actions workflows to full commit shas", "2026-05-30T00:00:00Z")
    dirty = redundant_prs.record("action_sha_pinning", BOT, human, "DIRTY")
    clean = redundant_prs.record(
        "action_sha_pinning", {**BOT, "repository": {"nameWithOwner": "openedx/aaa"}}, human, "CLEAN"
    )

    assert dirty["confidence"] == redundant_prs.CONFLICTING
    assert clean["confidence"] == redundant_prs.SUPERSEDED
    assert [item["repo_name"] for item in redundant_prs.ordered([clean, dirty])] == [
        "openedx/pytest-repo-health",
        "openedx/aaa",
    ]
    assert dirty["superseded_by_merged"] == "2026-05-30"

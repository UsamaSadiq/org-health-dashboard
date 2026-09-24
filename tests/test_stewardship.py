"""At-risk ownership: thin ownership joined with weak or falling activity."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from dashboard.lib import stewardship

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
RECENT_PUSH = "2026-09-20 10:00:00"
OLD_PUSH = "2025-01-01 10:00:00"


def _row(repo, owner="", kind="", name="", activity=80.0, push=RECENT_PUSH, score=70.0, **extra):
    return {
        "repo_name": repo,
        "ownership.owner": owner,
        "ownership.owner_kind": kind,
        "ownership.owner_name": name,
        "score_activity": activity,
        "github.last_push": push,
        "score_composite": score,
        "score_letter": "B",
        **extra,
    }


def _needs_maintainer(repo, **kwargs):
    return _row(repo, "group:openedx-unmaintained", "group", "openedx-unmaintained", **kwargs)


@pytest.mark.parametrize(
    "row, expected",
    [
        (_needs_maintainer("a"), stewardship.NEEDS_MAINTAINER),
        (_row("b", "user:alice", "user", "alice"), stewardship.SINGLE_PERSON),
        (_row("c"), stewardship.NO_OWNER),
        (_row("d", "group:team", "group", "team"), stewardship.TEAM),
    ],
)
def test_owner_status(row, expected):
    status = stewardship.owner_status(pd.Series(row), unmaintained_group="openedx-unmaintained")

    assert status == expected


def test_team_owned_repos_are_never_at_risk():
    scored = pd.DataFrame([_row("openedx/x", "group:team", "group", "team", activity=5.0, push=OLD_PUSH)])

    assert stewardship.at_risk_repos(scored, None, now=NOW).empty


def test_thin_ownership_without_warnings_is_not_listed():
    scored = pd.DataFrame([_needs_maintainer("openedx/healthy")])

    assert stewardship.at_risk_repos(scored, None, now=NOW).empty


def test_each_warning_is_reported():
    scored = pd.DataFrame([_needs_maintainer("openedx/ora", activity=10.0, push=OLD_PUSH, score=40.0)])
    baseline = pd.DataFrame([{"repo_name": "openedx/ora", "score_composite": 50.0}])

    result = stewardship.at_risk_repos(scored, baseline, now=NOW)

    reasons = result.loc[0, "reasons"]
    assert "activity score below 40" in reasons
    assert "no push in" in reasons
    assert "score down 10.0 points" in reasons
    assert result.loc[0, "delta"] == pytest.approx(-10.0)


def test_rule_thresholds_come_from_config():
    scored = pd.DataFrame([_row("openedx/y", "user:bob", "user", "bob", activity=55.0)])

    listed = stewardship.at_risk_repos(scored, None, now=NOW, rule={"weak_activity_below": 60})

    assert list(listed["repo_name"]) == ["openedx/y"]


def test_repo_missing_from_baseline_has_no_delta():
    scored = pd.DataFrame([_needs_maintainer("openedx/new", activity=10.0)])
    baseline = pd.DataFrame([{"repo_name": "openedx/other", "score_composite": 50.0}])

    result = stewardship.at_risk_repos(scored, baseline, now=NOW)

    assert pd.isna(result.loc[0, "delta"])


def test_catalog_link_uses_repo_basename():
    scored = pd.DataFrame([_needs_maintainer("openedx/edx-ora2", activity=10.0)])

    link = stewardship.at_risk_repos(scored, None, now=NOW).loc[0, "catalog_link"]

    assert link == "https://backstage.openedx.org/catalog/default/component/edx-ora2"


def test_production_or_release_filter():
    frame = pd.DataFrame(
        {"lifecycle": ["production", "experimental", "", ""], "release": ["", "", "master", ""]}
    )

    assert list(stewardship.production_or_release(frame)) == [True, False, True, False]


def test_repo_without_ownership_columns_counts_as_no_owner():
    scored = pd.DataFrame([{"repo_name": "openedx/z", "score_composite": 50.0, "score_activity": 10.0}])

    result = stewardship.at_risk_repos(scored, None, now=NOW)

    assert list(result["owner_status"]) == [stewardship.NO_OWNER]


@pytest.mark.parametrize(
    "extra",
    [{"ownership.lifecycle": "deprecated"}, {"ownership.lifecycle": "Deprecated"}, {"github.is_archived": True}],
    ids=["deprecated", "deprecated-case", "archived"],
)
def test_retired_repos_are_left_out(extra):
    scored = pd.DataFrame([_needs_maintainer("openedx/old", activity=5.0, push=OLD_PUSH, **extra)])

    assert stewardship.at_risk_repos(scored, None, now=NOW).empty


def test_production_repo_waiting_for_maintainer_is_listed():
    scored = pd.DataFrame(
        [_needs_maintainer("openedx/edx-ora2", activity=10.0, **{"ownership.lifecycle": "production"})]
    )

    result = stewardship.at_risk_repos(scored, None, now=NOW)

    assert list(result["owner_status"]) == [stewardship.NEEDS_MAINTAINER]


def test_rows_are_ordered_by_status_then_score():
    scored = pd.DataFrame(
        [
            _row("openedx/c", activity=10.0, score=20.0),
            _row("openedx/b", "user:bob", "user", "bob", activity=10.0, score=30.0),
            _needs_maintainer("openedx/a2", activity=10.0, score=60.0),
            _needs_maintainer("openedx/a1", activity=10.0, score=50.0),
        ]
    )

    result = stewardship.at_risk_repos(scored, None, now=NOW)

    assert list(result["repo_name"]) == ["openedx/a1", "openedx/a2", "openedx/b", "openedx/c"]

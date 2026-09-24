"""Repos whose ownership is thin and whose activity is weak or falling.

Joins the ``ownership.*`` columns from ``catalog-info.yaml`` with activity and
score history: the view Backstage's catalog cannot produce, because Backstage
has owners but no health data. Thresholds come from ``attention_rules.yaml``
(``stewardship_risk``) so they can be reviewed without touching code.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from dashboard.lib.schema import LAST_PUSH_COL, REPO_COL, parse_last_push_utc

OWNER_COL = "ownership.owner"
OWNER_KIND_COL = "ownership.owner_kind"
OWNER_NAME_COL = "ownership.owner_name"
LIFECYCLE_COL = "ownership.lifecycle"
RELEASE_COL = "ownership.release"

UNMAINTAINED = "unmaintained"
SINGLE_PERSON = "single person"
NO_OWNER = "no owner"
TEAM = "team"

AT_RISK_STATUSES = (UNMAINTAINED, SINGLE_PERSON, NO_OWNER)

DEFAULT_RULE: dict[str, Any] = {
    "unmaintained_group": "openedx-unmaintained",
    "weak_activity_below": 40,
    "stale_push_days": 180,
    "score_drop_points": 5,
    "catalog_url_template": "https://backstage.openedx.org/catalog/default/component/{name}",
}


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def owner_status(row: pd.Series, *, unmaintained_group: str) -> str:
    if _text(row.get(OWNER_NAME_COL)) == unmaintained_group:
        return UNMAINTAINED
    if not _text(row.get(OWNER_COL)):
        return NO_OWNER
    if _text(row.get(OWNER_KIND_COL)) == "user":
        return SINGLE_PERSON
    return TEAM


def has_column_data(df: pd.DataFrame, column: str) -> bool:
    return column in df.columns and df[column].map(_text).ne("").any()


def score_deltas(current: pd.DataFrame, baseline: pd.DataFrame | None) -> pd.Series:
    """Composite change per repo since ``baseline``; NaN where there is no baseline row."""
    if baseline is None or baseline.empty:
        return pd.Series(float("nan"), index=current.index)
    before = baseline.set_index(REPO_COL)["score_composite"]
    before = before[~before.index.duplicated()]
    return current["score_composite"] - current[REPO_COL].map(before)


def _days_since_push(row: pd.Series, now: datetime) -> int | None:
    pushed = parse_last_push_utc(row.get(LAST_PUSH_COL))
    return (now - pushed).days if pushed else None


def _reasons(activity: object, days: int | None, delta: float, rule: dict[str, Any]) -> list[str]:
    reasons = []
    if pd.notna(activity) and float(activity) < float(rule["weak_activity_below"]):
        reasons.append(f"activity score below {rule['weak_activity_below']}")
    if days is not None and days >= int(rule["stale_push_days"]):
        reasons.append(f"no push in {days} days")
    if pd.notna(delta) and delta <= -float(rule["score_drop_points"]):
        reasons.append(f"score down {abs(delta):.1f} points")
    return reasons


def catalog_url(repo_name: str, template: str) -> str:
    return template.format(name=repo_name.rsplit("/", 1)[-1])


def at_risk_repos(
    scored: pd.DataFrame,
    baseline: pd.DataFrame | None,
    *,
    now: datetime,
    rule: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """One row per repo with thin ownership and at least one activity warning."""
    rule = {**DEFAULT_RULE, **(rule or {})}
    if scored.empty or REPO_COL not in scored.columns:
        return pd.DataFrame()

    deltas = score_deltas(scored, baseline)
    rows = []
    for index, row in scored.iterrows():
        status = owner_status(row, unmaintained_group=rule["unmaintained_group"])
        if status not in AT_RISK_STATUSES:
            continue
        days = _days_since_push(row, now)
        reasons = _reasons(row.get("score_activity"), days, deltas.loc[index], rule)
        if not reasons:
            continue
        repo = str(row[REPO_COL])
        rows.append(
            {
                REPO_COL: repo,
                "owner_status": status,
                "owner": _text(row.get(OWNER_NAME_COL)),
                "lifecycle": _text(row.get(LIFECYCLE_COL)),
                "release": _text(row.get(RELEASE_COL)),
                "score_composite": row.get("score_composite"),
                "score_letter": row.get("score_letter"),
                "score_activity": row.get("score_activity"),
                "days_since_push": days,
                "delta": deltas.loc[index],
                "reasons": "; ".join(reasons),
                "catalog_link": catalog_url(repo, rule["catalog_url_template"]),
            }
        )
    return pd.DataFrame(rows)


def production_or_release(df: pd.DataFrame) -> pd.Series:
    """True for repos marked production or tracked in a named release."""
    lifecycle = df.get("lifecycle", pd.Series("", index=df.index)).fillna("")
    release = df.get("release", pd.Series("", index=df.index)).fillna("")
    return lifecycle.eq("production") | release.ne("")

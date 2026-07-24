from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

import pandas as pd

from dashboard.lib.config import get_config
from dashboard.lib.schema import TIMESTAMP_COL, parse_last_push_utc, parse_snapshot_date


@dataclass(frozen=True)
class Score:
    composite: float
    letter: str
    per_metric: dict[str, float]
    per_metric_weight: dict[str, float]
    per_metric_category: dict[str, str]
    unavailable_metrics: list[str]
    coverage: float  # 0..1 — fraction of total metric weight that was available
    structural: float | None  # composite over the structural sub-set (None when empty)
    activity: float | None  # composite over the activity sub-set (None when empty)
    config_version: str


CATEGORY_STRUCTURAL = "structural"
CATEGORY_ACTIVITY = "activity"


DEFAULT_LETTER_GRADES = {"A": [80, 100], "B": [60, 79], "C": [40, 59], "D": [20, 39], "F": [0, 19]}


def _as_of_datetime(as_of: date | datetime | None) -> datetime:
    """Resolve the 'now' reference used by time-sensitive metrics.

    Falls back to wall-clock only when no snapshot date is available; this
    keeps scoring of historical snapshots stable across reruns.
    """
    if isinstance(as_of, datetime):
        return as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    if isinstance(as_of, date):
        return datetime.combine(as_of, time.min, tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def score_row(
    row: pd.Series,
    columns: list[str],
    *,
    as_of: date | datetime | None = None,
) -> Score:
    """Compute score object for a single repository row."""
    config = get_config("scoring")
    metrics_cfg = config.get("metrics", {})
    letter_grades = config.get("letter_grades", DEFAULT_LETTER_GRADES)
    reference_dt = _as_of_datetime(as_of)

    weighted_sum = 0.0
    available_weight = 0.0
    total_weight = 0.0
    per_metric: dict[str, float] = {}
    per_metric_weight: dict[str, float] = {}
    per_metric_category: dict[str, str] = {}
    unavailable: list[str] = []

    structural_sum = structural_weight = 0.0
    activity_sum = activity_weight = 0.0

    for metric_name, metric_cfg in metrics_cfg.items():
        weight = float(metric_cfg.get("weight", 0))
        total_weight += weight
        category = str(metric_cfg.get("category", "")).lower() or None

        status = metric_cfg.get("status", "unavailable")
        column = metric_cfg.get("column")
        if status != "computable" or not column or column not in columns:
            unavailable.append(metric_name)
            continue

        metric_score = _metric_score(metric_name, metric_cfg, row.get(column), row, reference_dt=reference_dt)
        per_metric[metric_name] = metric_score
        per_metric_weight[metric_name] = weight
        if category:
            per_metric_category[metric_name] = category
        weighted_sum += metric_score * weight
        available_weight += weight

        if category == CATEGORY_STRUCTURAL:
            structural_sum += metric_score * weight
            structural_weight += weight
        elif category == CATEGORY_ACTIVITY:
            activity_sum += metric_score * weight
            activity_weight += weight

    composite = weighted_sum / available_weight if available_weight else 0.0
    coverage = (available_weight / total_weight) if total_weight else 0.0
    structural = round(structural_sum / structural_weight, 2) if structural_weight else None
    activity = round(activity_sum / activity_weight, 2) if activity_weight else None
    letter = _get_letter_grade(composite, letter_grades)

    return Score(
        composite=round(float(composite), 2),
        letter=letter,
        per_metric=per_metric,
        per_metric_weight=per_metric_weight,
        per_metric_category=per_metric_category,
        unavailable_metrics=unavailable,
        coverage=round(float(coverage), 4),
        structural=structural,
        activity=activity,
        config_version=str(config.get("version", "unknown")),
    )


def calculate_scores(
    df: pd.DataFrame,
    *,
    as_of: date | datetime | None = None,
) -> pd.DataFrame:
    """Calculate composite score and letter for each row in dataframe.

    `as_of` overrides the reference time for time-sensitive metrics
    (e.g. `commit_recency`). When omitted, the snapshot's `TIMESTAMP`
    column is used; only when neither is available does the implementation
    fall back to wall-clock — which is the failure mode the new behavior
    is designed to avoid for historical snapshots.
    """
    if df.empty:
        return df

    if as_of is None and TIMESTAMP_COL in df.columns:
        as_of = parse_snapshot_date(df[TIMESTAMP_COL].iloc[0])

    columns = list(df.columns)
    scores = [score_row(row, columns, as_of=as_of) for _, row in df.iterrows()]

    df = df.copy()
    df["score_composite"] = [score.composite for score in scores]
    df["score_letter"] = [score.letter for score in scores]
    df["score_per_metric"] = [score.per_metric for score in scores]
    df["score_per_metric_weight"] = [score.per_metric_weight for score in scores]
    df["score_per_metric_category"] = [score.per_metric_category for score in scores]
    df["score_unavailable_metrics"] = [score.unavailable_metrics for score in scores]
    df["score_coverage"] = [score.coverage for score in scores]
    df["score_structural"] = [score.structural for score in scores]
    df["score_activity"] = [score.activity for score in scores]
    df["score_config_version"] = [score.config_version for score in scores]
    return df


# ---------------------------------------------------------------------------
# Per-metric handlers
# ---------------------------------------------------------------------------
def _metric_score(
    metric_name: str,
    cfg: dict[str, Any],
    value: Any,
    row: pd.Series,
    *,
    reference_dt: datetime,
) -> float:
    if pd.isna(value):
        return float(cfg.get("default_when_missing", 50))

    if metric_name == "commit_recency":
        pushed = parse_last_push_utc(value)
        if pushed is None:
            return float(cfg.get("default_when_missing", 50))
        days = (reference_dt - pushed).days
        return _score_by_days(days, cfg.get("thresholds", []), default=0)

    if metric_name == "readme_quality":
        return _score_readme_quality(row)

    if metric_name in {"ci_status", "openedx_yaml_compliance"}:
        as_str = str(value).strip().lower()
        if as_str in {"true", "1", "yes"}:
            return 100.0
        if as_str in {"false", "0", "no"}:
            return 0.0
        return 50.0

    if metric_name == "dependency_freshness":
        return _score_dependency_freshness(row)

    if metric_name == "pr_response_time":
        # Median seconds to first response — lower is better, so score by an
        # ascending "max" ceiling rather than the higher-is-better handler.
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return float(cfg.get("default_when_missing", 50))
        return _score_by_max_threshold(numeric, cfg.get("thresholds", []), default=0)

    # Generic threshold-based numeric metric handler (higher is better).
    try:
        numeric = float(value)
        return _score_by_threshold(numeric, cfg.get("thresholds", []), default=50)
    except (TypeError, ValueError):
        return float(cfg.get("default_when_missing", 50))


def _score_by_days(days: int, thresholds: list[dict[str, Any]], default: float) -> float:
    for item in sorted(thresholds, key=lambda entry: int(entry["days"])):
        if days <= int(item["days"]):
            return float(item["score"])
    return float(default)


def _score_by_threshold(value: float, thresholds: list[dict[str, Any]], default: float) -> float:
    if not thresholds:
        return default
    for item in sorted(thresholds, key=lambda entry: float(entry.get("min", 0)), reverse=True):
        if value >= float(item.get("min", 0)):
            return float(item.get("score", default))
    return float(default)


def _score_by_max_threshold(value: float, thresholds: list[dict[str, Any]], default: float) -> float:
    """Score a lower-is-better numeric against ascending ``max`` ceilings.

    Returns the score of the first threshold whose ``max`` the value is at or
    below (thresholds sorted ascending). Falls through to ``default`` when the
    value exceeds every ceiling.
    """
    if not thresholds:
        return default
    for item in sorted(thresholds, key=lambda entry: float(entry.get("max", 0))):
        if value <= float(item.get("max", 0)):
            return float(item.get("score", default))
    return float(default)


# Per-column parse rules derived from check_readme.py source semantics.
# "boolean"             — True/1/yes = passes (GOOD_THINGS in the check source)
# "inverted_boolean"    — True = correctly absent (BAD_THINGS; True means the bad
#                         pattern is missing, which is good)
# "list_empty_passes"   — empty list [] = no broken links = passes
# "list_nonempty_passes"— non-empty list = has working links = passes
_README_RULES: dict[str, str] = {
    "readme.getting-help": "boolean",
    "readme.security": "boolean",
    "readme.irc-missing": "inverted_boolean",
    "readme.mailing-list-missing": "inverted_boolean",
    "readme.bad_links": "list_empty_passes",
    "readme.good_links": "list_nonempty_passes",
}

_FALSY_STR = {"", "nan", "none"}
_PASS_STR = {"true", "1", "yes"}


def _readme_sub_check_passes(rule: str, value: Any) -> bool | None:
    """Apply a parse rule to a single readme sub-check value.

    Returns None when the value is missing/uncomputable so the caller
    can exclude the check from the denominator rather than count it as a fail.
    """
    val_str = str(value).strip().lower()
    if val_str in _FALSY_STR or pd.isna(value):
        return None
    if rule in {"boolean", "inverted_boolean"}:
        return val_str in _PASS_STR
    if rule == "list_empty_passes":
        return val_str == "[]"
    if rule == "list_nonempty_passes":
        return val_str != "[]"
    return None


def _score_readme_quality(row: pd.Series) -> float:
    """Score readme quality as the proportion of passing sub-checks × 100.

    Each sub-check column has an explicit parse rule (see _README_RULES) derived
    from the upstream check_readme.py source. Sub-checks whose values are missing
    or uncomputable are excluded from the denominator rather than counted as fails.
    """
    results: list[bool] = []
    for col, rule in _README_RULES.items():
        if col not in row.index:
            continue
        outcome = _readme_sub_check_passes(rule, row.get(col))
        if outcome is not None:
            results.append(outcome)
    if not results:
        return 50.0
    return round(sum(results) / len(results) * 100, 2)


def _score_dependency_freshness(row: pd.Series) -> float:
    """Binary pass/fail: 100 if any dep-update tool is configured, 0 otherwise.

    A repo with neither Dependabot nor Renovate has no automated dependency
    hygiene — a 20-point floor (the old behaviour) inflated scores dishonestly.
    """
    has_dependabot = any(
        str(row.get(col, "")).strip().lower() in _PASS_STR
        for col in row.index
        if col.startswith("dependabot.")
    )
    has_renovate = str(row.get("renovate.configured", "")).strip().lower() in _PASS_STR
    return 100.0 if (has_dependabot or has_renovate) else 0.0


def _get_letter_grade(score: float, grades: dict[str, list[int]]) -> str:
    """Map a 0..100 composite to a letter, treating bucket bounds as half-open
    on the upper side so values like 79.5 land in B rather than falling through.
    """
    ordered = sorted(
        ((letter, bounds) for letter, bounds in grades.items() if isinstance(bounds, list) and len(bounds) == 2),
        key=lambda entry: float(entry[1][0]),
        reverse=True,
    )
    for letter, (low, _high) in ordered:
        if score >= float(low):
            return letter
    return "F"

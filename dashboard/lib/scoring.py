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
    unavailable_metrics: list[str]
    coverage: float  # 0..1 — fraction of total metric weight that was available
    config_version: str


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
    unavailable: list[str] = []

    for metric_name, metric_cfg in metrics_cfg.items():
        weight = float(metric_cfg.get("weight", 0))
        total_weight += weight

        status = metric_cfg.get("status", "unavailable")
        column = metric_cfg.get("column")
        if status != "computable" or not column or column not in columns:
            unavailable.append(metric_name)
            continue

        metric_score = _metric_score(metric_name, metric_cfg, row.get(column), row, reference_dt=reference_dt)
        per_metric[metric_name] = metric_score
        per_metric_weight[metric_name] = weight
        weighted_sum += metric_score * weight
        available_weight += weight

    composite = weighted_sum / available_weight if available_weight else 0.0
    coverage = (available_weight / total_weight) if total_weight else 0.0
    letter = _get_letter_grade(composite, letter_grades)

    return Score(
        composite=round(float(composite), 2),
        letter=letter,
        per_metric=per_metric,
        per_metric_weight=per_metric_weight,
        unavailable_metrics=unavailable,
        coverage=round(float(coverage), 4),
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
    df["score_unavailable_metrics"] = [score.unavailable_metrics for score in scores]
    df["score_coverage"] = [score.coverage for score in scores]
    df["score_config_version"] = [score.config_version for score in scores]
    return df


# ---------------------------------------------------------------------------
# Pair-restricted composite for honest A-vs-B comparison
# ---------------------------------------------------------------------------
def pair_restricted_composite(
    row_a: pd.Series,
    row_b: pd.Series,
) -> dict[str, Any]:
    """Composite scores for two repos renormalized over their shared metric set.

    Returns a dict with `score_a`, `score_b`, `metrics`, and `coverage` (the
    fraction of total metric weight represented by the intersection). When
    no metrics are shared, scores fall back to each repo's own composite
    and `metrics` is empty.
    """
    metrics_a = row_a.get("score_per_metric", {}) or {}
    metrics_b = row_b.get("score_per_metric", {}) or {}
    weights_a = row_a.get("score_per_metric_weight", {}) or {}
    weights_b = row_b.get("score_per_metric_weight", {}) or {}

    shared = sorted(set(metrics_a.keys()) & set(metrics_b.keys()))
    if not shared:
        return {
            "score_a": float(row_a.get("score_composite", 0.0)),
            "score_b": float(row_b.get("score_composite", 0.0)),
            "metrics": [],
            "coverage": 0.0,
        }

    weight_total = 0.0
    sum_a = 0.0
    sum_b = 0.0
    for metric in shared:
        # Use the weight from either side; they're config-driven so should agree.
        weight = float(weights_a.get(metric, weights_b.get(metric, 0.0)))
        if weight <= 0:
            continue
        weight_total += weight
        sum_a += float(metrics_a[metric]) * weight
        sum_b += float(metrics_b[metric]) * weight

    if weight_total == 0:
        return {
            "score_a": float(row_a.get("score_composite", 0.0)),
            "score_b": float(row_b.get("score_composite", 0.0)),
            "metrics": shared,
            "coverage": 0.0,
        }

    config = get_config("scoring")
    total_configured = sum(float(m.get("weight", 0.0)) for m in config.get("metrics", {}).values())
    coverage = (weight_total / total_configured) if total_configured else 0.0

    return {
        "score_a": round(sum_a / weight_total, 2),
        "score_b": round(sum_b / weight_total, 2),
        "metrics": shared,
        "coverage": round(coverage, 4),
    }


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

    # Generic threshold-based numeric metric handler.
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


def _score_readme_quality(row: pd.Series) -> float:
    readme_cols = [
        name
        for name in row.index
        if name.startswith("readme.") and name not in {"readme.url", "readme.length"}
    ]
    if not readme_cols:
        return 50.0

    penalty = 0
    for col in readme_cols:
        value = str(row.get(col, "")).strip().lower()
        is_passing = value in {"true", "1", "yes"}
        if not is_passing:
            penalty += 10
    return float(max(0, 100 - penalty))


def _score_dependency_freshness(row: pd.Series) -> float:
    dependabot_cols = [name for name in row.index if name.startswith("dependabot.")]
    dependabot_signals = [str(row.get(col, "")).strip().lower() in {"true", "1", "yes"} for col in dependabot_cols]
    has_dependabot = any(dependabot_signals)

    renovate_configured = str(row.get("renovate.configured", "")).strip().lower() in {"true", "1", "yes"}

    score = 0
    if has_dependabot:
        score += 60
    if renovate_configured:
        score += 40
    if score == 0:
        return 20.0
    return float(min(100, score))


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

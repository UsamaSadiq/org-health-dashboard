from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from dashboard.lib.config import get_config
from dashboard.lib.schema import LAST_PUSH_COL, parse_last_push_utc


@dataclass(frozen=True)
class Score:
    composite: float
    letter: str
    per_metric: dict[str, float]
    unavailable_metrics: list[str]
    config_version: str


DEFAULT_LETTER_GRADES = {"A": [80, 100], "B": [60, 79], "C": [40, 59], "D": [20, 39], "F": [0, 19]}


def score_row(row: pd.Series, columns: list[str]) -> Score:
    """Compute score object for a single repository row."""
    config = get_config("scoring")
    metrics_cfg = config.get("metrics", {})
    letter_grades = config.get("letter_grades", DEFAULT_LETTER_GRADES)

    weighted_sum = 0.0
    available_weight = 0.0
    per_metric: dict[str, float] = {}
    unavailable: list[str] = []

    for metric_name, metric_cfg in metrics_cfg.items():
        status = metric_cfg.get("status", "unavailable")
        column = metric_cfg.get("column")
        weight = float(metric_cfg.get("weight", 0))

        if status != "computable" or not column or column not in columns:
            unavailable.append(metric_name)
            continue

        metric_value = row.get(column)
        metric_score = _metric_score(metric_name, metric_cfg, metric_value, row)
        per_metric[metric_name] = metric_score
        weighted_sum += metric_score * weight
        available_weight += weight

    composite = weighted_sum / available_weight if available_weight else 0.0
    letter = _get_letter_grade(composite, letter_grades)

    return Score(
        composite=round(float(composite), 2),
        letter=letter,
        per_metric=per_metric,
        unavailable_metrics=unavailable,
        config_version=str(config.get("version", "unknown")),
    )


def calculate_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate composite score and letter for each row in dataframe."""
    if df.empty:
        return df

    scores = [score_row(row, list(df.columns)) for _, row in df.iterrows()]
    df = df.copy()
    df["score_composite"] = [score.composite for score in scores]
    df["score_letter"] = [score.letter for score in scores]
    df["score_per_metric"] = [score.per_metric for score in scores]
    df["score_unavailable_metrics"] = [score.unavailable_metrics for score in scores]
    df["score_config_version"] = [score.config_version for score in scores]
    return df


def _metric_score(metric_name: str, cfg: dict[str, Any], value: Any, row: pd.Series) -> float:
    if pd.isna(value):
        return float(cfg.get("default_when_missing", 50))

    if metric_name == "commit_recency":
        pushed = parse_last_push_utc(value)
        if pushed is None:
            return float(cfg.get("default_when_missing", 50))
        days = (datetime.now(timezone.utc) - pushed).days
        return _score_by_days(days, cfg.get("thresholds", []), default=0)

    if metric_name == "readme_quality":
        return _score_readme_quality(row)

    if metric_name == "ci_status":
        as_str = str(value).strip().lower()
        if as_str in {"true", "1", "yes"}:
            return 100.0
        if as_str in {"false", "0", "no"}:
            return 0.0
        return 50.0

    if metric_name == "openedx_yaml_compliance":
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
    for letter, bounds in grades.items():
        if not isinstance(bounds, list) or len(bounds) != 2:
            continue
        low, high = bounds
        if low <= score <= high:
            return letter
    return "F"

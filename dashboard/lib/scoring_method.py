"""Plain-language description of the scoring method, built from ``scoring.yaml``.

Everything the Scoring page shows comes from the config and the scored
snapshot, never from hardcoded numbers, so the explanation cannot drift from
what ``scoring.py`` actually computes.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from dashboard.lib.scoring import CONFIDENCE_DEFAULTED, CONFIDENCE_MEASURED, DEFAULT_LETTER_GRADES

SECONDS_PER_DAY = 86400

FIXED_RULES: dict[str, str] = {
    "boolean": "100 if the check passes, 0 if it fails",
    "boolean_any_dep_tool": "100 if Renovate or Dependabot is configured, 0 otherwise",
    "readme_sub_checks": "share of README sub-checks that pass (help link, security contact, "
    "no obsolete IRC or mailing-list references, no broken links, has working links), × 100",
}


def _days(seconds: float) -> str:
    days = seconds / SECONDS_PER_DAY
    return f"{days:g} day" + ("" if days == 1 else "s")


def _threshold_steps(parse_rule: str, thresholds: list[dict[str, Any]]) -> list[str]:
    if parse_rule == "threshold_days":
        ordered = sorted(thresholds, key=lambda item: int(item["days"]))
        steps = [f"≤ {item['days']} days → {item['score']}" for item in ordered]
        return steps + ["older → 0"]
    if parse_rule == "threshold_max_seconds":
        ordered = sorted(thresholds, key=lambda item: float(item["max"]))
        steps = [f"≤ {_days(float(item['max']))} → {item['score']}" for item in ordered]
        return steps + ["slower → 0"]
    ordered = sorted(thresholds, key=lambda item: float(item.get("min", 0)), reverse=True)
    return [f"≥ {item.get('min', 0):g} → {item['score']}" for item in ordered]


def rule_text(cfg: dict[str, Any]) -> str:
    parse_rule = str(cfg.get("parse_rule", ""))
    if parse_rule in FIXED_RULES:
        return FIXED_RULES[parse_rule]
    thresholds = cfg.get("thresholds") or []
    if not thresholds:
        return parse_rule or "not specified"
    return "; ".join(_threshold_steps(parse_rule, thresholds))


def letter_bands(config: dict[str, Any]) -> list[dict[str, Any]]:
    grades = config.get("letter_grades") or DEFAULT_LETTER_GRADES
    ordered = sorted(grades.items(), key=lambda item: float(item[1][0]), reverse=True)
    return [{"grade": letter, "from": low, "to": high} for letter, (low, high) in ordered]


def _confidence_counts(scored: pd.DataFrame) -> dict[str, Counter]:
    counts: dict[str, Counter] = {}
    if "score_metric_confidence" not in scored.columns:
        return counts
    for confidence in scored["score_metric_confidence"]:
        if not isinstance(confidence, dict):
            continue
        for metric, state in confidence.items():
            counts.setdefault(metric, Counter())[state] += 1
    return counts


def _percent(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def metric_rows(config: dict[str, Any], scored: pd.DataFrame) -> list[dict[str, Any]]:
    """One row per configured metric, with its weight share and live measured coverage."""
    metrics = config.get("metrics", {})
    total_weight = sum(float(cfg.get("weight", 0)) for cfg in metrics.values()) or 1.0
    counts = _confidence_counts(scored)
    repos = len(scored)
    rows = []
    for name, cfg in metrics.items():
        metric_counts = counts.get(name, Counter())
        rows.append(
            {
                "metric": name.replace("_", " "),
                "category": str(cfg.get("category", "")),
                "weight_pct": round(float(cfg.get("weight", 0)) / total_weight * 100, 1),
                "source": str(cfg.get("column", "")),
                "rule": rule_text(cfg),
                "missing_scores_as": cfg.get("default_when_missing", 50),
                "measured_pct": _percent(metric_counts[CONFIDENCE_MEASURED], repos),
                "defaulted_pct": _percent(metric_counts[CONFIDENCE_DEFAULTED], repos),
                "chaoss_metric": str(cfg.get("chaoss_metric", "")),
                "provisional": bool(cfg.get("provisional", False)),
                "limitation": str(cfg.get("limitation", "")),
            }
        )
    return rows

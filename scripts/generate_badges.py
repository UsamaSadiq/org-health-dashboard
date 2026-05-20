#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from dashboard.lib.data import load_snapshot
from dashboard.lib.scoring import calculate_scores

ROOT = Path(__file__).resolve().parents[1]
BADGES_DIR = ROOT / "dashboards" / "badges"

GRADE_COLOR = {
    "A": "#16a34a",
    "B": "#65a30d",
    "C": "#ca8a04",
    "D": "#ea580c",
    "F": "#dc2626",
}


def _svg(repo: str, grade: str, score: float) -> str:
    color = GRADE_COLOR.get(grade, "#475569")
    label = f"repo health {grade} ({score:.1f})"
    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"280\" height=\"20\" role=\"img\" aria-label=\"{label}\">\n  <rect width=\"190\" height=\"20\" fill=\"#334155\"/>\n  <rect x=\"190\" width=\"90\" height=\"20\" fill=\"{color}\"/>\n  <text x=\"95\" y=\"14\" fill=\"#fff\" text-anchor=\"middle\" font-family=\"Arial\" font-size=\"11\">{repo}</text>\n  <text x=\"235\" y=\"14\" fill=\"#fff\" text-anchor=\"middle\" font-family=\"Arial\" font-size=\"11\">{grade} {score:.1f}</text>\n</svg>\n"""


def main() -> int:
    df = calculate_scores(load_snapshot())
    if df.empty:
        print("No snapshot data available.")
        return 1

    BADGES_DIR.mkdir(parents=True, exist_ok=True)
    for row in df[["repo_name", "score_letter", "score_composite"]].itertuples(index=False):
        safe_repo = str(row.repo_name).replace("/", "__")
        target = BADGES_DIR / f"{safe_repo}.svg"
        target.write_text(_svg(str(row.repo_name), str(row.score_letter), float(row.score_composite)), encoding="utf-8")

    print(f"Generated badge SVGs in: {BADGES_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import pandas as pd

from dashboard.lib.data import load_snapshot
from dashboard.lib.scoring import calculate_scores

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "dashboards" / "cards"
YEAR_REVIEW_PATH = CARDS_DIR / "year-in-review.html"
EMBED_DIR = CARDS_DIR / "embeds"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _year_review_html(df: pd.DataFrame) -> str:
    top = df.sort_values("score_composite", ascending=False).head(10)
    rows = "\n".join(
        f"<tr><td>{row.repo_name}</td><td>{row.score_composite:.1f}</td><td>{row.score_letter}</td></tr>"
        for row in top.itertuples()
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta property=\"og:title\" content=\"Open edX Repo Health Year in Review\" />
  <meta property=\"og:description\" content=\"Top repositories by composite score\" />
  <title>Open edX Repo Health Year in Review</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; color: #0f172a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 0.5rem; text-align: left; }}
  </style>
</head>
<body>
  <h1>Open edX Repo Health Year in Review</h1>
  <p>Top repositories by composite score from the latest snapshot.</p>
  <table>
    <thead><tr><th>Repository</th><th>Score</th><th>Grade</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""


def _embed_html(repo_name: str, score: float, grade: str) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta property=\"og:title\" content=\"{repo_name} health card\" />
  <meta property=\"og:description\" content=\"Score {score:.1f}, grade {grade}\" />
  <title>{repo_name} health card</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .card {{ border: 1px solid #e2e8f0; border-radius: 12px; padding: 1rem; width: 320px; }}
    .repo {{ font-weight: 700; margin-bottom: 0.5rem; }}
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"repo\">{repo_name}</div>
    <div>Composite score: {score:.1f}</div>
    <div>Grade: {grade}</div>
  </div>
</body>
</html>
"""


def main() -> int:
    df = calculate_scores(load_snapshot())
    if df.empty:
        print("No snapshot data available.")
        return 1

    _write(YEAR_REVIEW_PATH, _year_review_html(df))

    for row in df[["repo_name", "score_composite", "score_letter"]].itertuples(index=False):
        file_name = str(row.repo_name).replace("/", "__") + ".html"
        _write(EMBED_DIR / file_name, _embed_html(str(row.repo_name), float(row.score_composite), str(row.score_letter)))

    print(f"Generated year-in-review card: {YEAR_REVIEW_PATH}")
    print(f"Generated embed cards: {EMBED_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

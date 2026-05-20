from __future__ import annotations

import pandas as pd


def repo_grade_table(df: pd.DataFrame) -> pd.DataFrame:
    return df[["repo_name", "score_composite", "score_letter"]].sort_values("score_composite", ascending=False)

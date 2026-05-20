from __future__ import annotations

import pandas as pd
import plotly.express as px

GRADE_COLORS = {"A": "#166534", "B": "#15803D", "C": "#CA8A04", "D": "#EA580C", "F": "#DC2626"}


def grade_histogram(df: pd.DataFrame):
    counts = df["score_letter"].value_counts().reindex(["A", "B", "C", "D", "F"]).fillna(0)
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        color=counts.index,
        color_discrete_map=GRADE_COLORS,
        labels={"x": "Grade", "y": "Repositories"},
        title="Grade Distribution",
    )
    return fig

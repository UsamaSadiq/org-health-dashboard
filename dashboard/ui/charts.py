from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.ui.theme import (
    ACCENT,
    BORDER,
    CATEGORICAL,
    FAIL,
    GRADE_COLORS,
    MUTED,
    PASS,
    PRIMARY,
    WARN,
)

GRADE_ORDER = ["A", "B", "C", "D", "F"]


def grade_histogram(df: pd.DataFrame) -> go.Figure:
    counts = df["score_letter"].value_counts().reindex(GRADE_ORDER).fillna(0).astype(int)
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        color=counts.index,
        color_discrete_map=GRADE_COLORS,
        category_orders={"x": GRADE_ORDER},
        labels={"x": "Grade", "y": "Repositories"},
        title="Grade distribution",
    )
    fig.update_layout(showlegend=False, bargap=0.35)
    return fig


def category_pass_rate_bar(category_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        category_df,
        x="category",
        y="pass_rate",
        title="Per-category pass rate",
        range_y=[0, 100],
        labels={"category": "", "pass_rate": "Pass rate (%)"},
    )
    fig.update_traces(marker_color=PRIMARY)
    return fig


def top_failing_bar(fail_df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        fail_df,
        x="check",
        y="failing",
        title="Top failing checks",
        labels={"check": "", "failing": "Repos failing"},
        custom_data=["check"],
    )
    fig.update_traces(marker_color=FAIL)
    fig.update_layout(xaxis={"tickangle": -30})
    return fig


def sparkline(points_df: pd.DataFrame, y_col: str = "pass_rate", title: str | None = None) -> go.Figure:
    fig = px.line(points_df, x="date", y=y_col, title=title)
    fig.update_traces(line={"color": ACCENT, "width": 2})
    fig.update_layout(
        showlegend=False,
        margin={"l": 8, "r": 8, "t": 28, "b": 8},
        xaxis={"showgrid": False, "title": ""},
        yaxis={"showgrid": False, "title": "", "range": [0, 100]},
        height=160,
    )
    return fig

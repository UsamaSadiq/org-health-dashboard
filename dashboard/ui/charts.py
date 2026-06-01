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
    GRADE_TEXT_COLORS,
    MUTED,
    PASS,
    PRIMARY,
    SURFACE_ALT,
    TEXT,
    WARN,
)

GRADE_ORDER = ["A", "B", "C", "D", "F"]


def _summary_annotation(fig: go.Figure, text: str) -> None:
    fig.add_annotation(
        x=0, y=1.12, xref="paper", yref="paper",
        text=f"<span style='color:{MUTED};font-size:12px;'>{text}</span>",
        showarrow=False, align="left", xanchor="left",
    )


def grade_histogram(df: pd.DataFrame) -> go.Figure:
    counts = df["score_letter"].value_counts().reindex(GRADE_ORDER).fillna(0).astype(int)
    total = int(counts.sum())
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
    if total:
        ab = int(counts.get("A", 0) + counts.get("B", 0))
        _summary_annotation(fig, f"{ab}/{total} repos at grade B or better")
    return fig


def grade_ribbon(df: pd.DataFrame) -> go.Figure:
    """A single thin full-width horizontal stacked bar showing grade mix."""
    counts = df["score_letter"].value_counts().reindex(GRADE_ORDER).fillna(0).astype(int)
    total = int(counts.sum()) or 1

    fig = go.Figure()
    for letter in GRADE_ORDER:
        n = int(counts.get(letter, 0))
        if n == 0:
            continue
        pct = 100.0 * n / total
        label = f"{letter} · {n}" if pct >= 6 else (letter if pct >= 3 else "")
        fig.add_trace(
            go.Bar(
                y=["Grades"],
                x=[n],
                name=letter,
                orientation="h",
                marker={"color": GRADE_COLORS[letter], "line": {"width": 0}},
                text=[label],
                textposition="inside",
                insidetextanchor="middle",
                textfont={"color": GRADE_TEXT_COLORS[letter], "size": 13, "family": "Inter"},
                hovertemplate=f"<b>Grade {letter}</b><br>{n} repos ({pct:.1f}%)<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="stack",
        showlegend=False,
        height=64,
        margin={"l": 0, "r": 0, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"visible": False, "fixedrange": True},
        bargap=0,
    )
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
    fig.update_traces(marker_color=PRIMARY, marker_line_width=0)
    fig.update_layout(bargap=0.3)
    if not category_df.empty:
        avg = float(category_df["pass_rate"].mean())
        _summary_annotation(fig, f"avg {avg:.0f}% pass · {len(category_df)} categories")
    return fig


def top_failing_bar(fail_df: pd.DataFrame) -> go.Figure:
    """Lollipop chart of top failing checks."""
    if fail_df.empty:
        fig = go.Figure()
        fig.update_layout(title="Top failing checks")
        return fig

    df = fail_df.copy()
    df = df.iloc[::-1]  # so largest is on top
    checks = df["check"].astype(str).tolist()
    values = df["failing"].astype(int).tolist()

    fig = go.Figure()

    # Stems
    for check, val in zip(checks, values):
        fig.add_shape(
            type="line",
            x0=0, x1=val, y0=check, y1=check,
            line={"color": BORDER, "width": 2},
            layer="below",
        )

    # Dots
    fig.add_trace(
        go.Scatter(
            x=values,
            y=checks,
            mode="markers",
            marker={"color": PRIMARY, "size": 14, "line": {"color": SURFACE_ALT, "width": 2}},
            customdata=checks,
            hovertemplate="<b>%{y}</b><br>%{x} repos failing<extra></extra>",
        )
    )

    fig.update_layout(
        title="Top failing checks",
        showlegend=False,
        height=max(280, 32 * len(checks) + 80),
        xaxis={"title": "Repos failing", "rangemode": "tozero"},
        yaxis={"title": "", "automargin": True},
    )
    total_fail = int(df["failing"].sum())
    _summary_annotation(fig, f"{total_fail} failures across {len(checks)} checks")
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

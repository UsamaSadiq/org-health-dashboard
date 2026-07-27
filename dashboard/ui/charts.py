from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.ui.theme import GRADE_ORDER, palette


def _summary_annotation(fig: go.Figure, text: str) -> None:
    """Add a centered caption above the plot. Charts drop their redundant
    Plotly title (the surrounding tab already names them), so this sits in the
    reserved top margin without colliding with a title."""
    fig.add_annotation(
        x=0.5, y=1.10, xref="paper", yref="paper",
        text=f"<span style='color:{palette().muted};font-size:12px;'>{text}</span>",
        showarrow=False, xanchor="center",
    )


def grade_histogram(df: pd.DataFrame) -> go.Figure:
    p = palette()
    counts = df["score_letter"].value_counts().reindex(GRADE_ORDER).fillna(0).astype(int)
    total = int(counts.sum())
    values = counts.values.tolist()
    pcts = [(100.0 * v / total if total else 0.0) for v in values]
    bar_labels = [f"<b>{v}</b>  {p:.0f}%" for v, p in zip(values, pcts)]

    fig = go.Figure(
        go.Bar(
            x=list(counts.index),
            y=values,
            marker={"color": [p.grade_colors[g] for g in counts.index], "line": {"width": 0}},
            text=bar_labels,
            textposition="outside",
            textfont={"size": 13, "color": p.text},
            cliponaxis=False,
            customdata=pcts,
            hovertemplate=(
                "<b>Grade %{x}</b><br>%{y} repositories"
                "<br>%{customdata:.1f}% of graded repos<extra></extra>"
            ),
        )
    )

    ymax = max(values) if values else 1
    fig.update_layout(
        showlegend=False,
        bargap=0.35,
        margin={"l": 12, "r": 12, "t": 48, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "Grade", "fixedrange": True, "automargin": True},
        yaxis={"title": "Repositories", "fixedrange": True, "automargin": True,
               "range": [0, ymax * 1.18 if ymax else 1]},
        hoverlabel={"bgcolor": p.surface_alt, "bordercolor": p.border},
    )
    if total:
        ab = int(counts.get("A", 0) + counts.get("B", 0))
        _summary_annotation(fig, f"{ab}/{total} repos ({100 * ab / total:.0f}%) at grade B or better")
    return fig


def grade_ribbon(df: pd.DataFrame) -> go.Figure:
    """A single thin full-width horizontal stacked bar showing grade mix."""
    p = palette()
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
                marker={"color": p.grade_colors[letter], "line": {"width": 0}},
                text=[label],
                textposition="inside",
                insidetextanchor="middle",
                textfont={"color": p.grade_text_colors[letter], "size": 13, "family": "Inter"},
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
    p = palette()
    fig = px.bar(
        category_df,
        x="category",
        y="pass_rate",
        range_y=[0, 100],
        labels={"category": "", "pass_rate": "Pass rate (%)"},
    )
    fig.update_traces(
        marker_color=p.primary,
        marker_line_width=0,
        text=[f"{v:.0f}%" for v in category_df["pass_rate"]] if not category_df.empty else None,
        textposition="outside",
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{y:.1f}% of checks passing<extra></extra>",
    )
    fig.update_layout(
        bargap=0.3,
        margin={"l": 8, "r": 8, "t": 48, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"fixedrange": True},
        yaxis={"fixedrange": True},
        hoverlabel={"bgcolor": p.surface_alt, "bordercolor": p.border},
    )
    if not category_df.empty:
        avg = float(category_df["pass_rate"].mean())
        _summary_annotation(fig, f"avg {avg:.0f}% pass · {len(category_df)} categories")
    return fig


def top_failing_bar(fail_df: pd.DataFrame) -> go.Figure:
    """Lollipop chart of top failing checks."""
    p = palette()
    if fail_df.empty:
        return go.Figure()

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
            line={"color": p.border, "width": 2},
            layer="below",
        )

    # Dots
    fig.add_trace(
        go.Scatter(
            x=values,
            y=checks,
            mode="markers",
            marker={"color": p.primary, "size": 14, "line": {"color": p.surface_alt, "width": 2}},
            customdata=checks,
            hovertemplate="<b>%{y}</b><br>%{x} repos failing<extra></extra>",
        )
    )

    fig.update_layout(
        showlegend=False,
        height=max(280, 32 * len(checks) + 80),
        margin={"t": 48},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "Repos failing", "rangemode": "tozero"},
        yaxis={"title": "", "automargin": True},
        hoverlabel={"bgcolor": p.surface_alt, "bordercolor": p.border},
    )
    total_fail = int(df["failing"].sum())
    _summary_annotation(fig, f"{total_fail} failures across {len(checks)} checks")
    return fig


def sparkline(points_df: pd.DataFrame, y_col: str = "pass_rate", title: str | None = None) -> go.Figure:
    p = palette()
    fig = px.line(points_df, x="date", y=y_col, title=title)
    fig.update_traces(line={"color": p.accent, "width": 2})
    fig.update_layout(
        showlegend=False,
        margin={"l": 8, "r": 8, "t": 28, "b": 8},
        xaxis={"showgrid": False, "title": ""},
        yaxis={"showgrid": False, "title": "", "range": [0, 100]},
        height=160,
    )
    return fig

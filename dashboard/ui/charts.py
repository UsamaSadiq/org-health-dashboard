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


def metric_score_bar(repo_row) -> go.Figure:
    """Per-metric scores for one repository, with unmeasured metrics marked.

    Replaces the radar chart, which was actively misleading: it plotted
    unavailable metrics at radius 100, so a repository with five of nine metrics
    looked close to perfect. A radar also cannot express three states, forces the
    reader to compare areas rather than lengths, overprinted its own radial tick
    labels, and carried a single-series legend.

    Three visual states, matching ``score_metric_confidence``:

    - **measured** — bar coloured by score.
    - **defaulted** — bar drawn at the fallback value, muted, labelled
      ``default (50)``. The column exists but held no usable value.
    - **unavailable** — no bar at all, labelled ``not collected``. Drawing
      nothing is the point; any length here is a claim we cannot support.
    """
    p = palette()

    per_metric = dict(repo_row.get("score_per_metric", {}) or {})
    confidence = dict(repo_row.get("score_metric_confidence", {}) or {})
    unavailable = sorted(set(repo_row.get("score_unavailable_metrics", []) or []))
    weights = dict(repo_row.get("score_per_metric_weight", {}) or {})

    # Measured first, descending by score, then defaulted, then not collected —
    # so the eye lands on real signal and the gaps read as a block.
    def _rank(name: str) -> tuple[int, float]:
        state = confidence.get(name, "measured" if name in per_metric else "unavailable")
        order = {"measured": 0, "defaulted": 1, "unavailable": 2}.get(state, 3)
        return (order, -float(per_metric.get(name, 0.0)))

    names = sorted(set(per_metric) | set(unavailable), key=_rank)
    if not names:
        return go.Figure()

    values, colors, labels, hovers = [], [], [], []
    for name in names:
        state = confidence.get(name, "measured" if name in per_metric else "unavailable")
        score = float(per_metric.get(name, 0.0))
        weight = weights.get(name)
        weight_text = f"{weight:.0%} weight" if isinstance(weight, (int, float)) else "excluded"

        if state == "unavailable":
            values.append(0.0)
            colors.append("rgba(0,0,0,0)")
            labels.append("not collected")
            hovers.append(f"<b>{name}</b><br>not collected in this snapshot<extra></extra>")
        elif state == "defaulted":
            values.append(score)
            colors.append(_muted_fill(p))
            labels.append(f"default ({score:.0f})")
            hovers.append(
                f"<b>{name}</b><br>no usable value; scored at the default "
                f"{score:.0f}<br>{weight_text}<extra></extra>"
            )
        else:
            values.append(score)
            colors.append(p.grade_colors[_letter_for(score)])
            labels.append(f"{score:.0f}")
            hovers.append(f"<b>{name}</b><br>{score:.0f} / 100<br>{weight_text}<extra></extra>")

    # Reverse so the highest-ranked metric sits at the top of a horizontal chart.
    names, values, colors, labels, hovers = (
        list(reversed(x)) for x in (names, values, colors, labels, hovers)
    )

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colors, "line": {"width": 0}},
            text=labels,
            textposition="outside",
            textfont={"size": 12, "color": p.muted},
            cliponaxis=False,
            hovertemplate=hovers,
        )
    )
    fig.update_layout(
        showlegend=False,
        height=max(260, 34 * len(names) + 70),
        margin={"l": 8, "r": 64, "t": 48, "b": 32},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"title": "Score", "range": [0, 108], "fixedrange": True, "automargin": True},
        yaxis={"title": "", "fixedrange": True, "automargin": True},
        hoverlabel={"bgcolor": p.surface_alt, "bordercolor": p.border},
    )

    measured = sum(1 for n in names if confidence.get(n, "measured") == "measured")
    _summary_annotation(fig, f"{measured} of {len(names)} metrics measured")
    return fig


def _letter_for(score: float) -> str:
    """Grade band for a 0-100 metric score, for colouring a single bar."""
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


def _muted_fill(p) -> str:
    """Low-emphasis fill for a defaulted bar, derived from the active palette."""
    value = p.muted.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, 0.35)"


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

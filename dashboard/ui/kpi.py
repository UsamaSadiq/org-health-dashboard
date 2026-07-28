from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.lib.schema import LAST_PUSH_COL, parse_last_push_utc
from dashboard.ui.theme import palette


def _tint(hex_color: str, alpha: float = 0.12) -> str:
    """Translucent version of a grade colour, for the gauge's background bands."""
    value = hex_color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _delta_str(value: float | int | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        if abs(value) < 0.05:
            return None
        return f"{value:+.1f}"
    if value == 0:
        return None
    return f"{value:+d}"


def _letter_from_score(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


def _gauge_figure(avg: float, measured_weight: float | None = None) -> go.Figure:
    """Org-average gauge.

    `measured_weight` (0..1) is the fraction of total metric weight genuinely
    measured rather than filled from `default_when_missing`. When it is below 1
    the gauge says so beneath the grade: presenting a confident composite
    without that caveat was the single least defensible thing on the page.
    """
    p = palette()
    letter = _letter_from_score(avg)
    color = p.grade_colors.get(letter, p.primary)

    # mode="gauge" (no auto number) so the value and grade can be placed as
    # separate, non-overlapping annotations inside the arc.
    fig = go.Figure(
        go.Indicator(
            mode="gauge",
            value=round(avg, 1),
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": p.border, "tickfont": {"color": p.muted}},
                "bar": {"color": color, "thickness": 0.25},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 20], "color": _tint(p.grade_colors["F"])},
                    {"range": [20, 40], "color": _tint(p.grade_colors["D"])},
                    {"range": [40, 60], "color": _tint(p.grade_colors["C"])},
                    {"range": [60, 80], "color": _tint(p.grade_colors["B"])},
                    {"range": [80, 100], "color": _tint(p.grade_colors["A"], 0.16)},
                ],
                "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": avg},
            },
            domain={"x": [0, 1], "y": [0.24, 1]},
        )
    )

    # Value above, grade below — comfortably separated in the arc's bowl.
    fig.add_annotation(
        x=0.5, y=0.34, xref="paper", yref="paper", showarrow=False,
        text=f"<b style='font-size:42px;color:{p.text};'>{avg:.1f}</b>",
    )
    fig.add_annotation(
        x=0.5, y=0.17, xref="paper", yref="paper", showarrow=False,
        text=f"<b style='font-size:22px;color:{color};'>Grade {letter}</b>",
    )

    # The caveat belongs on the number, not in a tile three columns away. On the
    # live snapshot this reads 50%, i.e. half the composite is
    # default_when_missing rather than measurement.
    if measured_weight is not None and measured_weight < 0.999:
        fig.add_annotation(
            x=0.5, y=0.02, xref="paper", yref="paper", showarrow=False,
            text=(
                f"<span style='font-size:12px;color:{p.warn};'>"
                f"based on {measured_weight:.0%} of metric weight</span>"
            ),
        )

    fig.update_layout(
        margin={"l": 28, "r": 28, "t": 12, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
    )
    return fig


def _count_stale(df: pd.DataFrame, stale_hours: int) -> int:
    if LAST_PUSH_COL not in df.columns:
        return 0
    threshold = datetime.now(timezone.utc).timestamp() - (stale_hours * 3600)
    count = 0
    for value in df[LAST_PUSH_COL]:
        pushed = parse_last_push_utc(value)
        if pushed is None:
            continue
        ts = pushed.replace(tzinfo=timezone.utc).timestamp() if pushed.tzinfo is None else pushed.timestamp()
        if ts < threshold:
            count += 1
    return count


def _sparkline(values: list[float]) -> go.Figure | None:
    p = palette()
    if not values or len(values) < 2:
        return None
    fig = go.Figure(
        go.Scatter(
            y=values,
            mode="lines",
            line={"color": p.accent, "width": 2},
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        height=40,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False},
        yaxis={"visible": False},
        showlegend=False,
    )
    return fig


def _load_org_avg_history(days: int = 30) -> list[float]:
    try:
        from dashboard.lib.scoring import calculate_scores
        from dashboard.lib.trends import load_history
        snaps = load_history(days=days)
    except Exception:
        return []
    out: list[float] = []
    for snap in snaps[-days:]:
        try:
            scored = calculate_scores(snap.df)
            out.append(float(scored["score_composite"].mean()))
        except Exception:
            continue
    return out


def render_kpi_strip(
    df: pd.DataFrame,
    baseline: pd.DataFrame | None = None,
    *,
    snapshot_date: date | None = None,
    stale_hours: int = 168,
) -> None:
    """Render the hero KPI block. If `baseline` is supplied (an earlier
    snapshot frame with the same shape), each tile shows a delta vs. that point.
    """
    total = len(df)
    avg = float(df["score_composite"].mean()) if total else 0.0
    grade_a = int((df["score_letter"] == "A").sum())
    grade_f = int((df["score_letter"] == "F").sum())
    stale = _count_stale(df, stale_hours)
    avg_coverage = float(df["score_coverage"].mean()) if "score_coverage" in df.columns and total else 0.0
    # Fraction of weight actually measured (see dashboard/lib/scoring.py). Falls
    # back to coverage for frames scored before WP-4 added the column.
    if "score_measured_weight" in df.columns and total:
        avg_measured = float(df["score_measured_weight"].mean())
    else:
        avg_measured = avg_coverage

    deltas: dict[str, str | None] = {
        "total": None, "avg": None, "a": None, "f": None, "stale": None,
    }
    if baseline is not None and not baseline.empty:
        b_total = len(baseline)
        b_avg = float(baseline["score_composite"].mean()) if b_total else 0.0
        b_a = int((baseline["score_letter"] == "A").sum())
        b_f = int((baseline["score_letter"] == "F").sum())
        b_stale = _count_stale(baseline, stale_hours)
        deltas["total"] = _delta_str(total - b_total)
        deltas["avg"] = _delta_str(avg - b_avg)
        deltas["a"] = _delta_str(grade_a - b_a)
        deltas["f"] = _delta_str(grade_f - b_f)
        deltas["stale"] = _delta_str(stale - b_stale)

    hero_col, tiles_col = st.columns([2, 3], gap="large")

    with hero_col:
        st.markdown(
            "<div style='font-size:0.95rem;color:var(--color-muted);"
            "font-weight:600;letter-spacing:.04em;text-transform:uppercase;"
            "margin-bottom:6px;'>Org Health</div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            _gauge_figure(avg, measured_weight=avg_measured),
            width="stretch",
            config={"displayModeBar": False},
        )
        snap = snapshot_date.isoformat() if snapshot_date else "unknown"
        st.caption(f"{total} repos · snapshot {snap}")

    with tiles_col:
        history = _load_org_avg_history(30)
        # Uniform 2x2 grid of equal-width tiles. Average score is intentionally
        # omitted here — it's the gauge's central value (with the trend shown by
        # the sparkline below), so a separate tile would just duplicate it.
        row1 = st.columns(2)
        row2 = st.columns(2)
        row1[0].metric("Grade A", grade_a, delta=deltas["a"])
        row1[1].metric("Grade F", grade_f, delta=deltas["f"], delta_color="inverse")
        row2[0].metric("Stale repos", stale, delta=deltas["stale"], delta_color="inverse")
        row2[1].metric(
            "Score measured",
            f"{avg_measured:.0%}",
            help="Fraction of total metric weight computed from real values. The "
                 "remainder falls back to default_when_missing (50), so it moves "
                 "no repository up or down relative to any other. "
                 f"Columns present in the snapshot: {avg_coverage:.0%}.",
        )

        spark = _sparkline(history)
        if spark is not None:
            st.plotly_chart(
                spark,
                width="stretch",
                config={"displayModeBar": False},
            )
            st.caption(f"Org-average composite · last {len(history)} snapshots")

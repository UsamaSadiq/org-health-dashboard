from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.lib.schema import LAST_PUSH_COL, parse_last_push_utc
from dashboard.ui.theme import (
    ACCENT,
    BORDER,
    FAIL,
    GRADE_COLORS,
    MUTED,
    PASS,
    PRIMARY,
    SURFACE_ALT,
    TEXT,
    WARN,
)


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


def _gauge_figure(avg: float, total: int, snapshot_date: date | None) -> go.Figure:
    letter = _letter_from_score(avg)
    color = GRADE_COLORS.get(letter, PRIMARY)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(avg, 1),
            number={"font": {"size": 44, "color": TEXT}, "suffix": ""},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": BORDER, "tickfont": {"color": MUTED}},
                "bar": {"color": color, "thickness": 0.25},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 20], "color": "rgba(185, 28, 28, 0.12)"},
                    {"range": [20, 40], "color": "rgba(234, 88, 12, 0.12)"},
                    {"range": [40, 60], "color": "rgba(217, 119, 6, 0.12)"},
                    {"range": [60, 80], "color": "rgba(22, 163, 74, 0.12)"},
                    {"range": [80, 100], "color": "rgba(21, 128, 61, 0.16)"},
                ],
                "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": avg},
            },
            domain={"x": [0, 1], "y": [0.15, 1]},
        )
    )

    fig.add_annotation(
        x=0.5, y=0.18, xref="paper", yref="paper",
        text=f"<b style='font-size:34px;color:{color};'>{letter}</b>",
        showarrow=False,
    )

    snap = snapshot_date.isoformat() if snapshot_date else "unknown"
    fig.add_annotation(
        x=0.5, y=0.02, xref="paper", yref="paper",
        text=f"<span style='color:{MUTED};font-size:12px;'>{total} repos · snapshot {snap}</span>",
        showarrow=False,
    )

    fig.update_layout(
        margin={"l": 12, "r": 12, "t": 12, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=280,
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
    if not values or len(values) < 2:
        return None
    fig = go.Figure(
        go.Scatter(
            y=values,
            mode="lines",
            line={"color": ACCENT, "width": 2},
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
            _gauge_figure(avg, total, snapshot_date),
            width="stretch",
            config={"displayModeBar": False},
        )

    with tiles_col:
        history = _load_org_avg_history(30)
        row1 = st.columns(2)
        row2 = st.columns(3)
        row1[0].metric("Grade A", grade_a, delta=deltas["a"])
        row1[1].metric("Grade F", grade_f, delta=deltas["f"], delta_color="inverse")
        row2[0].metric("Average score", f"{avg:.1f}", delta=deltas["avg"])
        row2[1].metric("Stale repos", stale, delta=deltas["stale"], delta_color="inverse")
        row2[2].metric(
            "Score coverage",
            f"{avg_coverage:.0%}",
            help="Fraction of total metric weight computable from this snapshot. "
                 "Metrics whose columns are absent from the snapshot are excluded.",
        )

        spark = _sparkline(history)
        if spark is not None:
            st.plotly_chart(
                spark,
                width="stretch",
                config={"displayModeBar": False},
            )
            st.caption(f"Org-average composite · last {len(history)} snapshots")

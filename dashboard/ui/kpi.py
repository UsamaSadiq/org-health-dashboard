from __future__ import annotations

import pandas as pd
import streamlit as st


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


def render_kpi_strip(df: pd.DataFrame, baseline: pd.DataFrame | None = None) -> None:
    """Render the four primary KPI tiles. If `baseline` is supplied (an earlier
    snapshot frame with the same shape), each tile shows a delta vs. that point.
    """
    total = len(df)
    avg = float(df["score_composite"].mean()) if total else 0.0
    grade_a = int((df["score_letter"] == "A").sum())
    grade_f = int((df["score_letter"] == "F").sum())

    deltas: dict[str, str | None] = {"total": None, "avg": None, "a": None, "f": None}
    if baseline is not None and not baseline.empty:
        b_total = len(baseline)
        b_avg = float(baseline["score_composite"].mean()) if b_total else 0.0
        b_a = int((baseline["score_letter"] == "A").sum())
        b_f = int((baseline["score_letter"] == "F").sum())
        deltas["total"] = _delta_str(total - b_total)
        deltas["avg"] = _delta_str(avg - b_avg)
        deltas["a"] = _delta_str(grade_a - b_a)
        deltas["f"] = _delta_str(grade_f - b_f)

    cols = st.columns(4)
    cols[0].metric("Total repos", total, delta=deltas["total"], delta_color="off")
    cols[1].metric("Average score", f"{avg:.1f}", delta=deltas["avg"])
    cols[2].metric("Grade A", grade_a, delta=deltas["a"])
    # For F-count: more failures is bad → inverse delta color.
    cols[3].metric("Grade F", grade_f, delta=deltas["f"], delta_color="inverse")

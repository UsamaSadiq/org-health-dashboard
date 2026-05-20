from __future__ import annotations

import pandas as pd
import streamlit as st


def render_kpi_strip(df: pd.DataFrame) -> None:
    cols = st.columns(4)
    cols[0].metric("Total Repos", len(df))
    cols[1].metric("Average Score", f"{df['score_composite'].mean():.1f}")
    cols[2].metric("Grade A", int((df['score_letter'] == 'A').sum()))
    cols[3].metric("Grade F", int((df['score_letter'] == 'F').sum()))

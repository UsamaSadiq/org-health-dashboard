from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from urllib.parse import quote

from dashboard.lib.data import load_snapshot
from dashboard.lib.linking import serialize_state
from dashboard.lib.scoring import calculate_scores


def render() -> None:
    st.title("Failing Checks")

    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No data available.")
        return

    check_cols = [
        col
        for col in df.columns
        if "." in col and not col.startswith("github.") and not col.startswith("language_bytes.")
    ]
    if not check_cols:
        st.warning("No check columns found in snapshot.")
        return

    rows = []
    for check in check_cols:
        failing_mask = df[check].astype(str).str.lower().isin(["false", "0", "no", "fail", "failing"])
        count = int(failing_mask.sum())
        if count > 0:
            rows.append({"check": check, "fail_count": count})

    if not rows:
        st.success("No failing checks detected.")
        return

    fail_df = pd.DataFrame(rows).sort_values("fail_count", ascending=False)

    st.subheader("Failing checks distribution")
    fig = px.bar(
        fail_df,
        x="check",
        y="fail_count",
        color="check",
        custom_data=["check"],
        title="Failing checks by count",
    )

    selection = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        selection_mode=["points"],
    )

    selected_check = None
    if selection and isinstance(selection, dict):
        selected = selection.get("selection", {}).get("points", [])
        if selected:
            selected_check = selected[0].get("customdata", [None])[0]

    filtered = df
    if selected_check:
        fail_mask = filtered[selected_check].astype(str).str.lower().isin(["false", "0", "no", "fail", "failing"])
        filtered = filtered[fail_mask]
        st.info(f"Filtered by selected bar: {selected_check}")

    result = filtered[["repo_name", "score_composite", "score_letter"]].sort_values("score_composite")
    result = result.copy()
    result["repo_link"] = result["repo_name"].map(
        lambda repo: f"https://share.streamlit.io/?tab=detail&repo={quote(str(repo), safe='')}"
    )
    st.dataframe(
        result,
        use_container_width=True,
        column_config={"repo_link": st.column_config.LinkColumn("Repo Detail Link")},
    )
    share_query = serialize_state({"tab": "failing-checks", "category": selected_check or ""})
    st.text_input("Copy link to this view", value=f"https://share.streamlit.io/?{share_query}", key="failing_share_link")


render()

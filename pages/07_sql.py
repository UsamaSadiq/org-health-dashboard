from __future__ import annotations

import duckdb
import streamlit as st

from dashboard.lib.data import load_snapshot
from dashboard.lib.scoring import calculate_scores


def render() -> None:
    st.title("Ad-hoc SQL")
    st.caption("Phase 2 feature. Read-only SQL over current snapshot.")

    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No snapshot available.")
        return

    query = st.text_area("SQL query", value="SELECT repo_name, score_letter FROM df LIMIT 20")

    if st.button("Run query"):
        try:
            con = duckdb.connect()
            con.register("snapshot", df)
            sql = query.replace(" FROM df", " FROM snapshot")
            result = con.execute(sql).fetch_df()
            st.dataframe(result, use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Query failed: {exc}")


render()

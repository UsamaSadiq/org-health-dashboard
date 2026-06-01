from __future__ import annotations

import duckdb
import streamlit as st

from dashboard.data import load_snapshot
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.sql import UnsafeQueryError, sanitize_readonly_query


def render() -> None:
    st.title("Ad-hoc SQL")
    st.caption("Phase 2 feature. Read-only SQL over current snapshot with row caps.")

    df = calculate_scores(load_snapshot())
    if df.empty:
        st.error("No snapshot available.")
        return

    row_cap = st.slider("Maximum rows", min_value=20, max_value=2000, value=500, step=20)
    query = st.text_area("SQL query", value="SELECT repo_name, score_letter FROM snapshot LIMIT 20")

    if st.button("Run query"):
        con = None
        try:
            con = duckdb.connect(database=":memory:")
            con.register("snapshot", df)
            sql = sanitize_readonly_query(query, row_limit=row_cap)
            result = con.execute(sql).fetch_df()
            st.dataframe(result, width="stretch")
        except UnsafeQueryError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Query failed: {exc}")
        finally:
            if con is not None:
                con.close()


render()

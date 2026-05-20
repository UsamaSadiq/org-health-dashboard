from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from dashboard.lib.data import load_config, load_snapshot
from dashboard.lib.schema import TIMESTAMP_COL, parse_snapshot_date


def render() -> None:
    df = load_snapshot()
    now = datetime.now(timezone.utc)
    version = "1.0.0"
    cfg = load_config("data_source")

    if df.empty:
        st.text("status=degraded")
        st.text(f"time_utc={now.isoformat()}")
        st.text(f"dashboard_version={version}")
        return

    snapshot_date = parse_snapshot_date(df[TIMESTAMP_COL].iloc[0]) if TIMESTAMP_COL in df.columns else None
    age_seconds = -1
    if snapshot_date is not None:
        age_seconds = int((now.date() - snapshot_date).total_seconds())

    st.text("status=ok")
    st.text(f"snapshot_age_seconds={age_seconds}")
    st.text(f"dashboard_version={version}")
    st.text(f"data_source_url={cfg.get('data_source_url', cfg.get('csv_url', ''))}")


render()

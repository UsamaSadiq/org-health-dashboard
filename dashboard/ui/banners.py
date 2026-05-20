from __future__ import annotations

from datetime import date, datetime, timezone

import streamlit as st


def render_freshness_banner(snapshot_date: date | None, stale_hours: int, critical_hours: int) -> None:
    if snapshot_date is None:
        st.error("Snapshot timestamp unavailable.")
        return

    now = datetime.now(timezone.utc).date()
    age_hours = (now - snapshot_date).days * 24
    text = f"Snapshot date: {snapshot_date.isoformat()} (UTC)"

    if age_hours > critical_hours:
        st.error(text + " | Data is stale - upstream pipeline may be down.")
    elif age_hours > stale_hours:
        st.warning(text + " | Data may be stale.")
    else:
        st.info(text)

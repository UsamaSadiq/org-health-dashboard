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


def _format_age(age_hours: int) -> str:
    if age_hours < 48:
        return f"{age_hours}h ago"
    days = age_hours // 24
    return f"{days}d ago"


def freshness_chip_html(snapshot_date: date | None, stale_hours: int, critical_hours: int) -> str:
    """Return the freshness pill as raw HTML (for composition into a larger block)."""
    if snapshot_date is None:
        return (
            '<div class="freshness-chip freshness-critical">'
            '<span class="freshness-dot"></span>No snapshot</div>'
        )

    now = datetime.now(timezone.utc).date()
    age_hours = max(0, (now - snapshot_date).days * 24)
    age_label = _format_age(age_hours)

    if age_hours > critical_hours:
        cls, label = "freshness-critical", f"Critical · {age_label}"
    elif age_hours > stale_hours:
        cls, label = "freshness-stale", f"Stale · {age_label}"
    else:
        cls, label = "freshness-fresh", f"Fresh · {age_label}"

    return (
        f'<div class="freshness-chip {cls}">'
        f'<span class="freshness-dot"></span>{label}</div>'
    )


def freshness_chip(snapshot_date: date | None, stale_hours: int, critical_hours: int) -> None:
    """Render a compact freshness pill suitable for the sidebar."""
    st.markdown(
        freshness_chip_html(snapshot_date, stale_hours, critical_hours),
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, body: str = "", icon: str = "cloud_off") -> None:
    """Render a friendly centered empty-state card.

    Streamlit's Material-icon shortcode `:material/name:` is only expanded by
    `st.markdown`, not inside `unsafe_allow_html` blocks, so we render the
    decorative shell with HTML and then layer the icon + title via native
    markdown inside a centered container.
    """
    with st.container():
        st.markdown('<div class="card card-empty">', unsafe_allow_html=True)
        st.markdown(
            f"<div style='text-align:center;'>\n\n"
            f":material/{icon}:\n\n"
            f"### {title}\n\n"
            f"<p style='color:var(--color-muted);margin:0;'>{body}</p>\n\n"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

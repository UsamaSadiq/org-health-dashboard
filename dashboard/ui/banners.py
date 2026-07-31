"""Banners, freshness reporting, and one empty-state vocabulary.

There were six different ways to say "nothing here" across seven pages, and the
colours contradicted each other: "no newly failing checks" rendered green while
"no newly passing checks" rendered blue, and "nothing to show for the current
filter" rendered green as though an empty filter result were good news.

:func:`empty_state` fixes the vocabulary rather than the individual call sites.
Its ``kind`` argument carries a single meaning each:

``good``
    Genuinely good news. Nothing failed, nothing regressed. Green.
``info``
    A neutral absence: no rows matched, a feature is switched off, nothing has
    been generated yet. Blue. This is the default and the right choice whenever
    "empty" is not itself an achievement.
``warn``
    Something about the data or configuration is wrong, and the reader may be
    looking at less than they think.
``error``
    A hard failure. There is nothing to show and it is not the reader's doing.

The second half of the fix is ``body``: an empty state that only says what is
absent leaves the reader stuck. "Not enough historical snapshots" invites "why?
for how long? is that expected?", so the body should answer at least one of those
(backlog I3).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable, Literal

import streamlit as st

EmptyStateKind = Literal["good", "info", "warn", "error"]

# Fixed kind -> renderer mapping. Centralised so the semantics cannot drift back
# apart one call site at a time.
_RENDERERS: dict[str, Callable[[str], None]] = {
    "good": st.success,
    "info": st.info,
    "warn": st.warning,
    "error": st.error,
}


def empty_state(
    kind: EmptyStateKind,
    title: str,
    body: str = "",
    *,
    action_label: str | None = None,
    action_url: str | None = None,
) -> None:
    """Report an absent or empty result with consistent semantics.

    Args:
        kind: See the module docstring. Use ``good`` only when empty is an
            achievement; ``info`` is the default for a neutral absence.
        title: One line stating what is absent.
        body: What the reader can do, or why it is absent. Strongly encouraged —
            a bare statement of absence is the thing this replaces.
        action_label: Optional link text, rendered after the message.
        action_url: Target for ``action_label``.
    """
    # Resolve through the mapping in both cases, including the fallback: reaching
    # for st.info directly would make _RENDERERS not quite the single source of
    # truth it claims to be.
    renderer = _RENDERERS.get(kind) or _RENDERERS["info"]
    message = f"**{title}**" if body else title
    if body:
        message = f"{message}\n\n{body}"
    renderer(message)
    if action_label and action_url:
        st.link_button(action_label, action_url)


def render_freshness_banner(snapshot_date: date | None, stale_hours: int, critical_hours: int) -> None:
    """Report snapshot age in the main content area.

    This existed and was never called: the only freshness signal was a small
    amber dot on a translucent chip partway down a dark sidebar, for data that
    was three days past its own stale threshold (backlog C2, E10). A fresh
    snapshot renders nothing at all — a banner on every page for the normal case
    is noise, and the sidebar chip already carries it.
    """
    if snapshot_date is None:
        empty_state(
            "error",
            "Snapshot timestamp unavailable.",
            "The dashboard cannot tell how old this data is.",
        )
        return

    now = datetime.now(timezone.utc).date()
    age_hours = max(0, (now - snapshot_date).days * 24)
    # Bare duration, not _format_age()'s relative phrasing: that returns "7d ago",
    # which reads as "Data is 7d ago old".
    age = f"{age_hours}h" if age_hours < 48 else f"{age_hours // 24} days"

    if age_hours > critical_hours:
        empty_state(
            "error",
            f"This data is {age} old.",
            f"Snapshot {snapshot_date.isoformat()} (UTC). The upstream pipeline may "
            "have stopped; everything below describes the repositories as they were "
            "at that point, not as they are now.",
        )
    elif age_hours > stale_hours:
        empty_state(
            "warn",
            f"This data is {age} old.",
            f"Snapshot {snapshot_date.isoformat()} (UTC), past the "
            f"{stale_hours}h freshness threshold. Recent changes will not appear yet.",
        )


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

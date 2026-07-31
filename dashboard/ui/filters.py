"""Shared sidebar filter component.

Single source of truth for the cross-page filter state. Each filter is
backed by `st.session_state` under a stable key so navigating between
pages preserves the user's selections.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from dashboard.ui.banners import freshness_chip_html


TIER_OPTIONS = ["all", "critical", "important", "standard"]


@dataclass(frozen=True)
class FilterState:
    search: str
    include_archived: bool
    tier: str
    # Sidebar slot reserved next to the filter controls, filled by
    # report_result_count() once the caller knows how many rows survived.
    count_slot: object | None = None

    def report_result_count(self, shown: int, total: int) -> None:
        """Write the post-filter count into the reserved sidebar slot."""
        if self.count_slot is None:
            return
        self.count_slot.caption(f"Showing {shown} of {total} repositories")

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        out = df
        if "github.is_archived" in out.columns and not self.include_archived:
            out = out[out["github.is_archived"] != True]  # noqa: E712
        if self.search:
            out = out[out["repo_name"].astype(str).str.contains(self.search, case=False, na=False)]
        if self.tier and self.tier != "all" and "repo_tier" in out.columns:
            out = out[out["repo_tier"] == self.tier]
        return out

    def as_query_params(self) -> dict[str, str]:
        return {
            "search": self.search,
            "archived": str(self.include_archived).lower(),
            "tier": self.tier,
        }


def render_sidebar_filters(
    *,
    show_tier: bool = True,
    show_archived: bool = True,
    snapshot_date: date | None = None,
    stale_hours: int = 48,
    critical_hours: int = 168,
    tier_counts: dict[str, int] | None = None,
) -> FilterState:
    """Render the shared filter group in the sidebar. Returns the live state.

    Args:
        tier_counts: Repositories per tier, from ``dashboard.lib.tiers``. When
            supplied, tier options carry their counts.
    """
    with st.sidebar:
        chip_html = freshness_chip_html(snapshot_date, stale_hours, critical_hours)
        st.markdown(
            '<div class="sidebar-identity">'
            '<div class="sidebar-wordmark">Open edX Health</div>'
            f'{chip_html}'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sidebar-section">Filters</div>', unsafe_allow_html=True)
        search = st.text_input(
            "Search repositories",
            value=st.session_state.get("filter_search", ""),
            key="filter_search",
            help="Substring match on repo name (case-insensitive).",
            placeholder="e.g. edx-platform",
        )
        include_archived = (
            st.checkbox(
                "Include archived",
                value=st.session_state.get("filter_archived", False),
                key="filter_archived",
            )
            if show_archived
            else False
        )
        # Counts in the labels, including zeros. tiers.yaml classifies only a
        # handful of repositories today, so "critical (0)" is honest where a bare
        # "critical" implies a curated list exists.
        def _tier_label(value: str) -> str:
            if tier_counts is None:
                return value.title()
            if value == "all":
                return f"All ({sum(tier_counts.values())})"
            return f"{value.title()} ({tier_counts.get(value, 0)})"

        tier = (
            st.selectbox(
                "Tier",
                TIER_OPTIONS,
                index=TIER_OPTIONS.index(st.session_state.get("filter_tier", "all")),
                key="filter_tier",
                format_func=_tier_label,
            )
            if show_tier
            else "all"
        )

        # Result count belongs directly under the controls that produce it, but
        # it is not known until the caller applies the filters. Reserve the slot
        # here and let report_result_count() fill it, rather than emitting the
        # caption after every other sidebar widget as the page used to.
        count_slot = st.empty()

        st.markdown("---")
        st.toggle(
            "Dark mode",
            value=st.session_state.get("theme_dark", False),
            key="theme_dark",
            help="Switches the dashboard to a dark palette.",
        )

    return FilterState(
        search=search,
        include_archived=include_archived,
        tier=tier,
        count_slot=count_slot,
    )


def hydrate_from_query_params() -> None:
    """Pull filter values from URL query params on first load.

    Subsequent reruns are driven by widget state directly; this only seeds
    session_state when a key is absent (so a deep link survives the first
    render but doesn't fight the user's later edits).
    """
    params = st.query_params
    if "search" in params and "filter_search" not in st.session_state:
        st.session_state["filter_search"] = str(params["search"])
    if "archived" in params and "filter_archived" not in st.session_state:
        st.session_state["filter_archived"] = str(params["archived"]).lower() == "true"
    if "tier" in params and "filter_tier" not in st.session_state:
        value = str(params["tier"])
        if value in TIER_OPTIONS:
            st.session_state["filter_tier"] = value

"""Shared sidebar filter component.

Single source of truth for the cross-page filter state. Each filter is
backed by `st.session_state` under a stable key so navigating between
pages preserves the user's selections.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st


TIER_OPTIONS = ["all", "critical", "important", "standard"]


@dataclass(frozen=True)
class FilterState:
    search: str
    include_archived: bool
    tier: str

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


def render_sidebar_filters(*, show_tier: bool = True, show_archived: bool = True) -> FilterState:
    """Render the shared filter group in the sidebar. Returns the live state."""
    with st.sidebar:
        st.markdown("### Filters")
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
        tier = (
            st.selectbox(
                "Tier",
                TIER_OPTIONS,
                index=TIER_OPTIONS.index(st.session_state.get("filter_tier", "all")),
                key="filter_tier",
            )
            if show_tier
            else "all"
        )

    return FilterState(search=search, include_archived=include_archived, tier=tier)


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

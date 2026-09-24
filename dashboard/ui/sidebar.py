"""Sidebar header shown on every page: org name and the theme toggle."""
from __future__ import annotations

import html

import streamlit as st

from dashboard.lib.config import get_config
from dashboard.ui.theme import THEME_STATE_KEY, is_dark

THEME_TOGGLE_KEY = "theme_dark_toggle"
DEFAULT_ORG_NAME = "Open edX Health"


def _store_theme_choice() -> None:
    st.session_state[THEME_STATE_KEY] = bool(st.session_state[THEME_TOGGLE_KEY])


def org_short_name() -> str:
    branding = get_config("org_branding")
    return str(branding.get("short_name") or DEFAULT_ORG_NAME).strip()


def render_sidebar_header() -> None:
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-identity">'
            f'<div class="sidebar-wordmark">{html.escape(org_short_name())}</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.toggle(
            "Dark mode",
            value=is_dark(),
            key=THEME_TOGGLE_KEY,
            on_change=_store_theme_choice,
            help="Switches the whole dashboard between the dark and light palettes.",
        )

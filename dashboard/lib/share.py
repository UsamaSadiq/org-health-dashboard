"""Helpers for building shareable URLs that respect the deployment host.

The dashboard may run on Streamlit Community Cloud, a self-host, or local
development. Set DASHBOARD_BASE_URL to the public root of the deployment
(e.g. https://myapp.streamlit.app). Falls back to http://localhost:8502
for local development.

URL structure: Streamlit multi-page apps route by URL *path*, not by
query params. share_link() maps the logical `tab` name to the correct
page path and appends remaining params as the query string.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

DEFAULT_BASE_URL = "http://localhost:8502"

# Maps the logical tab name used across the codebase to the Streamlit page
# URL path (derived from st.Page title by Streamlit's navigation layer).
_TAB_TO_PATH: dict[str, str] = {
    "overview": "",
    "detail": "repo_detail",
    "failing-checks": "failing_checks",
    "needing-attention": "needing_attention",
    "what-changed": "what_changed",
    "ownership": "ownership_views",
    "glossary": "glossary",
}


def base_url() -> str:
    return os.environ.get("DASHBOARD_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def share_link(params: dict[str, str]) -> str:
    """Build a shareable URL for the given tab and optional query params.

    Extracts 'tab' from params to determine the page path; all other
    non-empty params become the query string.

    Example:
        share_link({"tab": "detail", "repo": "openedx/edx-platform"})
        → "http://localhost:8502/repo_detail?repo=openedx%2Fedx-platform"
    """
    cleaned = {k: v for k, v in params.items() if v not in (None, "")}
    tab = cleaned.pop("tab", "overview")
    path = _TAB_TO_PATH.get(tab, "")

    root = base_url()
    url = f"{root}/{path}" if path else f"{root}/"
    if cleaned:
        url += f"?{urlencode(cleaned)}"
    return url

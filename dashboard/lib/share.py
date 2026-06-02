"""Helpers for building shareable URLs that respect the deployment host.

The dashboard may run on Streamlit Community Cloud, a self-host, or local
development on any port. base_url() resolves the origin in this order:

  1. DASHBOARD_BASE_URL env var — set this for production deployments
     (e.g. https://myapp.streamlit.app).
  2. st.context.headers["Host"] — the actual host:port the browser used,
     available during any Streamlit render cycle. Works for any port
     without hardcoding.
  3. "http://localhost:8502" — last-resort fallback for unit tests and
     out-of-render-cycle calls where st.context is unavailable.

URL structure: Streamlit multi-page apps route by URL *path*, not by
query params. share_link() maps the logical `tab` name to the correct
page path and appends remaining params as the query string.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

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
    """Return the root URL of the running app, port-agnostic.

    Priority: DASHBOARD_BASE_URL env var > Host request header > localhost fallback.
    """
    explicit = os.environ.get("DASHBOARD_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    try:
        import streamlit as st
        host = st.context.headers.get("Host", "")
        if host:
            # Use https for any non-localhost host (Streamlit Cloud, custom domains).
            scheme = "http" if host.startswith("localhost") or host.startswith("127.") else "https"
            return f"{scheme}://{host}"
    except Exception:  # noqa: BLE001 — st.context unavailable outside render cycle
        pass

    return "http://localhost:8502"


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

"""Helpers for building shareable URLs that respect the deployment host.

The dashboard may run on Streamlit Community Cloud, a self-host, or local
development. `DASHBOARD_BASE_URL` env var overrides the default; otherwise
we fall back to the Streamlit Cloud share URL used historically.
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

DEFAULT_BASE_URL = "https://share.streamlit.io/"


def base_url() -> str:
    return os.environ.get("DASHBOARD_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/"


def share_link(params: dict[str, str]) -> str:
    cleaned = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{base_url()}?{urlencode(cleaned)}" if cleaned else base_url()

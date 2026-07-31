"""Per-page initialisation and feature gating.

Both helpers here exist because of one Streamlit behaviour: **a direct load of a
non-root URL is served without the entry script's configuration taking effect.**
Streamlit discovers anything in ``pages/`` automatically and routes to it by a
filename-derived slug, so ``/repo_detail`` resolves whether or not
``streamlit_app.py`` got to call ``st.navigation()``.

That had two consequences, both verified against a cold server:

**No styling.** ``apply_base_style()`` used to be called only from
``streamlit_app.py``. On a deep link its ``<style>`` block never reached the
document: absent 45 seconds after load, and never arriving afterwards — a rerun
did not help, only navigating to ``/`` did. The page rendered with no Inter, no
card surfaces, no grade-pill colours, no sidebar gradient, and status chips
flattened into plain heading text. Since every share link this app generates
points at a sub-page (``/repo_detail?repo=…``, ``/needing_attention?tier=…``)
and Streamlit Community Cloud sleeps idle apps, the recipient of a pasted link
was the visitor most likely to see it. Fix: :func:`page_init`, called first in
every page module, so styling is owned by the page that needs it rather than by
a script that may not run.

**No access control.** ``feature_flags.yaml`` was consulted only when building
the nav, which meant a flag-off page was hidden from the menu but still served
at its URL. ``GET /sql`` returned the working Ad-hoc SQL page — query textarea
and Run button — with ``enable_sql_page: false``. Fix: :func:`require_feature`,
called by each optional page, so the flag gates the *feature* and not just its
menu entry.

The general rule the second fix encodes: **nav-level gating is presentation, not
authorisation.** Any page that must not be usable has to say so itself.
"""
from __future__ import annotations

import streamlit as st

# Imported from the submodules rather than the `dashboard.ui` package to keep
# this module importable from `dashboard/ui/__init__.py` without a cycle.
from dashboard.lib.config import get_feature_flags
from dashboard.ui.filters import hydrate_from_query_params
from dashboard.ui.theme import apply_base_style


def page_init() -> None:
    """Apply base styling and seed filter state from the URL.

    Call this as the first statement of every page module, before any early
    return. It is the only thing standing between a deep-linked visitor and an
    unstyled page, so it must run even on the paths that bail out early (no
    snapshot, no data, feature disabled).

    ``streamlit_app.py`` deliberately does *not* also call it: within a single
    render the entry script and the page script both write to the same document,
    so one injection from the page is sufficient and avoids emitting the whole
    stylesheet twice. ``tests/test_page_init.py`` enforces that every page calls
    it, since a page that forgets would silently regress the bug above.
    """
    apply_base_style()
    hydrate_from_query_params()


def feature_enabled(*flags: str, default: bool = False) -> bool:
    """True when any of the named feature flags is on.

    Several optional surfaces are gated by more than one flag — the Cards page
    is enabled by either the year-in-review flag or the embeddable-score-card
    flag — so this is deliberately an OR over the names given.
    """
    config = get_feature_flags()
    return any(bool(config.get(flag, default)) for flag in flags)


def require_feature(*flags: str, label: str, default: bool = False) -> bool:
    """Gate a page on its own feature flag, rendering a stub when it is off.

    Args:
        *flags: Flag names; the feature is on when any is true.
        label: Human name for the page, used as the stub's heading.
        default: Value assumed for a flag missing from the config.

    Returns:
        True when the caller should render its feature. When False the caller
        must return immediately — the stub has already been drawn.
    """
    if feature_enabled(*flags, default=default):
        return True

    st.title(label)
    st.info(f"{label} is not enabled for this deployment.")
    st.caption(
        "This page is gated by a feature flag in "
        "`dashboard/config/feature_flags.yaml`."
    )
    return False

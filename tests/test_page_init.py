"""Guards for WP-2A: deep-linked pages must style themselves and gate themselves.

Streamlit serves every file in ``pages/`` at a filename-derived URL, and it does
so without ``streamlit_app.py``'s configuration necessarily taking effect. Two
things therefore cannot live in the entry script alone, and these tests hold that
line because both failures are invisible in normal use — they only show up on a
cold direct load of a sub-page, which is exactly what a shared link is.

Source-level assertions rather than rendering assertions: driving Streamlit's
script runner in-process is slow and brittle, whereas "does this module call the
helper" is precisely the invariant that regressed in the first place. The
end-to-end proof lives in ``scripts/ux_audit.py`` (see
``scripts/uxaudit/readiness.py``), which refuses to capture an unstyled page.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PAGES_DIR = Path(__file__).resolve().parents[1] / "pages"

# 99_healthz.py is a machine-readable liveness endpoint, not a page: no chrome
# to apply, and its reachability outside the nav is the point. See its comment.
EXEMPT_FROM_PAGE_INIT = {"99_healthz.py"}

# Optional surfaces and the flag names that must gate them. Keys match the nav
# conditions in streamlit_app.py; a page enabled by several flags needs each of
# them named here so a rename cannot silently ungate the feature.
FLAG_GATED_PAGES = {
    "07_sql.py": {"enable_sql_page"},
    "08_badges.py": {"enable_badge_links"},
    "10_cards.py": {"enable_year_in_review_cards", "enable_embeddable_score_cards"},
}


def _page_files() -> list[Path]:
    return sorted(p for p in PAGES_DIR.glob("*.py") if not p.name.startswith("_"))


def _called_names(tree: ast.AST) -> set[str]:
    """Every plain function name invoked anywhere in the module."""
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _string_constants(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def test_pages_directory_is_not_empty() -> None:
    """A glob that silently matches nothing would make every test below pass."""
    assert _page_files(), f"no page modules found in {PAGES_DIR}"


@pytest.mark.parametrize("path", _page_files(), ids=lambda p: p.name)
def test_every_page_calls_page_init(path: Path) -> None:
    """Each page applies the base stylesheet itself.

    Regression guard for A0: with styling applied only by the entry script, a
    direct load of any sub-page rendered with no CSS at all — verified absent 45s
    after load, recovering only after a visit to ``/``.
    """
    if path.name in EXEMPT_FROM_PAGE_INIT:
        pytest.skip(f"{path.name} is exempt by design")

    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert "page_init" in _called_names(tree), (
        f"{path.name} does not call page_init(). A page that skips it renders "
        "unstyled when reached by a direct URL, which is how every share link "
        "arrives. Call it as the first statement of render(), before any early "
        "return."
    )


@pytest.mark.parametrize("name,flags", sorted(FLAG_GATED_PAGES.items()))
def test_flag_gated_pages_enforce_their_own_flag(name: str, flags: set[str]) -> None:
    """Optional pages gate the feature, not just the nav entry.

    Regression guard for A0b: ``GET /sql`` served the working query page — with
    a textarea and a Run button — while ``enable_sql_page`` was false, because
    the flag was only ever consulted when building ``st.navigation()``.
    """
    path = PAGES_DIR / name
    assert path.exists(), f"{name} is listed as flag-gated but does not exist"

    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert "require_feature" in _called_names(tree), (
        f"{name} does not call require_feature(). Nav-level gating is "
        "presentation, not authorisation: Streamlit serves this file at its URL "
        "regardless of st.navigation()."
    )

    referenced = _string_constants(tree)
    missing = flags - referenced
    assert not missing, f"{name} does not reference flag(s): {', '.join(sorted(missing))}"


def test_entry_script_does_not_own_styling() -> None:
    """streamlit_app.py must not be the only thing applying the stylesheet.

    Keeping the call here as well would be harmless, but the failure mode we are
    guarding is someone moving it *back* and removing it from the pages, which
    silently restores A0 for every deep link.
    """
    entry = PAGES_DIR.parent / "streamlit_app.py"
    tree = ast.parse(entry.read_text(encoding="utf-8"))
    assert "apply_base_style" not in _called_names(tree), (
        "streamlit_app.py calls apply_base_style(). Styling belongs in each "
        "page's page_init() because this script's output does not reach a "
        "deep-linked page. See dashboard/ui/page.py."
    )

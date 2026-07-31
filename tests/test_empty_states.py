"""Guards for WP-11: one empty-state vocabulary, one chart idiom.

Before this there were six ways to say "nothing here" across seven pages, and the
colours contradicted each other: "no newly failing checks" was green while "no
newly passing checks" was blue, and "nothing to show for the current filter" was
green as though an empty filter result were an achievement.

The rule these tests hold is that ``kind`` carries exactly one meaning: ``good``
only where empty *is* good news, ``info`` for a neutral absence, ``warn`` for
suspect data, ``error`` for a hard failure.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dashboard.ui.banners import _RENDERERS, empty_state

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "pages"

# Pages that legitimately still call st.error / st.warning directly, for things
# that are not empty states: an exception surfaced to the reader, a caveat about
# data that IS present, or a positive confirmation.
ALLOWED_BARE_ALERTS = {
    "01_overview.py",       # the "scores are directional" caveat
    "02_repo_detail.py",    # Scorecard fetch failure
    "07_sql.py",            # the reader's own query failing
    "09_ownership_views.py",  # ownership coverage caveat
    "10_cards.py",          # "found generated file" confirmation
}


def _page_files() -> list[Path]:
    return sorted(p for p in PAGES_DIR.glob("*.py") if not p.name.startswith("_"))


def _attribute_calls(tree: ast.AST) -> list[str]:
    return [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]


def test_every_kind_has_exactly_one_renderer() -> None:
    """The mapping is the whole point: semantics cannot drift per call site."""
    assert set(_RENDERERS) == {"good", "info", "warn", "error"}
    assert len(set(_RENDERERS.values())) == 4, "two kinds share a renderer"


def test_unknown_kind_falls_back_to_info_rather_than_raising(monkeypatch) -> None:
    """A typo must not take a page down, and must not claim good news."""
    import dashboard.ui.banners as banners  # noqa: PLC0415

    seen: list[str] = []
    monkeypatch.setitem(banners._RENDERERS, "info", seen.append)
    monkeypatch.setitem(
        banners._RENDERERS, "good", lambda _: pytest.fail("unknown kind must not read as good news")
    )

    empty_state("banana", "Something")  # type: ignore[arg-type]
    assert seen == ["Something"]


def test_body_is_rendered_with_the_title(monkeypatch) -> None:
    """An empty state that only names the absence leaves the reader stuck (I3)."""
    import dashboard.ui.banners as banners  # noqa: PLC0415

    seen: list[str] = []
    monkeypatch.setitem(banners._RENDERERS, "info", seen.append)

    empty_state("info", "No rows matched.", "Widen the filter.")
    assert "No rows matched." in seen[0]
    assert "Widen the filter." in seen[0]


def test_title_only_call_still_renders(monkeypatch) -> None:
    import dashboard.ui.banners as banners  # noqa: PLC0415

    seen: list[str] = []
    monkeypatch.setitem(banners._RENDERERS, "good", seen.append)
    empty_state("good", "Nothing failed.")
    assert seen == ["Nothing failed."]


@pytest.mark.parametrize("path", _page_files(), ids=lambda p: p.name)
def test_pages_use_empty_state_for_absences(path: Path) -> None:
    """No page may report an absence with a bare st.success / st.info.

    st.warning and st.error remain legitimate for genuine errors and caveats, so
    only the two "nothing here" colours are policed here — those are the ones
    that were contradicting each other.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = _attribute_calls(tree)

    if path.name in ALLOWED_BARE_ALERTS:
        pytest.skip(f"{path.name} has a documented non-empty-state alert")

    for banned in ("st.success", "st.info"):
        assert banned not in calls, (
            f"{path.name} calls {banned} directly. Use empty_state() so "
            "'nothing here' means the same thing on every page."
        )


def test_empty_filter_result_is_not_reported_as_good_news() -> None:
    """The specific inconsistency this WP fixed, pinned by content.

    Repo Detail rendered "Nothing to show for the current filter" in green. An
    empty filter result is neutral: the reader narrowed too far, which is not an
    achievement.
    """
    source = (PAGES_DIR / "02_repo_detail.py").read_text(encoding="utf-8")
    assert "Nothing to show for the current filter" not in source
    assert '"info",\n            "No checks match this filter."' in source


def test_no_page_imports_plotly_directly() -> None:
    """Charts go through the themed helpers in dashboard/ui/charts.py (E1).

    Failing Checks built its own px.bar, which is why it had 40 colours, an
    unreadable rotated label band and a legend that listed six of them.
    """
    for path in _page_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("plotly"), f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("plotly"), f"{path.name} imports from {node.module}"


def test_freshness_banner_is_actually_called() -> None:
    """It existed and was never invoked (C2/E10)."""
    source = (PAGES_DIR / "01_overview.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "render_freshness_banner" in _attribute_calls(tree) or "render_freshness_banner(" in source


def test_freshness_banner_is_silent_when_data_is_fresh(monkeypatch) -> None:
    """A banner on every page for the normal case is noise.

    The sidebar chip already reports freshness; the banner is for when the age has
    crossed a threshold the reader needs to know about.
    """
    import datetime as real_datetime  # noqa: PLC0415

    import dashboard.ui.banners as banners  # noqa: PLC0415

    rendered: list[str] = []
    for kind in ("good", "info", "warn", "error"):
        monkeypatch.setitem(banners._RENDERERS, kind, rendered.append)

    today = real_datetime.datetime.now(real_datetime.timezone.utc).date()
    banners.render_freshness_banner(today, stale_hours=48, critical_hours=168)
    assert rendered == [], "a fresh snapshot must not draw a banner"

    stale = today - real_datetime.timedelta(days=4)
    banners.render_freshness_banner(stale, stale_hours=48, critical_hours=168)
    assert len(rendered) == 1, "a stale snapshot must draw exactly one banner"
    assert "old" in rendered[0]


def test_freshness_banner_escalates_past_the_critical_threshold(monkeypatch) -> None:
    import datetime as real_datetime  # noqa: PLC0415

    import dashboard.ui.banners as banners  # noqa: PLC0415

    by_kind: dict[str, list[str]] = {k: [] for k in ("good", "info", "warn", "error")}
    for kind in by_kind:
        monkeypatch.setitem(banners._RENDERERS, kind, by_kind[kind].append)

    today = real_datetime.datetime.now(real_datetime.timezone.utc).date()
    banners.render_freshness_banner(today - real_datetime.timedelta(days=4), 48, 168)
    banners.render_freshness_banner(today - real_datetime.timedelta(days=30), 48, 168)

    assert len(by_kind["warn"]) == 1
    assert len(by_kind["error"]) == 1


def test_missing_snapshot_date_is_an_error_not_a_warning(monkeypatch) -> None:
    import dashboard.ui.banners as banners  # noqa: PLC0415

    errors: list[str] = []
    monkeypatch.setitem(banners._RENDERERS, "error", errors.append)
    banners.render_freshness_banner(None, 48, 168)
    assert len(errors) == 1

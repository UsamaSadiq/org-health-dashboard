"""Guards for WP-7: scoring and history must be loaded once, through the cache.

The pattern this replaces was ``calculate_scores(load_snapshot())`` repeated in
each page module. Because ``calculate_scores`` iterates rows in Python over a
171 x 111 frame, that ran on every rerun — every keystroke in a search box, every
tab switch. Overview was worse: three independent history loads per render, one of
which re-scored every snapshot in the window, and ``kpi.py`` reached past
``dashboard.data`` into ``dashboard.lib.trends`` so its load skipped the cache
entirely.

These are source-level assertions. The alternative is driving Streamlit's script
runner to count cache hits, which is slow and brittle; "does any page reintroduce
the uncached call" is the invariant that actually regressed.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "pages"
UI_DIR = ROOT / "dashboard" / "ui"

# ownership_views legitimately scores a *derived* frame (load_my_repos filters the
# snapshot by handle), which has no cached scored equivalent.
ALLOWED_DIRECT_SCORING = {"09_ownership_views.py"}


def _page_files() -> list[Path]:
    return sorted(p for p in PAGES_DIR.glob("*.py") if not p.name.startswith("_"))


def _calls(tree: ast.AST) -> set[str]:
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def _import_sources(tree: ast.AST) -> dict[str, set[str]]:
    """module -> imported names, for every ``from x import y`` in the file."""
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.setdefault(node.module, set()).update(alias.name for alias in node.names)
    return out


@pytest.mark.parametrize("path", _page_files(), ids=lambda p: p.name)
def test_pages_do_not_score_the_snapshot_themselves(path: Path) -> None:
    """``calculate_scores(load_snapshot())`` must come from the cached loader."""
    if path.name in ALLOWED_DIRECT_SCORING:
        pytest.skip(f"{path.name} scores a derived frame")

    source = path.read_text(encoding="utf-8")
    assert "calculate_scores(load_snapshot())" not in source, (
        f"{path.name} scores the snapshot inline. Use load_scored_snapshot() so "
        "the 171x111 Python-level scoring pass is cached rather than repeated on "
        "every rerun."
    )


@pytest.mark.parametrize("path", _page_files(), ids=lambda p: p.name)
def test_pages_load_history_through_the_cache(path: Path) -> None:
    """No module may import history from the library layer directly.

    ``dashboard.lib.trends.load_history`` is uncached; ``dashboard.data`` wraps it.
    kpi.py imported the former, so its history load re-fetched and re-scored on
    every rerun.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    trends_imports = _import_sources(tree).get("dashboard.lib.trends", set())
    assert "load_history" not in trends_imports, (
        f"{path.name} imports load_history from dashboard.lib.trends, which is "
        "uncached. Import load_scored_history from dashboard.data instead."
    )


def test_kpi_module_uses_the_cached_history_loader() -> None:
    """The specific bypass this WP fixed, pinned by name."""
    source = (UI_DIR / "kpi.py").read_text(encoding="utf-8")
    assert "from dashboard.lib.trends import load_history" not in source
    assert "load_scored_history" in source


def test_scored_loaders_are_cached() -> None:
    """Both scored entry points must carry a cache decorator.

    Checked on the source rather than the objects, because ``st.cache_data``
    wrappers do not expose their TTL in a stable, documented way.
    """
    source = (ROOT / "dashboard" / "data.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    decorated: dict[str, bool] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decorated[node.name] = any(
                "cache_data" in ast.unparse(decorator) for decorator in node.decorator_list
            )

    for name in ("load_snapshot", "load_scored_snapshot", "load_history", "load_scored_history"):
        assert decorated.get(name), f"{name} is not cached"


def test_snapshot_and_history_share_one_ttl() -> None:
    """Mismatched TTLs made the KPI tiles and their deltas disagree.

    The snapshot was 300s and history 86400s, so for up to a day after a pipeline
    run a tile could show a new value against a stale baseline.
    """
    from dashboard.data import CACHE_TTL_SECONDS  # noqa: PLC0415

    source = (ROOT / "dashboard" / "data.py").read_text(encoding="utf-8")
    assert "ttl=86400" not in source, "history still has its own longer TTL"
    # Every cache_data decorator should reference the shared constant.
    assert source.count("ttl=CACHE_TTL_SECONDS") == 4
    assert CACHE_TTL_SECONDS == 300


def test_scored_history_does_not_mutate_the_cached_raw_frames() -> None:
    """st.cache_data hands out references, not copies.

    Scoring the raw snapshots in place would add score_* columns to the entry that
    every unscored caller shares.
    """
    source = (ROOT / "dashboard" / "data.py").read_text(encoding="utf-8")
    assert "Snapshot(timestamp=" in source, (
        "load_scored_history should build new Snapshot objects rather than "
        "assigning into the cached ones"
    )


def test_repo_detail_does_not_cache_history_per_repository() -> None:
    """A per-repo cache held one copy of the 30-day window per repo browsed."""
    source = (PAGES_DIR / "02_repo_detail.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_history_for_repo":
            decorators = [ast.unparse(d) for d in node.decorator_list]
            assert not any("cache_data" in d for d in decorators), (
                "_history_for_repo is cached per repository; the underlying "
                "history is already cached by load_scored_history"
            )
            return
    pytest.fail("_history_for_repo not found in pages/02_repo_detail.py")


def test_cold_path_shows_a_spinner() -> None:
    """A silent cold fetch plus scoring pass read as a hung page."""
    source = (ROOT / "dashboard" / "data.py").read_text(encoding="utf-8")
    assert 'show_spinner="Scoring repositories…"' in source
    assert 'show_spinner="Loading history…"' in source
    assert "show_spinner=False" not in source

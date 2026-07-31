"""Guards for WP-10: one table renderer, one column vocabulary.

``dashboard/ui/tables.py`` was a seven-line stub, so five pages each grew their
own table. Every one leaked raw dataframe column names (``repo_name``,
``score_composite``, ``delta``), one forgot ``hide_index`` and showed internal row
numbers as the reader's first column, and link cells rendered full URLs truncated
mid-string because ``LinkColumn`` was never given ``display_text``.

The AST check below is the load-bearing one: it is what stops the sixth page from
reinventing the fifth table.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from dashboard.ui.tables import (
    COLUMN_LABELS,
    NUMBER_FORMATS,
    _column_config,
    add_detail_links,
    repo_grade_table,
)

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "pages"


def _page_files() -> list[Path]:
    return sorted(p for p in PAGES_DIR.glob("*.py") if not p.name.startswith("_"))


def _attribute_calls(tree: ast.AST) -> set[str]:
    """Dotted call names, e.g. ``st.dataframe``."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            out.add(ast.unparse(node.func))
    return out


@pytest.mark.parametrize("path", _page_files(), ids=lambda p: p.name)
def test_pages_do_not_call_st_dataframe_directly(path: Path) -> None:
    """Every table goes through repo_table().

    Bypassing it is how thirteen call sites came to disagree about column labels,
    number formats, index visibility and link text.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert "st.dataframe" not in _attribute_calls(tree), (
        f"{path.name} calls st.dataframe directly. Use repo_table() from "
        "dashboard.ui so the column vocabulary stays shared."
    )


def test_repo_table_hides_the_index_unconditionally() -> None:
    """hide_index is deliberately not a parameter (backlog A8)."""
    source = (ROOT / "dashboard" / "ui" / "tables.py").read_text(encoding="utf-8")
    assert "hide_index=True" in source

    import inspect  # noqa: PLC0415

    from dashboard.ui.tables import repo_table  # noqa: PLC0415

    assert "hide_index" not in inspect.signature(repo_table).parameters, (
        "hide_index must not be overridable; a page that passes False reintroduces "
        "the leaked index column"
    )


def _captured_dataframe_kwargs(monkeypatch, frame: pd.DataFrame, **kwargs) -> dict:
    """Call repo_table and return the kwargs it passed to st.dataframe."""
    import dashboard.ui.tables as tables_module  # noqa: PLC0415

    captured: dict = {}

    def _fake_dataframe(data, **kw):
        captured["data"] = data
        captured.update(kw)

    monkeypatch.setattr(tables_module.st, "dataframe", _fake_dataframe)
    tables_module.repo_table(frame, **kwargs)
    return captured


def test_repo_table_omits_height_when_not_requested(monkeypatch) -> None:
    """height=None must not reach st.dataframe.

    Regression guard: passing it through raised StreamlitInvalidHeightError and
    replaced three whole pages with a traceback. The original tests were all AST
    and unit-level, so nothing actually invoked the renderer.
    """
    frame = pd.DataFrame({"repo_name": ["openedx/a"], "score_composite": [70.0]})
    captured = _captured_dataframe_kwargs(monkeypatch, frame)
    assert "height" not in captured
    assert captured["hide_index"] is True


def test_repo_table_passes_an_explicit_height(monkeypatch) -> None:
    frame = pd.DataFrame({"repo_name": ["openedx/a"]})
    captured = _captured_dataframe_kwargs(monkeypatch, frame, height=460)
    assert captured["height"] == 460


def test_repo_table_renders_every_page_shape(monkeypatch) -> None:
    """Exercise the renderer with the frame shape each page actually passes."""
    shapes = {
        "overview-movers": pd.DataFrame({"repo_name": ["a"], "delta": [-3.5]}),
        "overview-full": pd.DataFrame(
            {"repo_name": ["a"], "score_composite": [70.0], "score_letter": ["B"]}
        ),
        "needing-attention": pd.DataFrame(
            {
                "repo_name": ["a"],
                "repo_tier": ["critical"],
                "score_composite": [13.3],
                "score_letter": ["F"],
                "reasons": ["no commits in 90+ days"],
            }
        ),
        "what-changed": pd.DataFrame({"repo_name": ["a"], "check": ["readme.security"]}),
        "ownership": pd.DataFrame(
            {"ownership.owner": ["axim"], "repo_count": [3], "avg_score": [61.2], "d_or_f": [1]}
        ),
        "sql-adhoc": pd.DataFrame({"anything": [1]}),
    }
    for name, frame in shapes.items():
        captured = _captured_dataframe_kwargs(
            monkeypatch, frame, link_to_detail="repo_name" in frame.columns, use_progress=True
        )
        assert captured["hide_index"] is True, name
        assert set(captured["column_config"]) == set(captured["data"].columns), name


def test_repo_table_shows_a_caption_for_an_empty_frame(monkeypatch) -> None:
    """An empty grid with headers reads as broken; a sentence does not."""
    import dashboard.ui.tables as tables_module  # noqa: PLC0415

    captions: list[str] = []
    monkeypatch.setattr(tables_module.st, "caption", lambda text, **_: captions.append(text))
    monkeypatch.setattr(
        tables_module.st, "dataframe", lambda *a, **k: pytest.fail("should not render a grid")
    )

    tables_module.repo_table(pd.DataFrame(), empty_message="Nothing here.")
    tables_module.repo_table(None, empty_message="Also nothing.")
    assert captions == ["Nothing here.", "Also nothing."]


def test_known_columns_all_have_labels() -> None:
    """The columns pages actually render must never fall through to a raw name."""
    for column in ("repo_name", "score_composite", "score_letter", "delta", "reasons", "repo_tier"):
        assert column in COLUMN_LABELS, f"{column} has no display label"
        assert COLUMN_LABELS[column] != column


def test_delta_format_carries_an_explicit_sign() -> None:
    """"-15" beside "44" gave no clue they were the same quantity."""
    assert NUMBER_FORMATS["delta"].startswith("%+")


def test_link_column_uses_display_text_not_the_url() -> None:
    """Bare URLs as link text were truncated mid-string and said nothing."""
    frame = pd.DataFrame({"repo_name": ["openedx/a"], "repo_link": ["https://example.test/x"]})
    config = _column_config(frame, use_progress=False, link_label="Open")
    # Streamlit column configs are plain dicts with the column kind and its
    # options under "type_config".
    type_config = config["repo_link"]["type_config"]
    assert type_config["type"] == "link"
    assert type_config["display_text"] == "Open"


def test_score_renders_as_a_bar_only_when_asked() -> None:
    frame = pd.DataFrame({"score_composite": [70.25]})
    plain = _column_config(frame, use_progress=False, link_label="Open")
    barred = _column_config(frame, use_progress=True, link_label="Open")
    assert plain["score_composite"]["type_config"]["type"] == "number"
    assert barred["score_composite"]["type_config"]["type"] == "progress"


def test_unknown_columns_survive_unlabelled() -> None:
    """The SQL page renders arbitrary query output; it must not crash."""
    frame = pd.DataFrame({"some_ad_hoc_column": [1, 2], "another": ["x", "y"]})
    config = _column_config(frame, use_progress=False, link_label="Open")
    assert set(config) == {"some_ad_hoc_column", "another"}


def test_extra_config_wins_over_the_shared_vocabulary() -> None:
    """A page must be able to override a label without editing the shared map."""
    import streamlit as st  # noqa: PLC0415

    frame = pd.DataFrame({"repo_name": ["a"]})
    override = {"repo_name": st.column_config.TextColumn("Project")}
    config = _column_config(frame, use_progress=False, link_label="Open", extra=override)
    assert config["repo_name"] is override["repo_name"]


def test_add_detail_links_builds_one_link_per_row() -> None:
    frame = pd.DataFrame({"repo_name": ["openedx/a", "openedx/b"]})
    out = add_detail_links(frame)
    assert list(out.columns) == ["repo_name", "repo_link"]
    assert out["repo_link"].str.contains("repo_detail").all()
    # The input frame is not mutated: callers pass frames they still use.
    assert "repo_link" not in frame.columns


def test_add_detail_links_tolerates_a_frame_with_no_repo_column() -> None:
    frame = pd.DataFrame({"check": ["a.b"]})
    assert "repo_link" not in add_detail_links(frame).columns
    assert add_detail_links(pd.DataFrame()).empty


def test_repo_grade_table_projection_is_preserved() -> None:
    """Pre-existing helper; callers rely on the projection, not the rendering."""
    frame = pd.DataFrame(
        {
            "repo_name": ["a", "b"],
            "score_composite": [10.0, 90.0],
            "score_letter": ["F", "A"],
            "extra": [1, 2],
        }
    )
    out = repo_grade_table(frame)
    assert list(out.columns) == ["repo_name", "score_composite", "score_letter"]
    assert list(out["repo_name"]) == ["b", "a"], "must be ranked descending"

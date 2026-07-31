"""Guards for WP-2: the dark-mode toggle must actually change something.

The bug these tests exist for: ``apply_base_style()`` used to emit
``<script>document.documentElement.setAttribute('data-theme', …)</script>``
through ``st.markdown``. Browsers never execute scripts inserted as
``innerHTML``, so the attribute stayed unset (verified null both before and
after toggling) and every ``[data-theme="dark"]`` rule in the stylesheet was
dead. The toggle moved, and nothing else did.

Two properties keep that from coming back. The stylesheet must carry the active
palette's *values* rather than switching on a selector, and the Plotly template
must be rebuilt from the same palette — charts bake their colours in at
construction time and are not reachable by CSS at all, so a stale template
renders a light chart on a dark page.
"""
from __future__ import annotations

import plotly.io as pio
import pytest

from dashboard.ui.theme import (
    DARK,
    GRADE_ORDER,
    LIGHT,
    PLOTLY_TEMPLATE_NAME,
    _base_css,
    _rgba,
    palette,
    register_plotly_template,
    status_chip,
)


def test_light_and_dark_differ_on_every_surface() -> None:
    """A dark theme that reuses light surfaces is the bug, not the fix."""
    for attribute in ("text", "muted", "page", "surface", "surface_alt", "border"):
        assert getattr(LIGHT, attribute) != getattr(DARK, attribute), (
            f"{attribute} is identical in both palettes"
        )


def test_dark_replaces_unreadable_brand_and_semantic_hues() -> None:
    """The light greens and the deep teal primary are unreadable on dark.

    Reusing them is the most likely shortcut someone takes when extending the
    palette, and it looks fine in a diff.
    """
    for attribute in ("primary", "success", "fail"):
        assert getattr(LIGHT, attribute) != getattr(DARK, attribute)


def test_every_grade_has_a_colour_and_text_colour_in_both_palettes() -> None:
    for active in (LIGHT, DARK):
        for letter in GRADE_ORDER:
            assert letter in active.grade_colors, f"{active.name} missing grade {letter}"
            assert letter in active.grade_text_colors


def test_css_contains_no_script_tag() -> None:
    """The original failure was a script tag that could never run."""
    for active in (LIGHT, DARK):
        css = _base_css(active)
        assert "<script" not in css.lower(), f"{active.name} CSS emits a script tag"


def test_css_carries_the_active_palette_not_a_theme_selector() -> None:
    """Values, not selectors: the dead ``[data-theme=...]`` block is gone."""
    dark_css = _base_css(DARK)
    light_css = _base_css(LIGHT)

    assert "data-theme" not in dark_css
    assert DARK.page in dark_css
    assert f"--color-text: {DARK.text}" in dark_css
    assert f"--color-text: {LIGHT.text}" in light_css
    assert dark_css != light_css


def test_status_chip_supports_a_nodata_state() -> None:
    """"No data" must be distinguishable from "unknown"."""
    assert 'status-nodata' in status_chip("nodata", "no data")
    # Unrecognised statuses still fall back rather than emitting a broken class.
    assert 'status-unknown' in status_chip("banana")


def test_nodata_chip_is_not_colour_only() -> None:
    """It carries a dashed border, so shape distinguishes it from a muted pass."""
    css = _base_css(LIGHT)
    nodata_rule = css.split(".status-nodata")[1].split("}")[0]
    assert "dashed" in nodata_rule


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_plotly_template_follows_the_palette(active) -> None:
    """Charts are immune to CSS, so the template has to be rebuilt per theme."""
    register_plotly_template(active)
    layout = pio.templates[PLOTLY_TEMPLATE_NAME].layout
    assert layout.paper_bgcolor == active.surface_alt
    assert layout.plot_bgcolor == active.page
    assert layout.font.color == active.text
    assert pio.templates.default == PLOTLY_TEMPLATE_NAME


def test_palette_defaults_to_light_outside_a_streamlit_run() -> None:
    """Tests and offline tooling must not blow up resolving the theme."""
    assert palette() is LIGHT


def test_rgba_helper_matches_known_values() -> None:
    assert _rgba("#15803D", 0.12) == "rgba(21, 128, 61, 0.12)"
    assert _rgba("D97706", 0.3) == "rgba(217, 119, 6, 0.3)"


def test_repo_pill_list_always_renders_the_grade_and_score() -> None:
    """The pill and score must survive, whatever the name length.

    Guards a regression found while rewriting this module: adding
    ``min-width: 0`` + ellipsis to the name cell to stop long names colliding
    with the pill (backlog A11) instead pushed the pill and score out of the
    flex row entirely at 390px, so mobile lost the grade for exactly the repos
    with the longest names. Losing data beats overlapping it, so A11 stays open
    until WP-8 can verify a fix against the mobile baseline.
    """
    import dashboard.ui.theme as theme_module  # noqa: PLC0415

    captured: list[str] = []

    class _Recorder:
        def markdown(self, body: str, **_: object) -> None:
            captured.append(body)

        def caption(self, body: str) -> None:
            captured.append(body)

    original = theme_module.st
    theme_module.st = _Recorder()  # type: ignore[assignment]
    try:
        theme_module.render_repo_pill_list(
            [("openedx/a-very-long-repository-name-indeed-truly", 13.3, "F")]
        )
    finally:
        theme_module.st = original

    markup = "".join(captured)
    assert "grade-f" in markup, "grade pill missing from the row"
    assert "13.3" in markup, "score missing from the row"

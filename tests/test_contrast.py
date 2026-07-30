"""Guards for WP-9: every colour pair we control must clear WCGA AA.

Computed here rather than only in the browser gate, so a palette edit fails fast
and locally. The browser gate (``scripts/ux_audit.py --mode a11y``) still matters:
it catches pairs that arise from Streamlit's own styling, which this file cannot
know about. Two of the four fixes in this WP were exactly that kind — a
translucent input fill whose effective background could not be predicted, and
caption text whose opacity blended everything inside it.

AA is 4.5:1 for normal text, 3:1 for large text (>=18.66px, or >=14px bold).
Everything below is normal-sized, so 4.5 applies throughout.
"""
from __future__ import annotations

import pytest

from dashboard.ui.theme import DARK, LIGHT, Palette

AA_NORMAL = 4.5


def _luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    """WCAG 2.x contrast ratio between two opaque colours."""
    a, b = _luminance(foreground), _luminance(background)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def over(foreground: str, alpha: float, background: str) -> str:
    """Flatten a translucent foreground onto an opaque background.

    Status chips sit on a 12%-alpha tint of their own colour, so the effective
    background has to be computed rather than read off the palette.
    """
    f = foreground.lstrip("#")
    b = background.lstrip("#")
    blended = [
        round(int(f[i : i + 2], 16) * alpha + int(b[i : i + 2], 16) * (1 - alpha))
        for i in (0, 2, 4)
    ]
    return "#%02X%02X%02X" % tuple(blended)


def test_contrast_helper_matches_known_values() -> None:
    """Sanity-check the maths before relying on it."""
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert contrast("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.01)
    # Documented failure this WP fixed: amber on its own 12% tint over white.
    assert contrast("#D97706", over("#D97706", 0.12, "#FFFFFF")) < AA_NORMAL


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
@pytest.mark.parametrize("status,hue_attr", [
    ("pass", "success"),
    ("warn", "warn"),
    ("fail", "fail"),
    ("unknown", "muted"),
])
def test_status_chip_text_clears_aa(active: Palette, status: str, hue_attr: str) -> None:
    """Chip text against the tint the chip actually paints.

    Reusing the chart hue as chip text put warn at 2.81 and pass at 4.27, which
    is why chip_text exists as a separate field.
    """
    hue = getattr(active, hue_attr)
    alpha = 0.08 if status == "unknown" else 0.12
    background = over(hue, alpha, active.surface_alt)
    ratio = contrast(active.chip_text[status], background)
    assert ratio >= AA_NORMAL, (
        f"{active.name} status-{status}: {active.chip_text[status]} on {background} "
        f"is {ratio:.2f}, below {AA_NORMAL}"
    )


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_metric_delta_clears_aa_on_the_card(active: Palette) -> None:
    """Streamlit's default delta green measures ~3.04 on a white card."""
    assert contrast(active.delta_text, active.surface_alt) >= AA_NORMAL
    # The downward direction reuses the fail chip colour.
    assert contrast(active.chip_text["fail"], active.surface_alt) >= AA_NORMAL


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_sidebar_input_text_clears_aa(active: Palette) -> None:
    """Sidebar inputs use an opaque fill so the pair is well defined.

    With an rgba() fill the checker resolved the nearest opaque ancestor instead
    of blending and reported white-on-#f2f6fa at 1.08.
    """
    assert contrast("#FFFFFF", active.sidebar_input_bg) >= AA_NORMAL


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_inline_code_clears_aa(active: Palette) -> None:
    """Inline code sits on a 10% muted tint over the page surface."""
    background = over(active.muted, 0.10, active.page)
    assert contrast(active.code_text, background) >= AA_NORMAL


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_body_and_muted_text_clear_aa(active: Palette) -> None:
    for attr in ("text", "muted"):
        for surface in (active.page, active.surface_alt):
            ratio = contrast(getattr(active, attr), surface)
            assert ratio >= AA_NORMAL, f"{active.name} {attr} on {surface} is {ratio:.2f}"


@pytest.mark.parametrize("active", [LIGHT, DARK], ids=lambda p: p.name)
def test_grade_pill_text_clears_aa_on_its_fill(active: Palette) -> None:
    """Pills are solid fills, so this is a direct pair.

    Pill text is 0.85rem semibold, still under the large-text threshold.
    """
    for letter, fill in active.grade_colors.items():
        ratio = contrast(active.grade_text_colors[letter], fill)
        assert ratio >= AA_NORMAL, (
            f"{active.name} grade {letter}: {active.grade_text_colors[letter]} on "
            f"{fill} is {ratio:.2f}"
        )


def test_caption_opacity_is_overridden() -> None:
    """Captions must not reduce opacity.

    Opacity creates a stacking context, so a child cannot opt back out: with
    Streamlit's default, near-black inline code inside a caption still measured
    4.16. De-emphasis is expressed as a colour instead.
    """
    from dashboard.ui.theme import _base_css  # noqa: PLC0415

    css = _base_css(LIGHT)
    assert 'stCaptionContainer"]' in css
    caption_block = css.split('stCaptionContainer"] p')[1].split("}")[0]
    assert "opacity: 1" in caption_block

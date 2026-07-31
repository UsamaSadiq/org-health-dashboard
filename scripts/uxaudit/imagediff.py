"""Pixel comparison of captured screenshots against ``tests/baseline/``.

This module is the mechanical half of the visual acceptance criteria: the defect
class it targets — a gauge tick clipped so ``100`` renders as ``1``, a y-axis
title rendering as ``positories``, a long repo name overrunning its grade pill —
produces no exception, no console error, and no assertion failure. Nothing but
comparing rendered pixels catches it. Four judgement calls shape the design.

**1. Tall images defeat a single global ratio, so we tile.**
A 1440x5900 Glossary capture is 8.5M pixels. A genuinely broken 200x20 axis
label is ~4,000 of them: a global changed ratio of 0.0005, which sits *below* the
default tolerance of 0.001. A mean over the whole frame is therefore structurally
incapable of catching the thing this module exists for — the signal is real but
diluted by four hundred times more unchanged page.

So the verdict is the OR of two metrics:

  * ``changed_ratio`` — the global fraction, kept because it is the honest
    summary of "how much of the page moved" and is what a reviewer skims.
  * ``worst_tile_ratio`` — the image is cut into ``TILE_SIZE`` squares and each
    tile gets its own fraction; the worst one is reported. The 200x20 defect
    above lands inside one or two 128px tiles and occupies 10-25% of them, three
    orders of magnitude above the global number. Locality is the whole point:
    a real visual break is dense in a small area, whereas the diffuse
    single-pixel scatter of a re-render is not dense anywhere.

A tile must also carry at least ``MIN_TILE_CHANGED_PIXELS`` changed pixels
before it can fail the comparison. Without that floor the partial tiles at the
right and bottom edges (a 1440px width leaves a 32px-wide column) can cross a
percentage threshold on a handful of stray pixels.

The bounding box of the changed pixels goes in ``note`` as a coordinate pair, so
the reviewer can find the defect in the diff image without hunting.

**2. Size mismatch is the common case, not an edge case.**
These are full-length stitched captures of a live dashboard; the page gets taller
whenever a row appears upstream. Three policies were available:

  * fail outright — correct-looking, but the gate would fail on ordinary data
    churn and be routed around within a week;
  * pad to the union size — the newly added strip counts as 100% changed, which
    inflates ``changed_ratio`` and buries any genuine defect under it, i.e. it
    breaks decision 1;
  * compare the common region and state the height delta.

We take the third. *Height* differences are treated as information, not failure:
the intersection is compared and ``note`` records the actual before/after so a
reviewer can distinguish "three rows of data appeared" (+120px) from "the layout
broke" (+2000px). *Width* differences do fail, because width is pinned by the
viewport we captured at — a width change means the layout or the capture itself
is wrong, never upstream data. Rows below the compared region are washed amber
in the diff image so nobody mistakes "not compared" for "unchanged".

**3. Anti-aliasing noise needs a threshold, not equality.**
Subpixel text rendering and chart rasterisation wobble by one to three intensity
levels between otherwise identical runs. A strict ``!=`` reports thousands of
changed pixels on a re-capture of the same page. A pixel counts as changed only
when its largest per-channel absolute difference exceeds
``CHANNEL_THRESHOLD`` (8 of 255, ~3%). That absorbs hinting jitter while staying
far below the deltas that matter: a text colour or contrast regression moves a
channel by 30+, and a clipped glyph swaps background for foreground, which is
hundreds. The comparison is per-channel rather than on luminance so that a
hue-only change — a status colour that stops meeting contrast but keeps its
brightness — is not silently averaged away.

**4. The diff image is for a human, not for a machine.**
A raw XOR is unreadable. We emit the candidate desaturated and lightened, with
changed pixels painted saturated magenta (dilated 3x3 so a one-pixel-wide change
is still visible at fit-to-window zoom) and the worst-affected tile outlined in
cyan. The reviewer sees *where*, in page context, in one glance.

**Known limitation — the snapshot date and freshness label churn daily.**
"Stale · 3d ago" and the snapshot date change with wall-clock time, so those
regions differ on every run regardless of code. Decision 1 makes this worse, not
better: the churn is small and *local*, exactly the shape a tile metric is built
to flag. Region masking will be needed; it is deliberately not solved here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Tuning constants. Public so scripts/ux_audit.py can override for a one-off
# run without editing this module; the defaults are what CI uses.
# ---------------------------------------------------------------------------

# Per-channel intensity delta (0-255) below which a pixel is considered
# unchanged. See decision 3 in the module docstring.
CHANNEL_THRESHOLD = 8

# Edge length of the square tiles used for the locality metric. 128px is a
# little larger than a chart axis label and a little smaller than a KPI tile, so
# a single broken element dominates its tile rather than being diluted.
TILE_SIZE = 128

# A tile fails when more than this fraction of it changed. 2% of a 128px tile is
# ~330 pixels — well under a broken 200x20 label (~4,000) and well over the
# residual scatter that survives CHANNEL_THRESHOLD.
TILE_TOLERANCE = 0.02

# ...and only if it also carries at least this many changed pixels, which stops
# the narrow partial tiles at the right/bottom edges from tripping on noise.
MIN_TILE_CHANGED_PIXELS = 120

_HIGHLIGHT = (255, 0, 170)      # changed pixels
_TILE_OUTLINE = (0, 210, 255)   # worst-affected tile
_UNCOMPARED = (255, 176, 0)     # rows beyond the compared region


@dataclass(frozen=True)
class DiffResult:
    key: str                     # "<viewport>/<page>.png"
    changed_ratio: float         # 0.0-1.0, fraction of differing pixels
    passed: bool
    baseline: Path | None
    candidate: Path | None
    diff_image: Path | None
    note: str = ""               # e.g. "no baseline", "size mismatch 2081->2145"
    # Additive extension to the agreed contract: the locality metric from
    # decision 1. It has to be a field rather than prose inside `note` because
    # format_report() and any CI summary need to read it as a number, and
    # re-parsing it out of a human-readable string would be worse. Defaulted, so
    # every construction form in the original contract still works.
    worst_tile_ratio: float = 0.0


# ---------------------------------------------------------------------------
# Pixel maths
# ---------------------------------------------------------------------------
def _load_rgb(path: Path) -> np.ndarray:
    """Read an image as an (h, w, 3) uint8 array.

    Screenshots are opaque PNGs, but Playwright can emit RGBA; normalising to
    RGB keeps the channel arithmetic below from tripping over an alpha plane
    that carries no information.
    """
    with Image.open(path) as img:
        return np.asarray(img.convert("RGB"), dtype=np.uint8)


def _changed_mask(base: np.ndarray, cand: np.ndarray) -> np.ndarray:
    """Boolean (h, w) mask of pixels that differ beyond CHANNEL_THRESHOLD.

    int16 rather than uint8 for the subtraction — uint8 wraps, so a -12 delta
    would read as 244 and every unchanged pixel would look catastrophic.
    """
    delta = np.abs(base.astype(np.int16) - cand.astype(np.int16))
    return delta.max(axis=2) > CHANNEL_THRESHOLD


def _worst_tile(mask: np.ndarray) -> tuple[float, int, tuple[int, int, int, int]]:
    """Return (worst tile ratio, changed pixels in it, its box) for `mask`.

    Implemented by padding to a whole number of tiles and reshaping, so the
    per-tile sums are two numpy reductions rather than a Python loop over the
    ~520 tiles of a full-length capture. The denominator comes from an
    identically padded ones-array, so partial edge tiles are divided by their
    real area and not by TILE_SIZE**2.
    """
    h, w = mask.shape
    if h == 0 or w == 0:
        return 0.0, 0, (0, 0, 0, 0)

    pad_h = (-h) % TILE_SIZE
    pad_w = (-w) % TILE_SIZE
    padded = np.pad(mask, ((0, pad_h), (0, pad_w)), constant_values=False)
    area = np.pad(np.ones((h, w), dtype=np.int32), ((0, pad_h), (0, pad_w)), constant_values=0)

    ny = padded.shape[0] // TILE_SIZE
    nx = padded.shape[1] // TILE_SIZE
    shape = (ny, TILE_SIZE, nx, TILE_SIZE)
    changed_per_tile = padded.reshape(shape).sum(axis=(1, 3))
    area_per_tile = area.reshape(shape).sum(axis=(1, 3))

    ratios = np.where(area_per_tile > 0, changed_per_tile / np.maximum(area_per_tile, 1), 0.0)
    flat = int(np.argmax(ratios))
    ty, tx = divmod(flat, nx)
    box = (
        tx * TILE_SIZE,
        ty * TILE_SIZE,
        min((tx + 1) * TILE_SIZE, w),
        min((ty + 1) * TILE_SIZE, h),
    )
    return float(ratios[ty, tx]), int(changed_per_tile[ty, tx]), box


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box (x0, y0, x1, y1) of all changed pixels, or None if clean.

    This is the box around *every* change, not around the largest contiguous
    one — two distant edits produce a box spanning both. The worst-tile box is
    the precise locator; this is the "how spread out is it" signal.
    """
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


# ---------------------------------------------------------------------------
# Diff rendering
# ---------------------------------------------------------------------------
def _write_diff_image(
    cand: np.ndarray,
    mask: np.ndarray,
    worst_box: tuple[int, int, int, int] | None,
    out_path: Path,
) -> Path:
    """Render the human-readable diff described in decision 4.

    The canvas is candidate-sized, so a capture that grew still shows its full
    height; the strip below the compared region gets an amber wash rather than
    being cropped away, because "we did not look here" and "nothing changed
    here" must not look the same.
    """
    h, w = cand.shape[:2]

    # Desaturate, then lift toward white so saturated magenta reads as an
    # overlay rather than competing with the page's own colours.
    gray = (cand.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32))
    washed = 255.0 - (255.0 - gray) * 0.35
    canvas = np.repeat(washed[:, :, None], 3, axis=2).astype(np.uint8)

    mh, mw = mask.shape
    if mask.any():
        # Dilate 3x3 via PIL's C filter: a 1px-wide change is invisible when the
        # reviewer looks at a 5900px-tall image scaled to fit.
        thick = Image.fromarray((mask.astype(np.uint8) * 255)).filter(ImageFilter.MaxFilter(3))
        thick_arr = np.asarray(thick) > 0
        region = canvas[:mh, :mw]
        region[thick_arr] = _HIGHLIGHT

    # Amber wash over anything outside the compared region.
    if mh < h:
        canvas[mh:, :] = (canvas[mh:, :] * 0.6 + np.array(_UNCOMPARED, dtype=np.float32) * 0.4).astype(np.uint8)
    if mw < w:
        canvas[:, mw:] = (canvas[:, mw:] * 0.6 + np.array(_UNCOMPARED, dtype=np.float32) * 0.4).astype(np.uint8)

    img = Image.fromarray(canvas, mode="RGB")
    if worst_box is not None:
        x0, y0, x1, y1 = worst_box
        ImageDraw.Draw(img).rectangle([x0, y0, x1 - 1, y1 - 1], outline=_TILE_OUTLINE, width=2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _default_key(path: Path) -> str:
    """Best-effort "<viewport>/<page>.png" key from a loose path.

    diff_tree() knows the real relative key and overrides this; it exists so a
    direct compare() call still produces a sensibly labelled result. Built with
    string joining, never os.path.join — keys must be identical on Windows.
    """
    parent = path.parent.name
    return f"{parent}/{path.name}" if parent else path.name


def _apply_masks(mask, regions: Sequence[tuple[int, int, int, int]]) -> None:
    """Zero the masked rectangles in place, clipped to the image bounds."""
    height, width = mask.shape[:2]
    for x0, y0, x1, y1 in regions:
        left, right = max(0, min(x0, x1)), min(width, max(x0, x1))
        top, bottom = max(0, min(y0, y1)), min(height, max(y0, y1))
        if right > left and bottom > top:
            mask[top:bottom, left:right] = False


def compare(baseline: Path, candidate: Path, out_path: Path, *,
            tolerance: float,
            masks: Sequence[tuple[int, int, int, int]] = ()) -> DiffResult:
    """Compare one candidate screenshot against its baseline.

    `tolerance` is the ceiling on the *global* changed fraction; the per-tile
    ceiling is the module-level TILE_TOLERANCE. A result fails if either is
    exceeded, or if the widths differ. A diff image is written to `out_path`
    only when there is something to look at.

    `masks` are (x0, y0, x1, y1) rectangles excluded from comparison, for regions
    that change with wall-clock time rather than with code. Without them the
    bulletin's "Generated: <timestamp>" line failed the gate on every single run,
    and a gate that is always red is a gate nobody reads. Masked pixels are
    zeroed *before* both reductions, so they cannot inflate either number, and
    they are outlined in the diff image so a reviewer can see what was skipped —
    an unlabelled blank region is how a masked-away real regression happens.
    """
    key = _default_key(candidate)

    # Missing baseline: a page we have never recorded. Not a regression — the PR
    # that adds a page would otherwise be blocked by the gate meant to protect
    # it — so this passes, and format_report() lists it under NEW so it stays
    # visible instead of silently accumulating.
    if not baseline.exists():
        return DiffResult(
            key=key, changed_ratio=0.0, passed=True,
            baseline=None, candidate=candidate if candidate.exists() else None,
            diff_image=None, note="no baseline — record with --mode baseline",
        )

    # Missing candidate, however, is a failure: the page was supposed to render
    # and did not. changed_ratio is 1.0 so severity-sorted reports float it up.
    if not candidate.exists():
        return DiffResult(
            key=key, changed_ratio=1.0, passed=False,
            baseline=baseline, candidate=None, diff_image=None,
            note="candidate missing — capture failed or page was removed",
        )

    try:
        base = _load_rgb(baseline)
        cand = _load_rgb(candidate)
    except Exception as exc:  # noqa: BLE001 — a truncated PNG must fail the gate, not the run
        return DiffResult(
            key=key, changed_ratio=1.0, passed=False,
            baseline=baseline, candidate=candidate, diff_image=None,
            note=f"unreadable image: {type(exc).__name__}: {exc}",
        )

    bh, bw = base.shape[:2]
    ch, cw = cand.shape[:2]
    notes: list[str] = []

    # Decision 2: width is pinned by the viewport, so a mismatch is a real
    # failure and we short-circuit rather than compare a shifted layout column
    # by column (which would report ~100% changed and say nothing useful).
    if bw != cw:
        return DiffResult(
            key=key, changed_ratio=1.0, passed=False,
            baseline=baseline, candidate=candidate, diff_image=None,
            note=f"width mismatch {bw}->{cw} (viewport is fixed; layout or capture is wrong)",
        )

    if bh != ch:
        notes.append(f"height {bh}->{ch} ({ch - bh:+d}px); compared common {cw}x{min(bh, ch)}")

    common_h = min(bh, ch)
    if common_h == 0:
        return DiffResult(
            key=key, changed_ratio=1.0, passed=False,
            baseline=baseline, candidate=candidate, diff_image=None,
            note=f"empty overlap: baseline {bw}x{bh}, candidate {cw}x{ch}",
        )

    mask = _changed_mask(base[:common_h], cand[:common_h])
    if masks:
        _apply_masks(mask, masks)
    changed = int(mask.sum())
    total = mask.size
    changed_ratio = changed / total

    worst_ratio, worst_changed, worst_box = _worst_tile(mask)
    tile_failed = worst_ratio > TILE_TOLERANCE and worst_changed >= MIN_TILE_CHANGED_PIXELS
    passed = changed_ratio <= tolerance and not tile_failed

    if changed:
        box = _bbox(mask)
        notes.append(
            f"worst tile {worst_ratio * 100:.1f}% at "
            f"({worst_box[0]},{worst_box[1]})-({worst_box[2]},{worst_box[3]})"
        )
        if box is not None:
            notes.append(f"changed bbox ({box[0]},{box[1]})-({box[2]},{box[3]})")
        if tile_failed and changed_ratio <= tolerance:
            # Spell this out: the global number looks harmless and a reviewer
            # who only reads it will think the gate misfired.
            notes.append("localised change: global ratio under tolerance, tile is not")

    # Only render when there is a change or the sizes moved — an unchanged page
    # should not leave a magenta-free artefact behind for the reviewer to open.
    diff_image: Path | None = None
    if changed or bh != ch:
        diff_image = _write_diff_image(cand, mask, worst_box if changed else None, out_path)

    return DiffResult(
        key=key, changed_ratio=changed_ratio, passed=passed,
        baseline=baseline, candidate=candidate, diff_image=diff_image,
        note="; ".join(notes), worst_tile_ratio=worst_ratio,
    )


def diff_tree(baseline_dir: Path, candidate_dir: Path, out_dir: Path, *,
              tolerance: float,
              masks: Mapping[str, Sequence[tuple[int, int, int, int]]] | None = None) -> list[DiffResult]:
    """Compare every PNG under two `<viewport>/<page>.png` trees.

    The key set is the *union* of both trees, so a page present only in the
    candidates surfaces as "no baseline" and a page present only in the
    baselines surfaces as a missing-candidate failure. Keys are relative posix
    paths, so a report generated on macOS is byte-identical to one from CI.

    `masks` maps a key to its excluded rectangles. The literal key `"*"` applies
    to every image, for chrome that is volatile on all pages.
    """
    keys: set[str] = set()
    for root in (baseline_dir, candidate_dir):
        if root.is_dir():
            keys.update(p.relative_to(root).as_posix() for p in root.rglob("*.png"))

    results: list[DiffResult] = []
    for key in sorted(keys):
        per_key = list((masks or {}).get("*", ())) + list((masks or {}).get(key, ()))
        result = compare(
            baseline_dir / key,
            candidate_dir / key,
            out_dir / key,
            tolerance=tolerance,
            masks=per_key,
        )
        # compare() only sees two loose paths, so it guesses a two-segment key.
        # Here we know the real one.
        results.append(replace(result, key=key))

    # Failures first, then by key: the reader of a 20-page report should not
    # have to scan for the red lines.
    results.sort(key=lambda r: (r.passed, r.key))
    return results


def format_report(results: list[DiffResult]) -> str:
    """Render results as a fixed-width text report for stdout or a PR comment.

    Both metrics are always shown. The global ratio alone is misleading on tall
    pages (decision 1), and the worst-tile column is what actually justifies a
    failure, so hiding either would make the gate look arbitrary.
    """
    if not results:
        return "UX image diff: nothing to compare (no baselines and no candidates)."

    new = [r for r in results if r.baseline is None]
    failed = [r for r in results if not r.passed]
    compared = [r for r in results if r.baseline is not None and r.candidate is not None]

    width = max(len(r.key) for r in results)
    lines = [
        f"UX image diff — {len(compared)} compared, {len(failed)} failed, {len(new)} new",
        f"thresholds: per-tile {TILE_TOLERANCE * 100:.1f}% of a {TILE_SIZE}px tile "
        f"(min {MIN_TILE_CHANGED_PIXELS}px), channel delta {CHANNEL_THRESHOLD}/255",
        "",
    ]
    for r in results:
        if r.baseline is None:
            status = "NEW "
        elif r.passed:
            status = "PASS"
        else:
            status = "FAIL"
        lines.append(
            f"{status}  {r.key.ljust(width)}  "
            f"global {r.changed_ratio * 100:7.3f}%  worst tile {r.worst_tile_ratio * 100:6.2f}%"
        )
        if r.note:
            lines.append(f"      {r.note}")
        if r.diff_image is not None and not r.passed:
            lines.append(f"      diff: {r.diff_image}")

    lines.append("")
    lines.append("PASS" if not failed else f"FAILED: {len(failed)} of {len(results)} page(s) differ")
    return "\n".join(lines)

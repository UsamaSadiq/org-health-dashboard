#!/usr/bin/env python3
"""UX audit harness: screenshots, accessibility scan, and visual regression.

One command, no manual setup. Every mode boots its own headless Streamlit
server, drives it with Playwright, prints a report to stdout, and exits with a
status CI can gate on.

    python scripts/ux_audit.py --mode screenshots   # capture current state
    python scripts/ux_audit.py --mode a11y          # axe-core, fail on blocking
    python scripts/ux_audit.py --mode baseline      # (re)write reference PNGs
    python scripts/ux_audit.py --mode diff          # compare against baseline

Why this exists: the acceptance criteria in ``docs/UX_REMEDIATION_PLAN.md`` are
mostly visual, and unit tests cannot see a clipped axis or a 3.1:1 contrast
ratio. Per that plan the harness lands *before* the UI work it verifies, so each
subsequent work package can prove its own claims.

Output locations are fixed so that all modes and all contributors agree:

    tests/baseline/<viewport>/<page>.png    reference images, reviewed like code
    .ux-audit/current/<viewport>/<page>.png this run's captures (gitignored)
    .ux-audit/diff/<viewport>/<page>.png    highlighted differences (gitignored)
    .ux-audit/baseline-subset/              scratch, only for a narrowed diff

``--out`` overrides the primary output directory of the selected mode:
candidates for ``screenshots``, the baseline tree for ``baseline``, and the diff
image tree for ``diff``.

Exit codes: ``a11y`` returns 1 if any blocking violation was found, ``diff``
returns 1 if any comparison failed, everything else returns 0 unless the run
itself broke.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# scripts/ has no __init__.py and this file is run directly, so sys.path[0] is
# scripts/ rather than the repo root. Put the root first so `scripts.uxaudit.*`
# (a namespace package) and `dashboard.*` both resolve. Matches how the other
# scripts in this directory expect to be invoked from the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.uxaudit import a11y, imagediff  # noqa: E402
from scripts.uxaudit.app import DEFAULT_PORT, running_app  # noqa: E402
from scripts.uxaudit.capture import capture_all  # noqa: E402
from scripts.uxaudit.pages import PAGES, VIEWPORTS, PageSpec, resolve_pages  # noqa: E402

BASELINE_DIR = REPO_ROOT / "tests" / "baseline"
CURRENT_DIR = REPO_ROOT / ".ux-audit" / "current"
DIFF_DIR = REPO_ROOT / ".ux-audit" / "diff"
# Only used when --pages/--viewport narrow the run; see _scoped_baseline().
SUBSET_BASELINE_DIR = REPO_ROOT / ".ux-audit" / "baseline-subset"

BASELINE_WARNING = """
!! Baseline mode overwrites the reference images in tests/baseline/.
!! Those PNGs are reviewed like code: a changed baseline is a claim that the
!! new rendering is correct. Commit them in their own diff, describe what
!! changed and why, and never regenerate them to make `--mode diff` go green.
""".strip()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ux_audit.py",
        description="Screenshot, accessibility, and visual-regression audit of the dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Pages: " + ", ".join(page.name for page in PAGES) + "\n"
            "Viewports: " + ", ".join(f"{name} {w}x{h}" for name, (w, h) in VIEWPORTS.items())
        ),
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("screenshots", "a11y", "baseline", "diff"),
        help="What to do. See the module docstring for output locations.",
    )
    parser.add_argument(
        "--pages",
        default="",
        help="Comma-separated page names to audit. Default: all.",
    )
    parser.add_argument(
        "--viewport",
        default="all",
        choices=(*VIEWPORTS.keys(), "all"),
        help="Which viewport(s) to audit. Default: all.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            f"Port for the headless Streamlit server. Default: {DEFAULT_PORT} when free, "
            "otherwise an OS-assigned port. Stability matters: the share-link boxes "
            "render the live host:port, so a changing port shows up as a pixel diff."
        ),
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.001,
        help="Diff mode only: fraction of differing pixels tolerated per image. Default: 0.001.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Override the selected mode's primary output directory.",
    )
    return parser


def _selected_viewports(choice: str) -> dict[str, tuple[int, int]]:
    if choice == "all":
        return dict(VIEWPORTS)
    return {choice: VIEWPORTS[choice]}


def _parse_pages(raw: str) -> list[PageSpec]:
    names = [part.strip() for part in raw.split(",") if part.strip()]
    return resolve_pages(names)


def _announce(
    base_url: str, pages: list[PageSpec], viewports: dict[str, tuple[int, int]]
) -> None:
    """Say what is about to be audited, so a long run is not a silent one."""
    print(
        f"Serving {base_url} — {len(pages)} page(s) x {len(viewports)} viewport(s): "
        f"{', '.join(page.name for page in pages)} @ {', '.join(viewports)}",
        flush=True,
    )


def _report_captures(written: dict[str, Path], out_dir: Path) -> None:
    print(f"\nWrote {len(written)} screenshot(s) to {out_dir}")
    for key in sorted(written):
        print(f"  {key}")


def _run_screenshots(
    out_dir: Path, pages: list[PageSpec], viewports: dict[str, tuple[int, int]], port: int | None
) -> int:
    with running_app(port) as base_url:
        _announce(base_url, pages, viewports)
        written = capture_all(base_url, out_dir, pages=pages, viewports=viewports)
    _report_captures(written, out_dir)
    return 0


def _run_baseline(
    out_dir: Path, pages: list[PageSpec], viewports: dict[str, tuple[int, int]], port: int | None
) -> int:
    print(BASELINE_WARNING)
    with running_app(port) as base_url:
        _announce(base_url, pages, viewports)
        written = capture_all(base_url, out_dir, pages=pages, viewports=viewports)
    _report_captures(written, out_dir)
    return 0


def _run_a11y(
    pages: list[PageSpec], viewports: dict[str, tuple[int, int]], port: int | None
) -> int:
    with running_app(port) as base_url:
        _announce(base_url, pages, viewports)
        blocking, accepted = a11y.audit_all(base_url, pages=pages, viewports=viewports)
    print(a11y.format_report(blocking, accepted))
    return 1 if blocking else 0


def _selected_keys(
    pages: list[PageSpec], viewports: dict[str, tuple[int, int]]
) -> set[str]:
    """The ``<viewport>/<page>.png`` keys this run is responsible for."""
    return {f"{viewport}/{page.name}.png" for viewport in viewports for page in pages}


def _scoped_baseline(keys: set[str]) -> Path:
    """Return a baseline root containing only ``keys``.

    ``imagediff.diff_tree`` compares the *union* of the two trees, so a
    narrowed run (``--pages overview``) would otherwise report all thirteen
    unrequested baselines as missing-candidate failures. For a full-matrix run
    the real baseline directory is used unchanged, so reported paths stay
    meaningful; only a subset run pays for a throwaway copy.
    """
    if keys == _selected_keys(list(PAGES), VIEWPORTS):
        return BASELINE_DIR

    shutil.rmtree(SUBSET_BASELINE_DIR, ignore_errors=True)
    for key in sorted(keys):
        source = BASELINE_DIR / key
        if not source.is_file():
            continue  # diff_tree will report it as NEW, which is the truth
        target = SUBSET_BASELINE_DIR / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return SUBSET_BASELINE_DIR


def _run_diff(
    diff_out: Path,
    pages: list[PageSpec],
    viewports: dict[str, tuple[int, int]],
    port: int | None,
    tolerance: float,
) -> int:
    if not BASELINE_DIR.exists() or not any(BASELINE_DIR.rglob("*.png")):
        print(
            f"No baseline images under {BASELINE_DIR}.\n"
            "Run `python scripts/ux_audit.py --mode baseline` first, review the "
            "PNGs, and commit them.",
            file=sys.stderr,
        )
        return 1

    # Stale captures from an earlier run must never be diffed as if they were
    # this build's output.
    shutil.rmtree(CURRENT_DIR, ignore_errors=True)
    with running_app(port) as base_url:
        _announce(base_url, pages, viewports)
        capture_all(base_url, CURRENT_DIR, pages=pages, viewports=viewports)

    baseline_root = _scoped_baseline(_selected_keys(pages, viewports))
    results = imagediff.diff_tree(baseline_root, CURRENT_DIR, diff_out, tolerance=tolerance)
    print(imagediff.format_report(results))
    failed = [result for result in results if result.passed is False]
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        pages = _parse_pages(args.pages)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    viewports = _selected_viewports(args.viewport)

    if args.mode == "screenshots":
        return _run_screenshots(args.out or CURRENT_DIR, pages, viewports, args.port)
    if args.mode == "baseline":
        return _run_baseline(args.out or BASELINE_DIR, pages, viewports, args.port)
    if args.mode == "a11y":
        return _run_a11y(pages, viewports, args.port)
    return _run_diff(args.out or DIFF_DIR, pages, viewports, args.port, args.tolerance)


if __name__ == "__main__":
    raise SystemExit(main())

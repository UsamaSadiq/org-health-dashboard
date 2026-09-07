"""Optional local data source, for deterministic rendering.

The dashboard normally fetches both CSVs live from ``openedx/wg-maintenance``.
That is right in production and wrong for two other jobs:

  * **The visual gate.** ``scripts/ux_audit.py --mode diff`` compares rendered
    pixels against ``tests/baseline/``. Against live data, upstream churn — a
    repo added, a check flipping, a score moving a tenth — repaints the page
    with no code change, so the gate reports a failure nobody caused. Pinning
    the data is what lets a pixel difference mean "someone changed the UI".
  * **Offline work.** A cold checkout on a plane renders nothing at all.

Set ``DASHBOARD_DATA_FIXTURE`` to a directory holding the two files, named as
upstream names them::

    <dir>/dashboard_main.csv
    <dir>/dashboard_history.csv

``tests/fixtures/data/`` is the tracked one the harness uses.

Two deliberate choices. A *missing* file under a configured fixture directory is
a hard error, not a fall back to the network: the caller asked for a pinned run,
and silently giving them a live one is exactly the failure this module exists to
prevent. And fixture loads never write the ``.cache/`` last-known-good files —
otherwise a fixture run would leave pinned data behind as the fallback for the
next live run, and a stale-data bug would appear days later with no way to trace
it back to here.
"""
from __future__ import annotations

import os
from pathlib import Path

FIXTURE_DIR_ENV = "DASHBOARD_DATA_FIXTURE"

SNAPSHOT_FILENAME = "dashboard_main.csv"
HISTORY_FILENAME = "dashboard_history.csv"


def fixture_dir() -> Path | None:
    """Return the configured fixture directory, or None when unset.

    Raises:
        ValueError: If the variable is set to a path that is not a directory.
            A typo here would otherwise degrade into a silent live fetch.
    """
    raw = os.environ.get(FIXTURE_DIR_ENV)
    if not raw:
        return None

    path = Path(raw).expanduser()
    if not path.is_dir():
        raise ValueError(
            f"{FIXTURE_DIR_ENV}={raw!r} is not a directory. It must point at a "
            f"folder containing {SNAPSHOT_FILENAME} and {HISTORY_FILENAME}."
        )
    return path


def is_active() -> bool:
    """True if a fixture directory is configured."""
    return bool(os.environ.get(FIXTURE_DIR_ENV))


def snapshot_path() -> Path | None:
    """Path to the pinned snapshot CSV, or None when no fixture is configured."""
    return _resolve(SNAPSHOT_FILENAME)


def history_path() -> Path | None:
    """Path to the pinned history CSV, or None when no fixture is configured."""
    return _resolve(HISTORY_FILENAME)


def _resolve(filename: str) -> Path | None:
    directory = fixture_dir()
    if directory is None:
        return None

    path = directory / filename
    if not path.is_file():
        raise FileNotFoundError(
            f"{FIXTURE_DIR_ENV} points at {directory}, but {filename} is not "
            f"there. A fixture directory must contain both "
            f"{SNAPSHOT_FILENAME} and {HISTORY_FILENAME}."
        )
    return path

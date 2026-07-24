#!/usr/bin/env python3
"""Build a local history cache for offline WS6 testing.

The dashboard now reads trend history from a single pre-computed history file
(``dashboards/dashboard_history.csv``) instead of enumerating GitHub commit
history at runtime. In production that file is produced by the pipeline
aggregator. For LOCAL testing before the pipeline ships it, this script
reconstructs the same file from the git history of your local
``wg-maintenance`` clone and writes it to the dashboard's cache
(``.cache/dashboard_data/history.csv``), where ``load_history`` picks it up as
its offline fallback.

Usage:
    python scripts/build_local_history.py \
        [--repo ../wg-maintenance] \
        [--path dashboards/dashboard_main.csv]
"""
from __future__ import annotations

import argparse
import subprocess
from io import StringIO
from pathlib import Path

import pandas as pd

DASHBOARD_DIR = Path(__file__).resolve().parent.parent
CACHE_FILE = DASHBOARD_DIR / ".cache" / "dashboard_data" / "history.csv"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def build(repo: Path, path: str) -> pd.DataFrame:
    shas = _git(repo, "log", "--format=%H", "--", path).split()
    frames: list[pd.DataFrame] = []
    seen_timestamps: set[str] = set()
    for sha in shas:
        try:
            content = _git(repo, "show", f"{sha}:{path}")
        except subprocess.CalledProcessError:
            continue
        try:
            frame = pd.read_csv(StringIO(content))
        except pd.errors.EmptyDataError:
            continue
        if frame.empty or "TIMESTAMP" not in frame.columns:
            continue
        stamp = str(frame["TIMESTAMP"].iloc[0])
        if stamp in seen_timestamps:  # one block per snapshot date
            continue
        seen_timestamps.add(stamp)
        frames.append(frame)
    if not frames:
        raise SystemExit("No usable snapshots found in git history.")
    combined = pd.concat(frames, ignore_index=True)
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(DASHBOARD_DIR.parent / "wg-maintenance"))
    parser.add_argument("--path", default="dashboards/dashboard_main.csv")
    args = parser.parse_args()

    combined = build(Path(args.repo).resolve(), args.path)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(CACHE_FILE, index=False)
    snapshots = combined["TIMESTAMP"].nunique()
    print(f"Wrote {len(combined)} rows across {snapshots} snapshot dates to {CACHE_FILE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dashboard.lib.clock import now_utc
from dashboard.lib.config import get_config
from dashboard.lib.data import DEFAULT_CSV_URL, load_snapshot
from dashboard.lib.scores_export import build_history_payload, build_snapshot_payload, dumps
from dashboard.lib.scoring import calculate_scores
from dashboard.lib.tiers import annotate_tiers
from dashboard.lib.trends import Snapshot, load_history

SNAPSHOT_FILENAME = "scores.json"
HISTORY_FILENAME = "scores_history.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write pre-computed score files.")
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def _scored_history() -> list[Snapshot]:
    return [
        Snapshot(timestamp=snapshot.timestamp, df=calculate_scores(snapshot.df))
        for snapshot in load_history()
    ]


def main() -> int:
    args = _parse_args()
    cfg = get_config("data_source")
    min_rows = int(cfg.get("expected_min_rows", 1))

    scored = calculate_scores(annotate_tiers(load_snapshot()))
    if len(scored) < min_rows:
        print(f"Snapshot has {len(scored)} rows, expected at least {min_rows}; not writing.")
        return 1

    scored_history = _scored_history()
    if not scored_history:
        print("History is empty; not writing.")
        return 1

    generated_at = now_utc()
    snapshot_url = cfg.get("csv_url", DEFAULT_CSV_URL)
    history_url = cfg.get("history_csv_url") or snapshot_url.replace(
        "dashboard_main.csv", "dashboard_history.csv"
    )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    snapshot_payload = build_snapshot_payload(scored, generated_at=generated_at, source_url=snapshot_url)
    (args.out_dir / SNAPSHOT_FILENAME).write_text(dumps(snapshot_payload), encoding="utf-8")

    history_payload = build_history_payload(
        scored_history, generated_at=generated_at, source_url=history_url
    )
    (args.out_dir / HISTORY_FILENAME).write_text(dumps(history_payload), encoding="utf-8")

    print(
        f"Wrote {len(snapshot_payload['records'])} repos and "
        f"{len(history_payload['snapshots'])} history snapshots to {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

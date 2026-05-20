#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASK_FILE = ROOT / "docs" / "prd_tasks_phase1.yaml"
DEFAULT_STATUS_FILE = ROOT / "docs" / "PRD_STATUS.md"


def _status_mark(status: str) -> str:
    mapping = {
        "done": "[x]",
        "partial": "[-]",
        "todo": "[ ]",
    }
    return mapping.get(status, "[ ]")


def _load_tasks(task_file: Path) -> dict:
    with task_file.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def _write_tasks(task_file: Path, payload: dict) -> None:
    with task_file.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(payload, stream, sort_keys=False, allow_unicode=False)


def _render_status(payload: dict, task_file: Path) -> str:
    phase = payload.get("phase", "Phase 01")
    items = payload.get("items", [])

    done = sum(1 for i in items if i.get("status") == "done")
    partial = sum(1 for i in items if i.get("status") == "partial")
    todo = sum(1 for i in items if i.get("status") not in {"done", "partial"})

    lines = [
        "# PRD Status",
        "",
        f"Generated from {task_file.name}",
        "",
        f"## {phase}",
        "",
        f"- done: {done}",
        f"- partial: {partial}",
        f"- todo: {todo}",
        "",
    ]

    for item in items:
        mark = _status_mark(str(item.get("status", "todo")))
        lines.append(f"- {mark} {item.get('id', '?')} {item.get('title', 'Untitled')}")
        notes = str(item.get("notes", "")).strip()
        if notes:
            lines.append(f"  - {notes}")
    lines.append("")
    return "\n".join(lines)


def _write_status(status_file: Path, payload: dict, task_file: Path) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(_render_status(payload, task_file), encoding="utf-8")


def _set_item_status(payload: dict, item_id: str, status: str, notes: str | None) -> bool:
    items = payload.get("items", [])
    for item in items:
        if str(item.get("id")) == item_id:
            item["status"] = status
            if notes is not None:
                item["notes"] = notes
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Update PRD task status and regenerate PRD_STATUS.md")
    parser.add_argument("--set", nargs=2, metavar=("ID", "STATUS"), help="Set item status. STATUS: done|partial|todo")
    parser.add_argument("--notes", help="Optional notes for --set updates")
    parser.add_argument("--generate-only", action="store_true", help="Only regenerate PRD_STATUS.md from task file")
    parser.add_argument(
        "--task-file",
        default=str(DEFAULT_TASK_FILE.relative_to(ROOT)),
        help="Task YAML file path, relative to repo root",
    )
    parser.add_argument(
        "--status-file",
        default=str(DEFAULT_STATUS_FILE.relative_to(ROOT)),
        help="Status markdown output path, relative to repo root",
    )
    args = parser.parse_args()

    task_file = (ROOT / args.task_file).resolve()
    status_file = (ROOT / args.status_file).resolve()
    payload = _load_tasks(task_file)

    if args.set:
        item_id, status = args.set
        status = status.strip().lower()
        if status not in {"done", "partial", "todo"}:
            print("Invalid status. Use: done|partial|todo")
            return 2
        updated = _set_item_status(payload, item_id=item_id, status=status, notes=args.notes)
        if not updated:
            print(f"Task id not found: {item_id}")
            return 3
        _write_tasks(task_file, payload)

    _write_status(status_file, payload, task_file)
    print(f"Updated {status_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "dashboard", ROOT / "pages"]
EXCLUDE_SUFFIXES = {".pyc"}


def scan_for_hardcoded_strings() -> list[str]:
    issues: list[str] = []
    for directory in SCAN_DIRS:
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if path.suffix in EXCLUDE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            for idx, line in enumerate(text.splitlines(), start=1):
                line_strip = line.strip()
                if "st." in line_strip and '"' in line_strip and "strings" not in line_strip:
                    if "http" in line_strip:
                        continue
                    issues.append(f"{path.relative_to(ROOT)}:{idx}:{line_strip[:120]}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check i18n readiness.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when issues are found.")
    args = parser.parse_args()

    issues = scan_for_hardcoded_strings()
    if not issues:
        print("No obvious hardcoded Streamlit strings found.")
        return 0

    print("Potential hardcoded user-facing strings:")
    for issue in issues:
        print(f"- {issue}")

    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())

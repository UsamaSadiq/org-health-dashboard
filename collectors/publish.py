"""Write collector output in the same envelope as ``scores.json``."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from dashboard.lib.scores_export import dumps

SCHEMA_VERSION = 1


def payload(records: list[dict[str, Any]], *, generated_at: datetime, source: str, **metadata: Any) -> dict[str, Any]:
    return {
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at.isoformat(),
            "source": source,
            **metadata,
        },
        "records": records,
    }


def write(path: Path, content: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(content), encoding="utf-8")

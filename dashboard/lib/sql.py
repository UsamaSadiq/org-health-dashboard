from __future__ import annotations

import re

FORBIDDEN_SQL_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\bcreate\b",
    r"\battach\b",
    r"\bdetach\b",
    r"\bcopy\b",
    r"\bcall\b",
    r"\bpragma\b",
]

ALLOWED_SQL_PREFIXES = ("select", "with", "show", "describe")


class UnsafeQueryError(ValueError):
    """Raised when SQL query is not safe for read-only execution."""


def sanitize_readonly_query(query: str, row_limit: int = 500) -> str:
    """Validate a read-only SQL query and enforce a row limit wrapper.

    The query must be a single statement and start with a read-only prefix.
    Queries are wrapped to enforce a hard output row cap.
    """
    normalized = (query or "").strip()
    if not normalized:
        raise UnsafeQueryError("Query is empty.")

    if ";" in normalized[:-1]:
        raise UnsafeQueryError("Only a single SQL statement is allowed.")

    if normalized.endswith(";"):
        normalized = normalized[:-1].strip()

    lowered = normalized.lower()
    if not lowered.startswith(ALLOWED_SQL_PREFIXES):
        raise UnsafeQueryError("Only SELECT/WITH/SHOW/DESCRIBE queries are allowed.")

    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, lowered):
            raise UnsafeQueryError("Query contains forbidden SQL operation.")

    if lowered.startswith(("show", "describe")):
        return normalized

    safe_limit = max(1, min(int(row_limit), 5000))
    return f"SELECT * FROM ({normalized}) AS readonly_query LIMIT {safe_limit}"

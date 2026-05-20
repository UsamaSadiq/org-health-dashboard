import pytest

from dashboard.lib.sql import UnsafeQueryError, sanitize_readonly_query


def test_sanitize_allows_select_and_wraps_limit():
    sql = sanitize_readonly_query("SELECT repo_name FROM snapshot", row_limit=123)
    assert sql.startswith("SELECT * FROM (")
    assert "LIMIT 123" in sql


def test_sanitize_rejects_mutating_keywords():
    with pytest.raises(UnsafeQueryError):
        sanitize_readonly_query("DELETE FROM snapshot")


def test_sanitize_rejects_multi_statement():
    with pytest.raises(UnsafeQueryError):
        sanitize_readonly_query("SELECT 1; SELECT 2")

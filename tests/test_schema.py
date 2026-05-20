from dashboard.lib.schema import parse_last_push_utc, parse_snapshot_date


def test_parse_snapshot_date():
    parsed = parse_snapshot_date("2026-05-08")
    assert parsed is not None
    assert parsed.isoformat() == "2026-05-08"


def test_parse_last_push_utc():
    parsed = parse_last_push_utc("2026-05-08 12:30:45")
    assert parsed is not None
    assert parsed.tzinfo is not None

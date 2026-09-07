"""The pinned-clock contract that the visual gate depends on.

If these fail, ``--mode diff`` starts failing on unchanged code a day later,
which is a much harder failure to diagnose than a red test here.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dashboard.lib import clock


def test_unfrozen_clock_tracks_wall_time(monkeypatch):
    monkeypatch.delenv(clock.FROZEN_NOW_ENV, raising=False)

    before = datetime.now(timezone.utc)
    observed = clock.now_utc()
    after = datetime.now(timezone.utc)

    assert before <= observed <= after
    assert observed.tzinfo is not None
    assert not clock.is_frozen()


def test_frozen_clock_returns_the_pinned_instant(monkeypatch):
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "2026-08-31T12:00:00+00:00")

    assert clock.is_frozen()
    assert clock.now_utc() == datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    # Pinned means pinned: two reads in the same run must not drift.
    assert clock.now_utc() == clock.now_utc()


def test_naive_value_is_read_as_utc_not_local(monkeypatch):
    """A naive pin must not inherit the runner's timezone.

    CI runs in UTC and a developer's laptop does not; reading a naive value as
    local time would put an offset back into the value whose entire job is to
    remove one, and the baselines would differ by timezone.
    """
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "2026-08-31T12:00:00")

    assert clock.now_utc() == datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def test_offset_value_is_normalised_to_utc(monkeypatch):
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "2026-08-31T17:00:00+05:00")

    observed = clock.now_utc()
    assert observed == datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    assert observed.utcoffset() == timedelta(0)


def test_unparseable_pin_raises_rather_than_silently_unfreezing(monkeypatch):
    """The caller asked for determinism; giving them wall-clock instead is worse
    than failing, because the resulting gate failure surfaces days later with no
    trace back to the typo that caused it."""
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "last tuesday")

    with pytest.raises(ValueError, match=clock.FROZEN_NOW_ENV):
        clock.now_utc()


def test_empty_value_means_unfrozen(monkeypatch):
    """An explicit empty value is how the harness's override documents itself."""
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "")

    assert not clock.is_frozen()
    assert clock.now_utc() > datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_frozen_now_context_manager_restores_previous_state(monkeypatch):
    monkeypatch.setenv(clock.FROZEN_NOW_ENV, "2026-01-01T00:00:00+00:00")

    with clock.frozen_now("2026-08-31T12:00:00+00:00") as pinned:
        assert pinned == datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
        assert clock.now_utc() == pinned

    assert clock.now_utc() == datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_frozen_now_context_manager_unsets_when_it_was_unset(monkeypatch):
    monkeypatch.delenv(clock.FROZEN_NOW_ENV, raising=False)

    with clock.frozen_now(datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)):
        assert clock.is_frozen()

    assert not clock.is_frozen()


def test_rendered_freshness_follows_the_pinned_clock():
    """The end-to-end reason this module exists.

    The freshness chip is a pure function of (snapshot date, now). Pinned, it
    renders the same string forever; unpinned it changes daily, which is exactly
    what made the pixel gate unrunnable.
    """
    from datetime import date

    from dashboard.ui.banners import freshness_chip_html

    snapshot = date(2026, 8, 31)
    with clock.frozen_now("2026-08-31T12:00:00+00:00"):
        same_day = freshness_chip_html(snapshot, stale_hours=48, critical_hours=168)
    with clock.frozen_now("2026-09-09T12:00:00+00:00"):
        nine_days_later = freshness_chip_html(snapshot, stale_hours=48, critical_hours=168)

    assert same_day != nine_days_later
    assert "9d ago" in nine_days_later
    # And re-reading under the same pin is stable, which is the gate's premise.
    with clock.frozen_now("2026-08-31T12:00:00+00:00"):
        assert freshness_chip_html(snapshot, stale_hours=48, critical_hours=168) == same_day

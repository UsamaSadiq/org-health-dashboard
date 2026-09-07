"""The single source of "now" for the dashboard.

Every wall-clock read in rendered code goes through :func:`now_utc`. That is one
import more than ``datetime.now(timezone.utc)``, and it buys two things.

**The visual gate becomes possible.** ``scripts/ux_audit.py --mode diff``
compares rendered pixels against ``tests/baseline/``. Several rendered strings
are functions of the clock rather than of the code: the sidebar freshness chip
reads "9d ago", the staleness banner reads "This data is 9 days old", the
bulletin stamps "Generated: <timestamp>", and Needing Attention evaluates its
rules against the current instant. Left on the wall clock, those strings change
between the moment a baseline is captured and every later run, so the gate fails
on unchanged code — and a gate that cannot pass teaches people to ignore gates.
``scripts/uxaudit/pages.py`` says the same thing from the other side: masking a
volatile region hides real regressions inside it, so the better answer is to
make the value injectable and pin it.

**Time-dependent behaviour becomes testable.** Asserting that a 50-hour-old
snapshot renders the stale banner previously meant monkeypatching ``datetime``
in whichever module happened to import it. Now it is one environment variable,
or :func:`frozen_now` in-process.

Freezing is opt-in and absent by default, so production is wall-clock as before.

Set ``DASHBOARD_FROZEN_NOW`` to an ISO 8601 timestamp to pin the clock::

    DASHBOARD_FROZEN_NOW=2026-08-31T12:00:00+00:00 streamlit run streamlit_app.py

A value without an offset is read as UTC. An unparseable value is a hard error
rather than a silent fall back to the wall clock: the caller asked for a
deterministic run, and quietly giving them a non-deterministic one produces a
gate that fails days later for reasons nobody can reconstruct.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

FROZEN_NOW_ENV = "DASHBOARD_FROZEN_NOW"


def now_utc() -> datetime:
    """Return the current UTC time, or the pinned instant when frozen.

    Returns:
        A timezone-aware ``datetime`` in UTC.

    Raises:
        ValueError: If ``DASHBOARD_FROZEN_NOW`` is set but not ISO 8601.
    """
    raw = os.environ.get(FROZEN_NOW_ENV)
    if not raw:
        return datetime.now(timezone.utc)

    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"{FROZEN_NOW_ENV}={raw!r} is not an ISO 8601 timestamp "
            f"(e.g. 2026-08-31T12:00:00+00:00)."
        ) from exc

    # A naive value is taken as UTC rather than local time: every consumer of
    # this module works in UTC, and inheriting the runner's timezone would put
    # the offset back into a value whose whole purpose is to remove it.
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_frozen() -> bool:
    """True if the clock is currently pinned by the environment."""
    return bool(os.environ.get(FROZEN_NOW_ENV))


@contextmanager
def frozen_now(moment: datetime | str) -> Iterator[datetime]:
    """Pin :func:`now_utc` to ``moment`` for the duration of the block.

    For tests and scripts running in-process. The harness pins the clock for the
    Streamlit *child* process through the environment instead; see
    ``scripts/uxaudit/app.py``.

    Args:
        moment: The instant to pin, as a ``datetime`` or an ISO 8601 string.

    Yields:
        The pinned instant, as :func:`now_utc` will report it.
    """
    value = moment.isoformat() if isinstance(moment, datetime) else moment
    previous = os.environ.get(FROZEN_NOW_ENV)
    os.environ[FROZEN_NOW_ENV] = value
    try:
        yield now_utc()
    finally:
        if previous is None:
            os.environ.pop(FROZEN_NOW_ENV, None)
        else:
            os.environ[FROZEN_NOW_ENV] = previous

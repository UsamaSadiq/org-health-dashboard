"""Total orderings for anything the dashboard ranks.

Sorting a health score puts many repositories on the same value — 62 repos share
grade A, five sat on exactly -25.5 in one snapshot's movers table — and pandas'
default ``sort_values(kind="quicksort")`` is not a stable sort. Tied rows come
back in whatever order the underlying partition happened to produce, which is a
function of the numpy build rather than of the data.

The consequence is not theoretical. The visual gate caught it: the same fixture,
rendered on two machines, produced different "Top 5" lists (`openedx/XBlock` on
one, `openedx/openedx-filters` on the other, both scoring 93.3) and permuted the
gainers and losers tables. Whichever machine you read the dashboard from, you
were seeing an arbitrary choice among equals presented as a ranking.

Sorting on ``(value, repo_name)`` makes the order total, because ``repo_name`` is
unique. Ties then resolve alphabetically — still arbitrary as a matter of merit,
but *stated* and identical everywhere, which is the property both a reader and a
pixel diff need.

This does not address the separate question of whether a tie should be *visible*
to the reader ("5 of 23 repos tied at 96.7"); that is backlog B9 and a
presentation decision.
"""
from __future__ import annotations

import pandas as pd

from dashboard.lib.schema import REPO_COL


def rank(
    df: pd.DataFrame,
    by: str | list[str],
    *,
    ascending: bool | list[bool] = True,
    tiebreak: str = REPO_COL,
) -> pd.DataFrame:
    """Sort ``df`` by ``by``, breaking ties on ``tiebreak`` for a total order.

    Args:
        df: Frame to sort. Returned unchanged if empty.
        by: Column or columns to sort on, in priority order.
        ascending: Direction, per ``by`` column. A single bool applies to all.
        tiebreak: Unique column appended as the final sort key, always
            ascending. Ignored if absent from the frame.

    Returns:
        A new frame with a reset index, ordered identically on every machine.
    """
    if df.empty:
        return df

    columns = [by] if isinstance(by, str) else list(by)
    directions = [ascending] * len(columns) if isinstance(ascending, bool) else list(ascending)

    if tiebreak in df.columns and tiebreak not in columns:
        columns.append(tiebreak)
        # Always ascending: the tiebreak exists to be predictable, not to carry
        # meaning, and flipping it with the primary key would make "the same
        # repos in reverse" quietly stop being the same repos.
        directions.append(True)

    # mergesort is pandas' stable option. Stability is belt-and-braces given the
    # explicit tiebreak, but it costs nothing and keeps the result well defined
    # if a caller ever passes a tiebreak that is not actually unique.
    return df.sort_values(columns, ascending=directions, kind="mergesort").reset_index(drop=True)


def top(df: pd.DataFrame, by: str, count: int, *, tiebreak: str = REPO_COL) -> pd.DataFrame:
    """The ``count`` highest rows by ``by``, ties broken deterministically.

    Replaces ``nlargest``, which resolves ties by position in the input and so
    inherits whatever order produced that input.
    """
    return rank(df, by, ascending=False, tiebreak=tiebreak).head(count)


def bottom(df: pd.DataFrame, by: str, count: int, *, tiebreak: str = REPO_COL) -> pd.DataFrame:
    """The ``count`` lowest rows by ``by``, ties broken deterministically.

    Note this returns them in ascending order — worst first — which is how both
    a "biggest losers" table and a "bottom 5" list want to read. Callers that
    want the opposite should reverse explicitly rather than sorting again.
    """
    return rank(df, by, ascending=True, tiebreak=tiebreak).head(count)

"""One table renderer, one column vocabulary.

This module was a seven-line stub, which is why five pages each grew their own
table and every one of them leaked raw dataframe column names at the reader:
``repo_name``, ``score_composite``, ``delta``. Streamlit's ``column_config`` was
barely used — only ``LinkColumn``, and never with a display label, so link cells
showed full URLs truncated mid-string.

The fix is a shared renderer plus a central column vocabulary. Anything named in
:data:`COLUMN_LABELS` is formatted the same way everywhere it appears, so
"Score" means one thing on Overview, Failing Checks and Needing Attention. A page
that needs something specific passes ``extra_config``; it does not hand-roll the
common columns again.

Two deliberate constraints:

**``hide_index`` is not a parameter.** Streamlit shows the dataframe index by
default, and a page that forgot it exposed a column of internal row numbers as
the reader's first column (backlog A8). Making it a non-overridable default fixes
the class rather than the instance.

**Numeric formats are shared.** Deltas carry an explicit sign, because a bare
``-15`` beside ``44`` in the movers tables gave no clue they were the same
quantity.

Grade rendering deserves a note. ``st.dataframe`` cannot host the HTML grade pill
used elsewhere in the UI, so the table shows the letter as text. That is a real
inconsistency with :func:`dashboard.ui.theme.render_repo_pill_list`, and the
alternative — hand-building an HTML table to get pills — would lose sorting,
resizing and column configuration. Sorting wins.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.lib.share import share_link

# Column vocabulary. Keys are dataframe column names; values are display labels.
# A column absent from here renders under its own name, which is correct for
# ad-hoc output (the SQL page) and a bug anywhere else.
COLUMN_LABELS: dict[str, str] = {
    "repo_name": "Repository",
    "score_composite": "Score",
    "score_letter": "Grade",
    "score_structural": "Structural",
    "score_activity": "Activity",
    "repo_tier": "Tier",
    "reasons": "Why flagged",
    "delta": "Change",
    "repo_link": "Detail",
    "check": "Check",
    "fail_count": "Repos failing",
    "repo_count": "Repositories",
    "avg_score": "Average score",
    "d_or_f": "Grade D or F",
    "score": "Score",
    "reason": "Detail",
}

NUMBER_FORMATS: dict[str, str] = {
    "score_composite": "%.1f",
    "score_structural": "%.1f",
    "score_activity": "%.1f",
    "avg_score": "%.1f",
    "delta": "%+.1f",
    "score": "%.2f",
}

# Columns rendered as a bar rather than a bare number. Only 0-100 scores qualify.
PROGRESS_COLUMNS = {"score_composite"}

NARROW_COLUMNS = {"score_letter", "repo_tier", "d_or_f", "fail_count", "repo_count"}


def _column_config(
    df: pd.DataFrame,
    *,
    use_progress: bool,
    link_label: str,
    extra: dict | None = None,
) -> dict:
    """Build the Streamlit column config for the columns actually present."""
    config: dict = {}
    for column in df.columns:
        if column == "repo_link":
            # display_text is what stops a full URL being used as link text and
            # then truncated mid-string.
            config[column] = st.column_config.LinkColumn(
                COLUMN_LABELS.get(column, ""), display_text=link_label
            )
            continue

        label = COLUMN_LABELS.get(column, column)

        if column in PROGRESS_COLUMNS and use_progress:
            config[column] = st.column_config.ProgressColumn(
                label, min_value=0, max_value=100, format=NUMBER_FORMATS.get(column, "%.1f")
            )
        elif column in NUMBER_FORMATS:
            config[column] = st.column_config.NumberColumn(label, format=NUMBER_FORMATS[column])
        elif pd.api.types.is_numeric_dtype(df[column]):
            config[column] = st.column_config.NumberColumn(label)
        elif column in NARROW_COLUMNS:
            config[column] = st.column_config.TextColumn(label, width="small")
        else:
            config[column] = st.column_config.TextColumn(label)
    if extra:
        config.update(extra)
    return config


def add_detail_links(df: pd.DataFrame, *, repo_column: str = "repo_name") -> pd.DataFrame:
    """Return a copy with a ``repo_link`` column pointing at Repo Detail.

    Centralised so pages stop rebuilding the same ``share_link`` mapping, and so
    the link column is always named the one thing the config expects.
    """
    if df.empty or repo_column not in df.columns:
        return df
    out = df.copy()
    out["repo_link"] = out[repo_column].map(
        lambda repo: share_link({"tab": "detail", "repo": str(repo)})
    )
    return out


def repo_table(
    df: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    link_to_detail: bool = False,
    link_label: str = "Open",
    use_progress: bool = False,
    height: int | None = None,
    extra_config: dict | None = None,
    empty_message: str = "No repositories to show.",
) -> None:
    """Render a table with the shared column vocabulary.

    Args:
        df: Frame to render.
        columns: Subset and ordering to display. Unknown names are ignored, so a
            caller can ask for optional columns without guarding on presence.
            The sharp edge: a *misspelled* name is also ignored, so the column
            simply disappears rather than raising. This bit once already —
            requesting ``repo_tier`` from a frame that spelled it ``tier`` dropped
            the Tier column silently. Use the canonical names from
            :data:`COLUMN_LABELS`.
        link_to_detail: Append a Repo Detail link column.
        link_label: Text shown in the link cell.
        use_progress: Render the composite score as a bar. Suits a ranked list;
            avoid where the reader compares exact values.
        height: Fixed pixel height, for long tables that would otherwise run to
            several thousand pixels.
        extra_config: Per-call ``column_config`` entries, merged last.
        empty_message: Caption shown instead of an empty grid.
    """
    if df is None or df.empty:
        st.caption(empty_message)
        return

    frame = df
    if columns:
        present = [column for column in columns if column in frame.columns]
        if present:
            frame = frame[present]

    if link_to_detail:
        frame = add_detail_links(frame)

    # height is omitted rather than passed as None: this Streamlit version
    # validates the argument and rejects None with StreamlitInvalidHeightError,
    # so the "no explicit height" case must not supply the keyword at all.
    size_kwargs = {"height": height} if height is not None else {}

    st.dataframe(
        frame,
        width="stretch",
        # Not a parameter: see the module docstring. The dataframe index is an
        # implementation detail that was being shown to readers as data.
        hide_index=True,
        column_config=_column_config(
            frame, use_progress=use_progress, link_label=link_label, extra=extra_config
        ),
        **size_kwargs,
    )


def repo_grade_table(df: pd.DataFrame) -> pd.DataFrame:
    """Ranked (repo, score, grade) projection.

    Pre-existing helper, kept because callers use it for the projection itself
    rather than for rendering.
    """
    return df[["repo_name", "score_composite", "score_letter"]].sort_values(
        "score_composite", ascending=False
    )

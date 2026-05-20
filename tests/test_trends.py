import pandas as pd

from dashboard.lib.trends import summarize_weekly_changes


def test_summarize_weekly_changes_detects_new_failures():
    previous = pd.DataFrame([
        {"repo_name": "openedx/edx-platform", "exists.openedx.yaml": True}
    ])
    current = pd.DataFrame([
        {"repo_name": "openedx/edx-platform", "exists.openedx.yaml": False}
    ])
    summary = summarize_weekly_changes(current, previous)
    assert len(summary["new_failures"]) == 1

import pandas as pd

from dashboard.lib import trends
from dashboard.lib.trends import load_history, summarize_weekly_changes


def test_summarize_weekly_changes_detects_new_failures():
    previous = pd.DataFrame([
        {"repo_name": "openedx/edx-platform", "exists.openedx.yaml": True}
    ])
    current = pd.DataFrame([
        {"repo_name": "openedx/edx-platform", "exists.openedx.yaml": False}
    ])
    summary = summarize_weekly_changes(current, previous)
    assert len(summary["new_failures"]) == 1


def test_load_history_reads_single_file_no_github_api(monkeypatch):
    """History comes from one static-file fetch, split by TIMESTAMP — no API calls."""
    history_csv = (
        "repo_name,TIMESTAMP,exists.openedx.yaml\n"
        "openedx/edx-platform,2026-05-01,True\n"
        "openedx/xblock,2026-05-01,False\n"
        "openedx/edx-platform,2026-05-08,True\n"
        "openedx/xblock,2026-05-08,True\n"
    )
    requested_urls: list[str] = []

    class _Resp:
        text = history_csv
        status_code = 200

        def raise_for_status(self):
            return None

    def _fake_get(url, timeout=30):
        requested_urls.append(url)
        return _Resp()

    monkeypatch.setattr(trends.requests, "get", _fake_get)
    # Force the remote path (ignore any pre-existing local cache).
    monkeypatch.setattr(trends, "_HISTORY_CACHE", trends._HISTORY_CACHE.with_name("nonexistent_history.csv"))

    snapshots = load_history(days=90)

    assert len(snapshots) == 2
    assert [s.timestamp.isoformat() for s in snapshots] == ["2026-05-01", "2026-05-08"]
    assert len(snapshots[0].df) == 2  # two repos per snapshot block
    assert len(requested_urls) == 1  # exactly one fetch
    assert all("api.github.com" not in url for url in requested_urls)

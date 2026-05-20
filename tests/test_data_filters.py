import pandas as pd

from dashboard.lib import data


def test_load_my_repos_matches_repo_owner(monkeypatch):
    frame = pd.DataFrame(
        {
            "repo_name": ["openedx/edx-platform", "example/other"],
            "ownership.theme": ["", ""],
            "ownership.squad": ["", ""],
        }
    )
    monkeypatch.setattr(data, "load_snapshot", lambda: frame)

    result = data.load_my_repos("openedx")
    assert len(result) == 1
    assert result.iloc[0]["repo_name"] == "openedx/edx-platform"


def test_load_my_repos_matches_maintainers_token(monkeypatch):
    frame = pd.DataFrame(
        {
            "repo_name": ["example/repo"],
            "maintainers": ["[@Usama_Sadiq, someone_else]"],
        }
    )
    monkeypatch.setattr(data, "load_snapshot", lambda: frame)

    result = data.load_my_repos("usama_sadiq")
    assert len(result) == 1


def test_load_my_repos_matches_ownership_owner(monkeypatch):
    frame = pd.DataFrame(
        {
            "repo_name": ["example/repo", "another/repo"],
            "ownership.owner": ["user:alice", "group:axim-admins"],
        }
    )
    monkeypatch.setattr(data, "load_snapshot", lambda: frame)

    result = data.load_my_repos("alice")
    assert len(result) == 1
    assert result.iloc[0]["repo_name"] == "example/repo"

import pandas as pd

from dashboard.lib.scoring import calculate_scores


def test_calculate_scores_adds_expected_columns():
    df = pd.DataFrame(
        [
            {
                "repo_name": "openedx/edx-platform",
                "github.last_push": "2026-05-15 00:00:00",
                "github_actions": True,
                "exists.openedx.yaml": True,
                "dependabot.exists": True,
                "renovate.configured": False,
                "readme.getting-help": True,
                "readme.security": True,
            }
        ]
    )
    scored = calculate_scores(df)
    assert "score_composite" in scored.columns
    assert "score_letter" in scored.columns
    assert scored.iloc[0]["score_letter"] in {"A", "B", "C", "D", "F"}

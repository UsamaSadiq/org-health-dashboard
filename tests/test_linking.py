from dashboard.lib.linking import github_issue_url, normalize_params


def test_normalize_params_redirects_old_keys():
    params = normalize_params({"repository": "openedx/edx-platform", "section": "detail"})
    assert params["repo"] == "openedx/edx-platform"
    assert params["tab"] == "detail"


def test_github_issue_url_contains_prefill_fields():
    url = github_issue_url("openedx/edx-platform", "github_actions", "body")
    assert "issues/new" in url
    assert "title=" in url
    assert "body=" in url

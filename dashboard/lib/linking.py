from __future__ import annotations

from urllib.parse import urlencode

REDIRECT_PARAM_MAP = {
    "repository": "repo",
    "repo_name": "repo",
    "section": "tab",
}

DEFAULT_VIEW_STATE = {
    "tab": "overview",
    "archived": "false",
    "view": "charts",
    "search": "",
}


def normalize_params(params: dict[str, str]) -> dict[str, str]:
    """Normalize old parameter names and apply defaults."""
    normalized: dict[str, str] = {}
    for key, value in params.items():
        new_key = REDIRECT_PARAM_MAP.get(key, key)
        normalized[new_key] = value
    for key, default in DEFAULT_VIEW_STATE.items():
        normalized.setdefault(key, default)
    return normalized


def serialize_state(state: dict[str, str]) -> str:
    """Serialize query params to a compact query string."""
    cleaned = {key: value for key, value in state.items() if value not in (None, "")}
    return urlencode(cleaned, doseq=True)


def github_issue_url(
    repo: str,
    check: str,
    body_template: str,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    projects: list[str] | None = None,
    milestone: str | None = None,
    issue_type: str | None = None,
    template: str | None = None,
) -> str:
    """Build issue URL with prefilled title/body and optional metadata."""
    title = f"[Repo health] Fix failing check: {check}"
    body = body_template.strip()
    query = {
        "title": title,
        "body": body,
    }
    if template:
        query["template"] = template
    if labels:
        query["labels"] = ",".join(labels)
    if assignees:
        query["assignees"] = ",".join(assignees)
    if projects:
        query["projects"] = ",".join(projects)
    if milestone:
        query["milestone"] = milestone
    if issue_type:
        query["type"] = issue_type
    return f"https://github.com/{repo}/issues/new?{urlencode(query)}"


def github_pr_compare_url(repo: str, branch: str, title: str, body: str) -> str:
    """Build GitHub compare URL for quick pull request creation."""
    query = {
        "quick_pull": "1",
        "title": title,
        "body": body,
    }
    return f"https://github.com/{repo}/compare/main...{branch}?{urlencode(query)}"

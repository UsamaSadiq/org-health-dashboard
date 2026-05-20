from dashboard.lib.scorecard import fetch_scorecard_result


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_fetch_scorecard_result_parses_payload(monkeypatch):
    payload = {
        "score": 7.8,
        "date": "2026-05-20",
        "checks": [
            {"name": "CI-Tests", "score": 10, "reason": "all checks pass"},
            {"name": "Maintained", "score": 5, "reason": "few commits"},
        ],
    }

    def _fake_get(url, timeout):
        assert "api.securityscorecards.dev" in url
        return _FakeResponse(payload)

    monkeypatch.setattr("dashboard.lib.scorecard.requests.get", _fake_get)

    result = fetch_scorecard_result("openedx/edx-platform")
    assert result is not None
    assert result.score == 7.8
    assert len(result.checks) == 2
    assert result.checks[0].name == "CI-Tests"


def test_fetch_scorecard_result_returns_none_for_bad_repo():
    assert fetch_scorecard_result("bad-repo-name") is None

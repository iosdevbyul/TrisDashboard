from backend import integrations


def test_github_provider_rejects_cross_site_pr_links(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/repo")
    def fake(url):
        if "/pulls?" in url:
            return [{"number": 12, "title": "Valid", "html_url": "https://github.com/owner/repo/pull/12"},
                    {"number": 13, "title": "Bad", "html_url": "https://evil.example/a"}]
        return {"workflow_runs": [{"status": "completed", "conclusion": "success",
                 "html_url": "https://evil.example/run", "name": "CI"}]}
    monkeypatch.setattr(integrations, "get_json", fake)
    data = integrations.github()["repositories"][0]
    assert data["open_pr_count"] == 2
    assert [p["number"] for p in data["open_prs"]] == [12]
    assert data["latest_ci"]["url"] is None


def test_github_provider_retains_canonical_action_url(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/another")
    monkeypatch.setattr(integrations, "get_json", lambda url: (
        [] if "/pulls?" in url else {"workflow_runs": [{
            "status": "completed", "conclusion": "success",
            "html_url": "https://github.com/owner/another/actions/runs/123", "name": "CI"}]}))
    assert integrations.github()["repositories"][0]["latest_ci"]["url"].endswith("/123")

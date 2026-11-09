from backend import integrations


def test_malformed_preview_metadata_does_not_hide_repository(monkeypatch):
    integrations._cache.clear()
    monkeypatch.setenv("TRIS_GITHUB_REPOS", "owner/repo")
    def fetch(url):
        if "/actions/runs" in url:
            return {"workflow_runs": [None]}
        return [None, {"number": "4", "title": "Bad", "html_url": "/bad"},
                {"number": 5, "title": "Valid", "html_url": "https://github.com/owner/repo/pull/5"}]
    monkeypatch.setattr(integrations, "get_json", fetch)
    result = integrations.github()
    repo = result["repositories"][0]
    assert repo["available"] is True
    assert repo["open_pr_count"] == 3
    assert repo["latest_ci"] is None
    assert [entry["number"] for entry in repo["open_prs"]] == [5]

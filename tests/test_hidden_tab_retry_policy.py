from pathlib import Path


def test_hidden_tab_failure_does_not_schedule_retry():
    source = (Path(__file__).resolve().parents[1] / "frontend/static/dashboard.js").read_text(encoding="utf-8")
    retry = source.split("function retryOverview() {", 1)[1].split("function loadOverview(", 1)[0]
    assert 'if (document.hidden) {' in retry
    assert retry.index('if (document.hidden) {') < retry.index('overviewRetryTimer = setTimeout(')
    assert 'Tab hidden; refresh resumes on return.' in retry
    assert 'if (!document.hidden)' in source.split('document.addEventListener("visibilitychange"', 1)[1]

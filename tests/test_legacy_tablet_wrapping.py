from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_long_dashboard_rows_wrap_instead_of_truncating():
    css = (ROOT / "frontend/static/style.css").read_text(encoding="utf-8")
    assert ".repo-row{white-space:normal;" in css
    assert ".trello-preview{font-size:12px;color:#90a2bb;white-space:normal;" in css
    assert ".github-pr-link{display:block;font-size:12px;color:#a7ccef;white-space:normal;" in css


def test_skip_navigation_visible_only_for_keyboard_focus():
    css = (ROOT / "frontend/static/style.css").read_text(encoding="utf-8")
    assert ".skip-link:focus{top:12px;" in css
    assert "top:-100px" in css

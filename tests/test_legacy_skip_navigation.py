from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_has_keyboard_skip_link_and_focus_target():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'href="#dashboard-modules"' in html
    assert 'id="dashboard-modules" tabindex="-1"' in html
    assert html.index('href="#dashboard-modules"') < html.index("<main")
    assert html.count('id="dashboard-modules"') == 1

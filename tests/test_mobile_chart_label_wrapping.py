from pathlib import Path


def test_mobile_chart_labels_wrap_and_shrink_on_narrow_tablets():
    css = (Path(__file__).resolve().parents[1] / "frontend/static/style.css").read_text(encoding="utf-8")
    for selector in (".workout-bar-row>span:first-child",
                     ".dividend-bar-row>span:first-child",
                     ".allocation-row>span:first-child"):
        assert selector + "{width:" in css
        assert "overflow-wrap:break-word;word-wrap:break-word" in css
    assert "@media (max-width:380px){" in css
    assert "width:86px" in css

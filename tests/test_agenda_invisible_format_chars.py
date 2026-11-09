import json
from datetime import date
import pytest
from backend.agenda import load_agenda


@pytest.mark.parametrize("character", ["\u200b", "\u200c", "\u200d", "\u200e", "\u200f", "\u2060", "\ufeff"])
def test_invisible_formatting_is_rejected_from_calendar_title(tmp_path, character):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [
        {"date": "2026-11-09", "title": "Meeting" + character + "Today"}
    ]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid event title"):
        load_agenda(path, today=date(2026, 11, 9))


def test_regular_korean_calendar_title_is_preserved(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [{"date": "2026-11-09", "title": "운동 일정"}]}), encoding="utf-8")
    assert load_agenda(path, today=date(2026, 11, 9))["next_event"]["title"] == "운동 일정"

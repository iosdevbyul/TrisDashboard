import json
from datetime import date
from backend.agenda import load_agenda


def test_agenda_can_read_last_calendar_day_without_overflow(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [{"date": "9999-12-31", "title": "Last day"}]}), encoding="utf-8")
    data = load_agenda(path, today=date.max)
    assert data["upcoming_count"] == 1
    assert data["tomorrow_event_count"] == 0
    assert data["next_seven_days_count"] == 1
    assert data["window_end"] == "9999-12-31"


def test_agenda_window_clamps_to_last_calendar_day(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [{"date": "9999-12-31", "title": "Final event"}]}), encoding="utf-8")
    data = load_agenda(path, today=date(9999, 12, 29))
    assert data["window_end"] == "9999-12-31"
    assert data["tomorrow_event_count"] == 0
    assert data["upcoming_count"] == 1

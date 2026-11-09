import json
from datetime import date
from backend.agenda import load_agenda


def test_next_timed_event_excludes_all_day_entries(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [
        {"date": "2026-11-09", "title": "All day"},
        {"date": "2026-11-10", "time": "09:30", "title": "Call"},
    ]}), encoding="utf-8")
    result = load_agenda(path, today=date(2026, 11, 9))
    assert result["next_timed_event"] == {"date": "2026-11-10", "time": "09:30", "title": "Call"}


def test_no_timed_events_returns_none(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text('{"events":[]}', encoding="utf-8")
    assert load_agenda(path, today=date(2026, 11, 9))["next_timed_event"] is None

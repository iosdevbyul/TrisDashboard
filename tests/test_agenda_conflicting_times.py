import json
from datetime import date
from backend.agenda import load_agenda


def write(tmp_path, events):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": events}), encoding="utf-8")
    return path


def test_same_day_same_time_reports_conflicts_without_dropping_events(tmp_path):
    events = [
        {"date": "2026-11-09", "time": "09:00", "title": "Work"},
        {"date": "2026-11-09", "time": "09:00", "title": "Gym"},
        {"date": "2026-11-09", "time": "", "title": "All day"},
        {"date": "2026-11-10", "time": "09:00", "title": "Other day"},
    ]
    data = load_agenda(write(tmp_path, events), today=date(2026, 11, 9))
    assert data["conflicting_time_slots"] == 1
    assert data["conflicting_event_count"] == 2
    assert data["upcoming_count"] == 4


def test_only_in_window_timed_events_are_counted(tmp_path):
    events = [
        {"date": "2026-11-08", "time": "09:00", "title": "Past one"},
        {"date": "2026-11-08", "time": "09:00", "title": "Past two"},
        {"date": "2026-11-09", "title": "Untimed"},
        {"date": "2026-11-09", "title": "Another untimed"},
    ]
    data = load_agenda(write(tmp_path, events), today=date(2026, 11, 9))
    assert data["conflicting_time_slots"] == 0
    assert data["conflicting_event_count"] == 0

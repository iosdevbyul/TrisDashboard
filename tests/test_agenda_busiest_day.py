import json
from datetime import date
from backend.agenda import load_agenda


def load(tmp_path, events):
    path = tmp_path / "events.json"
    path.write_text(json.dumps({"events": events}), encoding="utf-8")
    return load_agenda(path, today=date(2026, 11, 9))


def test_busiest_day_counts_all_appointments_with_earliest_tie_break(tmp_path):
    events = [{"date": "2026-11-12", "title": "Later one"},
              {"date": "2026-11-12", "title": "Later two"},
              {"date": "2026-11-10", "title": "Earlier one"},
              {"date": "2026-11-10", "title": "Earlier two"},
              {"date": "2026-11-08", "title": "Past"}]
    assert load(tmp_path, events)["busiest_upcoming_day"] == {"date": "2026-11-10", "events": 2}


def test_no_upcoming_appointments_has_no_busiest_day(tmp_path):
    assert load(tmp_path, [])["busiest_upcoming_day"] is None

import json
from datetime import date
import pytest
from backend.agenda import agenda, load_agenda

def file_with(tmp_path, events):
    file = tmp_path / "agenda.json"
    file.write_text(json.dumps({"events": events}))
    return file

def test_upcoming_sorted_and_filtered(tmp_path):
    file = file_with(tmp_path, [
        {"date": "2026-11-20", "title": "Later", "time": "13:00"},
        {"date": "2026-11-08", "title": "Today", "time": "09:00"},
        {"date": "2026-11-07", "title": "Past"},
        {"date": "2026-12-10", "title": "Far future"},
    ])
    data = load_agenda(file, today=date(2026, 11, 8))
    assert data["upcoming_count"] == 2
    assert [x["title"] for x in data["events"]] == ["Today", "Later"]

@pytest.mark.parametrize("time", ["25:00", "10:70", "bad", 900])
def test_invalid_time(tmp_path, time):
    file = file_with(tmp_path, [{"date": "2026-11-09", "title": "Meeting", "time": time}])
    with pytest.raises(ValueError):
        load_agenda(file, today=date(2026, 11, 8))

def test_unconfigured(monkeypatch):
    monkeypatch.delenv("TRIS_AGENDA_FILE", raising=False)
    assert agenda()["configured"] is False

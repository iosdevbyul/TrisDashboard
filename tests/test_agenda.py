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


@pytest.mark.parametrize("time", ["25:00", "10:70", "bad", 900, "١٢:٣٠", "12:30\\n"])
def test_invalid_time(tmp_path, time):
    file = file_with(tmp_path, [{"date": "2026-11-09", "title": "Meeting", "time": time}])
    with pytest.raises(ValueError):
        load_agenda(file, today=date(2026, 11, 8))


@pytest.mark.parametrize("bad_date", ["20261109", "2026-1-09", "2026-11-9",
                                    "2026-02-30", 20261109, None, "２０２６-11-09"])
def test_invalid_date(tmp_path, bad_date):
    file = file_with(tmp_path, [{"date": bad_date, "title": "Meeting"}])
    with pytest.raises(ValueError):
        load_agenda(file, today=date(2026, 11, 8))


@pytest.mark.parametrize("title", ["Bad" + chr(10) + "line", "Zero" + chr(0) + "byte", "Delete" + chr(127) + "char", "  "])
def test_reject_control_characters_and_blank_titles(tmp_path, title):
    file = file_with(tmp_path, [{"date": "2026-11-09", "title": title}])
    with pytest.raises(ValueError):
        load_agenda(file, today=date(2026, 11, 8))


def test_reject_duplicate_json_keys(tmp_path):
    file = tmp_path / "agenda.json"
    file.write_text('{"events":[{"date":"2026-11-09","title":"First","title":"Second"}]}')
    with pytest.raises(ValueError, match="Duplicate"):
        load_agenda(file, today=date(2026, 11, 8))


def test_malformed_agenda_returns_unavailable(tmp_path, monkeypatch):
    file = tmp_path / "agenda.json"
    file.write_text('{"events":[{"date":"20261109","title":"Invalid"}]}')
    monkeypatch.setenv("TRIS_AGENDA_FILE", str(file))
    assert agenda() == {"available": False, "configured": True, "stale": True}


def test_unconfigured(monkeypatch):
    monkeypatch.delenv("TRIS_AGENDA_FILE", raising=False)
    assert agenda()["configured"] is False


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_reject_nonstandard_json_numeric_constant_anywhere(tmp_path, constant):
    path = tmp_path / "invalid-agenda.json"
    path.write_text('{"metadata":' + constant + ',"events":[]}')
    with pytest.raises(ValueError, match="Non-standard JSON"):
        load_agenda(path, today=date(2026, 11, 8))


@pytest.mark.parametrize("reference", ["2026-11-08", 123, True])
def test_reject_invalid_agenda_reference_date(tmp_path, reference):
    with pytest.raises(ValueError, match="Invalid agenda reference date"):
        load_agenda(file_with(tmp_path, []), today=reference)

import json
from datetime import date
import pytest
from backend.agenda import load_agenda


@pytest.mark.parametrize("control", ["\u202a", "\u202e", "\u2066", "\u2069"])
def test_agenda_rejects_bidirectional_override_and_isolate_controls(tmp_path, control):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [{"date": "2026-11-09", "title": "Pay " + control + "now"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid event title"):
        load_agenda(path, today=date(2026, 11, 9))


def test_normal_multilingual_title_still_works(tmp_path):
    path = tmp_path / "agenda.json"
    path.write_text(json.dumps({"events": [{"date": "2026-11-09", "title": "회의 Meeting"}]}), encoding="utf-8")
    assert load_agenda(path, today=date(2026, 11, 9))["upcoming_count"] == 1

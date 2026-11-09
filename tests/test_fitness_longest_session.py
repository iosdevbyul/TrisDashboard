import json
from datetime import date
from backend.fitness import load_fitness


def test_longest_session_only_uses_current_week(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": [
        {"date": "2026-10-01", "type": "Cycling", "duration_minutes": 300},
        {"date": "2026-11-07", "type": "Running", "duration_minutes": 60},
        {"date": "2026-11-09", "type": "Strength", "duration_minutes": 75},
    ]}), encoding="utf-8")
    result = load_fitness(path, today=date(2026, 11, 9))
    assert result["longest_session"] == {"date": "2026-11-09", "type": "Strength",
                                         "duration_minutes": 75}


def test_empty_week_has_no_longest_session(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text('{"workouts":[]}', encoding="utf-8")
    assert load_fitness(path, today=date(2026, 11, 9))["longest_session"] is None

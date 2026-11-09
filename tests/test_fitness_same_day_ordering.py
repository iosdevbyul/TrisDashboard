import json
from datetime import date
from backend.fitness import load_fitness


def test_recent_workouts_are_sorted_by_day_then_longest_session(tmp_path):
    file = tmp_path / "workouts.json"
    file.write_text(json.dumps({"workouts": [
        {"date": "2026-11-09", "type": "Walking", "duration_minutes": 20},
        {"date": "2026-11-09", "type": "Strength", "duration_minutes": 60},
        {"date": "2026-11-08", "type": "Running", "duration_minutes": 120},
        {"date": "2026-11-09", "type": "Running", "duration_minutes": 60},
    ]}), encoding="utf-8")
    recent = load_fitness(file, today=date(2026, 11, 9))["recent"]
    assert [(x["date"], x["type"]) for x in recent] == [
        ("2026-11-09", "Strength"), ("2026-11-09", "Running"),
        ("2026-11-09", "Walking"), ("2026-11-08", "Running")]

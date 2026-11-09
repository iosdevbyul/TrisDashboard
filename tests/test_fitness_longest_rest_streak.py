import json
from datetime import date
from backend.fitness import load_fitness


def test_longest_rest_streak_with_interleaved_workouts(tmp_path):
    path = tmp_path / "fitness.json"
    path.write_text(json.dumps({"workouts": [
        {"date":"2026-11-03","type":"running","duration_minutes":20},
        {"date":"2026-11-07","type":"walking","duration_minutes":30},
    ]}), encoding="utf-8")
    result = load_fitness(path, today=date(2026,11,9))
    assert result["longest_rest_streak_days"] == 3


def test_full_week_rest_streak(tmp_path):
    path = tmp_path / "fitness.json"
    path.write_text('{"workouts":[]}', encoding="utf-8")
    assert load_fitness(path, today=date(2026,11,9))["longest_rest_streak_days"] == 7

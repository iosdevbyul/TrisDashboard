import json
from datetime import date, datetime
import pytest
from backend.fitness import load_fitness


@pytest.mark.parametrize("invalid", ["2026-11-09", 123, True, datetime(2026, 11, 9)])
def test_invalid_workout_reference_date_is_rejected(tmp_path, invalid):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid workout reference date"):
        load_fitness(path, today=invalid)


def test_explicit_workout_reference_date_still_works(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    assert load_fitness(path, today=date(2026, 11, 9))["period_end"] == "2026-11-09"

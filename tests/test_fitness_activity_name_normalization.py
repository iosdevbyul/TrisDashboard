import json
from datetime import date
import pytest
from backend.fitness import load_fitness


def write_workouts(tmp_path, workouts):
    path = tmp_path / "fitness.json"
    path.write_text(json.dumps({"workouts": workouts}), encoding="utf-8")
    return path


def test_whitespace_variants_group_as_single_activity(tmp_path):
    path = write_workouts(tmp_path, [
        {"date": "2026-11-08", "type": " Running ", "duration_minutes": 20},
        {"date": "2026-11-09", "type": "Running", "duration_minutes": 30},
    ])
    data = load_fitness(path, today=date(2026, 11, 9))
    assert data["activity_breakdown"][0]["type"] == "Running"
    assert data["activity_breakdown"][0]["sessions"] == 2
    assert {item["type"] for item in data["recent"]} == {"Running"}


@pytest.mark.parametrize("name", [" ", "  ", "---"])
def test_unusable_activity_names_do_not_create_blank_groups(tmp_path, name):
    path = write_workouts(tmp_path, [{"date": "2026-11-09", "type": name, "duration_minutes": 10}])
    if name == "---":
        assert load_fitness(path, today=date(2026, 11, 9))["activity_breakdown"][0]["type"] == "---"
    else:
        with pytest.raises(ValueError, match="Invalid workout type"):
            load_fitness(path, today=date(2026, 11, 9))

import json
from datetime import date
import pytest
from backend.fitness import load_fitness


@pytest.mark.parametrize("day", [date(1, 1, 1), date(1, 1, 6)])
def test_earliest_reference_dates_fail_cleanly(tmp_path, day):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="seven days"):
        load_fitness(path, today=day)


def test_earliest_full_week_reference_still_works(tmp_path):
    path = tmp_path / "workouts.json"
    path.write_text(json.dumps({"workouts": []}), encoding="utf-8")
    value = load_fitness(path, today=date(1, 1, 7))
    assert value["period_start"] == "0001-01-01"
    assert value["period_end"] == "0001-01-07"

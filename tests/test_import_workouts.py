import csv
import json
import pytest

from macos.import_workouts import import_csv


def make_csv(tmp_path, rows, name="workouts.csv"):
    path = tmp_path / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "type", "duration_minutes", "distance_km"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_import_creates_dashboard_compatible_json(tmp_path):
    source = make_csv(tmp_path, [
        {"date": "2026-11-08", "type": "Running", "duration_minutes": "42", "distance_km": "7.2"},
        {"date": "2026-11-06", "type": "Strength", "duration_minutes": "60", "distance_km": "0"},
    ])
    output = tmp_path / "private" / "fitness.json"
    result = import_csv(source, output)
    assert result == {"validated": 2, "written": True}
    assert len(json.loads(output.read_text())["workouts"]) == 2
    assert output.stat().st_mode & 0o077 == 0


def test_dry_run_never_creates_final_destination(tmp_path):
    source = make_csv(tmp_path, [{"date": "2026-11-08", "type": "Running",
                                  "duration_minutes": "20", "distance_km": "3"}])
    output = tmp_path / "fitness.json"
    assert import_csv(source, output, dry_run=True)["written"] is False
    assert not output.exists()


def test_invalid_csv_does_not_overwrite_existing_data(tmp_path):
    source = make_csv(tmp_path, [{"date": "2026-11-08", "type": "Running",
                                  "duration_minutes": "-10", "distance_km": "0"}])
    output = tmp_path / "fitness.json"
    output.write_text('{"workouts": []}')
    with pytest.raises(ValueError):
        import_csv(source, output, overwrite=True)
    assert output.read_text() == '{"workouts": []}'


def test_existing_file_requires_explicit_force(tmp_path):
    source = make_csv(tmp_path, [{"date": "2026-11-08", "type": "Running",
                                  "duration_minutes": "20", "distance_km": "0"}])
    output = tmp_path / "fitness.json"
    output.write_text('{"workouts": []}')
    with pytest.raises(ValueError, match="already exists"):
        import_csv(source, output)
    assert import_csv(source, output, overwrite=True)["written"]


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "bad"])
def test_invalid_measurements_rejected(tmp_path, value):
    source = make_csv(tmp_path, [{"date": "2026-11-08", "type": "Running",
                                  "duration_minutes": value, "distance_km": "1"}])
    with pytest.raises(ValueError):
        import_csv(source, tmp_path / "fitness.json")

"""Offline workout CSV -> private JSON import; no HealthKit access or remote upload."""
import argparse
import csv
import json
import math
import os
import tempfile
from pathlib import Path

from backend.fitness import load_fitness

COLUMNS = {"date", "type", "duration_minutes", "distance_km"}
REQUIRED = {"date", "type", "duration_minutes"}
MAX_ROWS = 500
MAX_INPUT_BYTES = 128 * 1024


def convert_csv(source: Path) -> dict:
    if source.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("CSV is too large")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Invalid CSV header")
        fields = set(reader.fieldnames)
        if not REQUIRED.issubset(fields) or not fields.issubset(COLUMNS):
            raise ValueError("Unexpected CSV columns")
        workouts = []
        for record in reader:
            if len(workouts) >= MAX_ROWS:
                raise ValueError("Too many workouts")
            if None in record or any(value is None for value in record.values()):
                raise ValueError("Invalid CSV row")
            name = record["type"].strip()
            day = record["date"].strip()
            try:
                minutes = float(record["duration_minutes"].strip())
                distance = float(record.get("distance_km", "0").strip() or "0")
            except ValueError as error:
                raise ValueError("Invalid numeric workout data") from error
            if not math.isfinite(minutes) or not math.isfinite(distance):
                raise ValueError("Invalid workout measurement")
            workouts.append({"date": day, "type": name,
                             "duration_minutes": minutes, "distance_km": distance})
    return {"workouts": workouts}


def import_csv(source: Path, output: Path, *, overwrite: bool = False, dry_run: bool = False) -> dict:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if output == source or output.is_relative_to(project / "frontend"):
        raise ValueError("Output location is not permitted")
    payload = convert_csv(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        raise ValueError("Destination already exists (use --force to replace)")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                         dir=output.parent, prefix=".tris-import-", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False)
        # Reuse dashboard validation of all rows before committing.
        load_fitness(temp_path)
        if not dry_run:
            os.replace(temp_path, output)
            temp_path = None
        return {"validated": len(payload["workouts"]), "written": not dry_run}
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import private workout CSV into dashboard JSON")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="Replace existing output after validation")
    parser.add_argument("--dry-run", action="store_true", help="Validate without saving")
    args = parser.parse_args()
    try:
        result = import_csv(args.input, args.output, overwrite=args.force, dry_run=args.dry_run)
    except (OSError, ValueError, TypeError):
        parser.exit(1, "Import failed: check CSV format and output permissions.\n")
    print("Validated " + str(result["validated"]) + " workouts" +
          ("; saved locally" if result["written"] else "; dry-run only"))


if __name__ == "__main__":
    main()

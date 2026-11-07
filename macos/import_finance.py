"""Local finance CSV imports; user-exported values only, no market/broker access."""
import argparse
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backend.dividends import load_dividends
from backend.portfolio import load_portfolio

FIELDS = {
    "portfolio": {"symbol", "currency", "quantity", "price"},
    "dividends": {"symbol", "currency", "paid_on", "amount"},
}
REQUIRED = {
    "portfolio": {"symbol", "currency", "quantity"},
    "dividends": FIELDS["dividends"],
}
MAX_ROWS = {"portfolio": 25, "dividends": 300}


def csv_payload(path: Path, kind: str, as_of: str | None = None) -> dict:
    if kind not in FIELDS:
        raise ValueError("Unsupported import")
    if path.stat().st_size > 65536:
        raise ValueError("CSV too large")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if (not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames)
                or not REQUIRED[kind].issubset(reader.fieldnames)
                or not set(reader.fieldnames).issubset(FIELDS[kind])):
            raise ValueError("Invalid columns")
        entries = []
        for row in reader:
            if len(entries) >= MAX_ROWS[kind] or None in row or any(v is None for v in row.values()):
                raise ValueError("Invalid number of rows or column count")
            item = {key: value.strip() for key, value in row.items() if value is not None}
            if kind == "portfolio" and not item.get("price"):
                item.pop("price", None)
            entries.append(item)
    if kind == "portfolio":
        return {"as_of": as_of or datetime.now(timezone.utc).isoformat(), "positions": entries}
    return {"payments": entries}


def import_finance(source: Path, output: Path, *, kind: str, as_of: str | None = None,
                   overwrite: bool = False, dry_run: bool = False) -> dict:
    source, output = source.expanduser().resolve(), output.expanduser().resolve()
    project = Path(__file__).resolve().parent.parent
    if source == output or output == project or project in output.parents:
        raise ValueError("Destination must be outside the repository")
    if output.suffix.lower() != ".json":
        raise ValueError("Destination must be JSON")
    payload = csv_payload(source, kind, as_of=as_of)
    validator = load_portfolio if kind == "portfolio" else load_dividends
    if output.exists() and not overwrite:
        raise ValueError("Destination exists; explicit --force required")
    if not dry_run:
        output.parent.mkdir(parents=True, exist_ok=True)
    directory = output.parent if not dry_run else None
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json",
                                         prefix=".tris-finance-", dir=directory, delete=False) as handle:
            temp = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False)
        validator(temp)
        if not dry_run:
            os.replace(temp, output)
            temp = None
        return {"validated": len(payload["positions"] if kind == "portfolio" else payload["payments"]),
                "written": not dry_run}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert private portfolio or dividend CSV into dashboard JSON")
    parser.add_argument("kind", choices=("portfolio", "dividends"))
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", help="Timezone-aware portfolio snapshot time (default: import time)")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.as_of and args.kind != "portfolio":
            raise ValueError("--as-of applies only to portfolio")
        summary = import_finance(args.input, args.output, kind=args.kind, as_of=args.as_of,
                                 overwrite=args.force, dry_run=args.dry_run)
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Import failed: verify finance CSV values and output permissions.\n")
    print("Validated " + str(summary["validated"]) + " records" +
          ("; saved locally" if summary["written"] else "; dry-run only"))


if __name__ == "__main__":
    main()

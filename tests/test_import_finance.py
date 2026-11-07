import csv
import json
from datetime import datetime, timezone

import pytest

from macos.import_finance import import_finance


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_portfolio_import_keeps_missing_quote_unknown(tmp_path):
    source = write_csv(tmp_path / "holdings.csv", ["symbol", "currency", "quantity", "price"], [
        {"symbol": "JEPQ", "currency": "USD", "quantity": "10", "price": "50.5"},
        {"symbol": "SCHD", "currency": "USD", "quantity": "3", "price": ""},
    ])
    output = tmp_path / "private" / "holdings.json"
    outcome = import_finance(source, output, kind="portfolio")
    assert outcome == {"validated": 2, "written": True}
    data = json.loads(output.read_text())
    assert "price" not in data["positions"][1]
    assert output.stat().st_mode & 0o077 == 0


def test_dividend_import_does_not_infer_future_payments(tmp_path):
    source = write_csv(tmp_path / "dividends.csv", ["symbol", "currency", "paid_on", "amount"], [
        {"symbol": "QQQI", "currency": "USD", "paid_on": "2025-12-02", "amount": "14.30"}
    ])
    output = tmp_path / "dividends.json"
    assert import_finance(source, output, kind="dividends", dry_run=True)["written"] is False
    assert not output.exists()
    assert import_finance(source, output, kind="dividends")["written"] is True


def test_bad_amount_preserves_previous_file(tmp_path):
    source = write_csv(tmp_path / "dividends.csv", ["symbol", "currency", "paid_on", "amount"], [
        {"symbol": "JEPQ", "currency": "USD", "paid_on": "2025-01-01", "amount": "NaN"}
    ])
    output = tmp_path / "private.json"
    output.write_text("original")
    with pytest.raises(ValueError):
        import_finance(source, output, kind="dividends", overwrite=True)
    assert output.read_text() == "original"


def test_invalid_destination_requires_explicit_force(tmp_path):
    source = write_csv(tmp_path / "holdings.csv", ["symbol", "currency", "quantity"], [
        {"symbol": "SCHD", "currency": "USD", "quantity": "5"}
    ])
    output = tmp_path / "portfolio.json"
    import_finance(source, output, kind="portfolio")
    with pytest.raises(ValueError, match="explicit"):
        import_finance(source, output, kind="portfolio")


def test_invalid_future_portfolio_as_of_is_rejected(tmp_path):
    source = write_csv(tmp_path / "holdings.csv", ["symbol", "currency", "quantity"], [
        {"symbol": "JEPQ", "currency": "USD", "quantity": "1"}
    ])
    with pytest.raises(ValueError):
        import_finance(source, tmp_path / "out.json", kind="portfolio", as_of="2099-01-01T00:00:00+00:00")

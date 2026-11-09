import json
from datetime import datetime, timezone
import pytest
from backend.portfolio import load_portfolio


def make_snapshot(tmp_path, positions):
    path = tmp_path / "portfolio.json"
    path.write_text(json.dumps({"as_of": datetime.now(timezone.utc).isoformat(), "positions": positions}), encoding="utf-8")
    return path


def test_lowercase_portfolio_symbol_is_canonicalized(tmp_path):
    result = load_portfolio(make_snapshot(tmp_path, [{"symbol": "jepq", "currency": "USD", "quantity": 2, "price": 10}]))
    assert result["positions"][0]["symbol"] == "JEPQ"


def test_case_only_duplicate_portfolio_symbols_are_rejected(tmp_path):
    path = make_snapshot(tmp_path, [
        {"symbol": "jepq", "currency": "USD", "quantity": 1},
        {"symbol": "JEPQ", "currency": "USD", "quantity": 2},
    ])
    with pytest.raises(ValueError, match="Duplicate portfolio holding"):
        load_portfolio(path)

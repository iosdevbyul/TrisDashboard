from datetime import datetime, timezone
import pytest
from backend.quotes import parse_quote

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize("symbol", ["ſCHD", "ＳＣＨＤ", "SСHD", "SCHD\n", ""])
def test_provider_symbol_rejects_confusable_or_malformed_text(symbol):
    with pytest.raises(ValueError, match="Unexpected symbol"):
        parse_quote({"symbol": symbol, "currency": "USD", "close": "40",
                     "timestamp": int(NOW.timestamp())}, "SCHD", now=NOW)


def test_normal_ascii_lowercase_quote_symbol_supported():
    result = parse_quote({"symbol": "schd", "currency": "USD", "close": "40",
                         "timestamp": int(NOW.timestamp())}, "SCHD", now=NOW)
    assert result["symbol"] == "SCHD"

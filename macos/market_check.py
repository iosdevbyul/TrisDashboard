"""Offline Twelve Data setup checks. Never requests paid provider data."""
import argparse
import json
from pathlib import Path

from backend.quotes import quote_symbols
from macos.service import read_public_settings
from macos.secure_launch import keychain_value, SERVICE_NAMES


def inspect_market(settings_file: Path, *, lookup=keychain_value) -> dict:
    result = {"settings_valid": False, "symbols_configured": False,
              "symbol_count": 0, "keychain_key_present": False,
              "ready_for_optional_api_test": False, "network_requests": 0}
    try:
        settings = read_public_settings(settings_file)
    except (OSError, ValueError, TypeError):
        return result
    result["settings_valid"] = True
    raw = settings.get("TRIS_QUOTE_SYMBOLS")
    if raw:
        try:
            symbols = quote_symbols(raw)
            result["symbol_count"] = len(symbols)
            result["symbols_configured"] = bool(symbols)
        except ValueError:
            return result
    if result["symbols_configured"]:
        try:
            credential = lookup(SERVICE_NAMES["TRIS_TWELVEDATA_API_KEY"])
            result["keychain_key_present"] = isinstance(credential, str) and bool(credential.strip())
        except (OSError, ValueError, TypeError):
            pass
    result["ready_for_optional_api_test"] = (
        result["symbols_configured"] and result["keychain_key_present"]
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline market configuration readiness")
    parser.add_argument("--settings", required=True, type=Path)
    args = parser.parse_args()
    report = inspect_market(args.settings)
    print(json.dumps(report, sort_keys=True))
    if not report["settings_valid"]:
        parser.exit(1)


if __name__ == "__main__":
    main()

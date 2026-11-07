"""Read-only localhost deployment verification without printing private dashboard data."""
import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8080"
SOURCE_NAMES = ("weather", "github", "trello", "portfolio", "fitness", "dividends", "agenda")
ASSETS = ("/static/style.css", "/static/dashboard.js", "/static/preferences.js")


def request_local(path: str):
    if not path.startswith("/") or "//" in path:
        raise ValueError("Invalid smoke-check route")
    with urlopen(Request(BASE + path, headers={"Accept": "*/*"}), timeout=8) as response:
        return response.status, dict(response.headers.items()), response.read()


def header(headers: dict, name: str) -> str | None:
    return next((value for key, value in headers.items() if key.lower() == name.lower()), None)


def check_deployment(fetch=request_local) -> dict:
    report = {"health": False, "homepage": False, "assets": False, "overview": False,
              "headers": False, "sources_ready": 0, "sources_stale": 0,
              "sources_unavailable": 0, "passed": False}
    try:
        status, headers, body = fetch("/healthz")
        report["health"] = status == 200 and json.loads(body) == {"status": "ok"}
        report["headers"] = (header(headers, "Cache-Control") == "no-store"
                             and header(headers, "X-Content-Type-Options") == "nosniff"
                             and header(headers, "X-Frame-Options") == "DENY")
        status, headers, body = fetch("/")
        report["homepage"] = status == 200 and b"TRIS DASHBOARD" in body
        report["headers"] = report["headers"] and header(headers, "Cache-Control") == "no-store"
        report["assets"] = all(
            status == 200 and bool(data) and asset_header(headers, "Cache-Control") == "no-cache, max-age=0, must-revalidate"
            for status, asset_headers, data in (fetch(path) for path in ASSETS)
        )
        status, headers, body = fetch("/api/overview")
        overview = json.loads(body)
        report["overview"] = (status == 200 and isinstance(overview, dict)
                              and all(name in overview for name in SOURCE_NAMES)
                              and isinstance(overview.get("server"), dict)
                              and overview["server"].get("available") is True)
        report["headers"] = report["headers"] and header(headers, "Cache-Control") == "no-store"
        if report["overview"]:
            for name in SOURCE_NAMES:
                source = overview[name]
                if not isinstance(source, dict):
                    report["overview"] = False
                    break
                if source.get("available"):
                    report["sources_ready"] += 1
                    if source.get("stale") or source.get("quality", {}).get("outdated"):
                        report["sources_stale"] += 1
                elif source.get("configured") is not False:
                    report["sources_unavailable"] += 1
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError):
        pass
    report["passed"] = all(report[name] for name in ("health", "homepage", "assets", "overview", "headers"))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a running localhost dashboard without exposing data")
    parser.add_argument("--json", action="store_true", help="Print machine-readable checks")
    args = parser.parse_args()
    result = check_deployment()
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        for key, value in result.items():
            print(key.replace("_", " ") + ": " + str(value).lower())
    if not result["passed"]:
        parser.exit(1)


if __name__ == "__main__":
    main()

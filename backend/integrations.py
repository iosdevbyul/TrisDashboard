"""Server-only read-only integrations with bounded HTTP calls and stale caching."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

_cache = {}
_lock = threading.Lock()
TTL_SECONDS = 300


def get_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "TrisDashboard/1.0"})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def cached(key: str, loader, *, ttl: int = TTL_SECONDS) -> dict:
    now = time.monotonic()
    with _lock:
        previous = _cache.get(key)
        if previous and now - previous["time"] < ttl:
            return dict(previous["data"])
    try:
        fresh = loader()
        fresh["updated_at"] = datetime.now(timezone.utc).isoformat()
        fresh["stale"] = False
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError) as error:
        if previous:
            fallback = dict(previous["data"])
            fallback["stale"] = True
            return fallback
        return {"available": False, "stale": True, "error": "temporarily unavailable"}
    with _lock:
        _cache[key] = {"time": time.monotonic(), "data": dict(fresh)}
    return fresh


def weather() -> dict:
    latitude = float(os.environ.get("TRIS_LATITUDE", "37.5665"))
    longitude = float(os.environ.get("TRIS_LONGITUDE", "126.9780"))
    label = os.environ.get("TRIS_LOCATION_NAME", "Seoul")[:60]
    query = urlencode({
        "latitude": latitude, "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code",
        "timezone": "auto",
    })
    url = "https://api.open-meteo.com/v1/forecast?" + query

    def load():
        payload = get_json(url)
        current = payload["current"]
        return {
            "available": True, "location": label,
            "temperature_c": current["temperature_2m"],
            "humidity_percent": current["relative_humidity_2m"],
            "weather_code": current["weather_code"],
        }
    return cached("weather:" + query + ":" + label, load, ttl=600)


def github() -> dict:
    raw = os.environ.get("TRIS_GITHUB_REPOS", "iosdevbyul/TrisDashboard")
    repositories = []
    for name in raw.split(","):
        name = name.strip()
        if len(name.split("/")) == 2 and all(part and part.replace("-", "").replace("_", "").replace(".", "").isalnum() for part in name.split("/")):
            if name not in repositories:
                repositories.append(name)
        if len(repositories) == 6:
            break

    def load():
        results = []
        for repo in repositories:
            encoded = "/".join(quote(part, safe="") for part in repo.split("/"))
            pulls = get_json("https://api.github.com/repos/" + encoded + "/pulls?state=open&per_page=20")
            if not isinstance(pulls, list):
                raise ValueError("Unexpected GitHub response")
            results.append({"repository": repo, "open_pr_count": len(pulls),
                            "open_prs": [{"number": item["number"], "title": item["title"][:120],
                                          "url": item["html_url"]} for item in pulls[:3]]})
        return {"available": True, "repositories": results}
    return cached("github:" + ",".join(repositories), load, ttl=180)


def overview() -> dict:
    return {"weather": weather(), "github": github()}

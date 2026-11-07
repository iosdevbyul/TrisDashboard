"""Server-only read-only integrations with bounded HTTP calls and stale caching."""
import json
from concurrent.futures import ThreadPoolExecutor, wait
import os
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from backend.portfolio import portfolio
from backend.fitness import fitness

_cache = {}
_lock = threading.Lock()
TTL_SECONDS = 300
_PROVIDER_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="dashboard-provider")
_PROVIDER_INFLIGHT = {}
_PROVIDER_LOCK = threading.Lock()


def _future_for(name, loader):
    # Reuse unfinished requests during upstream outages, avoiding an unbounded job queue.
    with _PROVIDER_LOCK:
        future = _PROVIDER_INFLIGHT.get(name)
        if future is None or future.done():
            future = _PROVIDER_EXECUTOR.submit(loader)
            _PROVIDER_INFLIGHT[name] = future
        return future


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
        "current": "temperature_2m,relative_humidity_2m,weather_code,apparent_temperature,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
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
            "feels_like_c": current.get("apparent_temperature"),
            "wind_kmh": current.get("wind_speed_10m"),
            "today_high_c": (payload.get("daily", {}).get("temperature_2m_max") or [None])[0],
            "today_low_c": (payload.get("daily", {}).get("temperature_2m_min") or [None])[0],
            "rain_chance_percent": (payload.get("daily", {}).get("precipitation_probability_max") or [None])[0],
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
            runs_payload = get_json("https://api.github.com/repos/" + encoded + "/actions/runs?per_page=1")
            runs = runs_payload["workflow_runs"]
            if not isinstance(runs, list):
                raise ValueError("Unexpected workflow response")
            latest = runs[0] if runs else None
            ci = {
                "status": latest.get("status", "unknown"),
                "conclusion": latest.get("conclusion"),
                "url": latest.get("html_url"),
                "name": latest.get("name", "Workflow"),
            } if latest else None
            results.append({"repository": repo, "open_pr_count": len(pulls),
                            "open_pr_count_truncated": len(pulls) == 20,
                            "latest_ci": ci,
                            "open_prs": [{"number": item["number"], "title": item["title"][:120],
                                          "url": item["html_url"]} for item in pulls[:3]]})
        return {"available": True, "repositories": results}
    return cached("github:" + ",".join(repositories), load, ttl=900)


def trello() -> dict:
    """Read-only personal board summary; credentials never reach the browser."""
    board = os.environ.get("TRIS_TRELLO_BOARD_ID", "").strip()
    key = os.environ.get("TRIS_TRELLO_KEY", "").strip()
    token = os.environ.get("TRIS_TRELLO_TOKEN", "").strip()
    if not (board and key and token):
        return {"available": False, "configured": False, "stale": False}
    if not board.isalnum() or len(board) > 64:
        return {"available": False, "configured": False, "stale": False}

    def load():
        query = urlencode({
            "key": key, "token": token, "fields": "name",
            "cards": "open", "card_fields": "name,idList",
            "card_limit": "100",
        })
        url = "https://api.trello.com/1/boards/" + quote(board, safe="") + "/lists?" + query
        lists = get_json(url)
        if not isinstance(lists, list):
            raise ValueError("Invalid Trello data")
        result = []
        for entry in lists:
            name = entry.get("name", "")
            if name.lower().strip() not in ("next", "in progress", "done"):
                continue
            cards = entry.get("cards", [])
            if not isinstance(cards, list):
                raise ValueError("Invalid Trello cards")
            result.append({"name": name, "count": len(cards),
                           "cards": [str(card.get("name", ""))[:90] for card in cards[:3]]})
        return {"available": True, "configured": True, "lists": result}

    # The cache key must never contain access tokens.
    return cached("trello:" + board, load, ttl=600)


def overview(timeout_seconds: float = 4.0) -> dict:
    """Collect slow upstreams concurrently without delaying the whole dashboard indefinitely."""
    providers = {"weather": weather, "github": github, "trello": trello}
    futures = {name: _future_for(name, loader) for name, loader in providers.items()}
    completed, pending = wait(set(futures.values()), timeout=max(0, timeout_seconds))
    result = {}
    for name, future in futures.items():
        if future not in completed:
            result[name] = {"available": False, "configured": True, "stale": True}
            continue
        try:
            result[name] = future.result()
        except Exception:
            # Never expose provider credentials or provider error text.
            result[name] = {"available": False, "configured": True, "stale": True}
    result["portfolio"] = portfolio()
    result["fitness"] = fitness()
    return result

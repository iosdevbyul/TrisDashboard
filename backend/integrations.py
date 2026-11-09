"""Server-only read-only integrations with bounded HTTP calls and stale caching."""
import json
import math
import hashlib
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
from backend.dividends import dividends
from backend.agenda import agenda
from backend.quotes import quote_symbols, load_quotes, refresh_quote_freshness
from backend.valuation import quote_valuation

_cache = {}
_lock = threading.Lock()
TTL_SECONDS = 300
MAX_STALE_SECONDS = 24 * 60 * 60
MAX_PROVIDER_RESPONSE_BYTES = 1024 * 1024
_PROVIDER_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dashboard-provider")
_PROVIDER_INFLIGHT = {}
_PROVIDER_LOCK = threading.Lock()
# A total market-provider outage should not trigger a fresh, potentially
# credit-consuming request on every dashboard refresh.
_QUOTE_RETRY_AT = {}
_QUOTE_RETRY_SECONDS = 600


def _future_for(name, loader):
    # Reuse unfinished requests during upstream outages, avoiding an unbounded job queue.
    with _PROVIDER_LOCK:
        future = _PROVIDER_INFLIGHT.get(name)
        if future is None or future.done():
            future = _PROVIDER_EXECUTOR.submit(loader)
            _PROVIDER_INFLIGHT[name] = future
        return future


def get_json(url: str, headers: dict | None = None) -> dict:
    request_headers = {"Accept": "application/json", "User-Agent": "TrisDashboard/1.0"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=5) as response:
        payload = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        if len(payload) > MAX_PROVIDER_RESPONSE_BYTES:
            raise ValueError("Provider JSON response too large")
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate provider JSON key")
                result[key] = value
            return result

        def reject_constant(value):
            raise ValueError("Invalid provider JSON constant")

        return json.loads(payload, object_pairs_hook=unique_keys, parse_constant=reject_constant)


def cached(key: str, loader, *, ttl: int = TTL_SECONDS) -> dict:
    now = time.monotonic()
    with _lock:
        previous = _cache.get(key)
        if previous and now - previous["time"] < ttl:
            return dict(previous["data"])
    try:
        fresh = dict(loader())
        fresh["updated_at"] = datetime.now(timezone.utc).isoformat()
        fresh["stale"] = False
    except (OSError, ValueError, KeyError, TypeError, HTTPError, URLError) as error:
        if previous and now - previous["time"] <= MAX_STALE_SECONDS:
            fallback = dict(previous["data"])
            fallback["stale"] = True
            return fallback
        return {"available": False, "stale": True, "error": "temporarily unavailable"}
    with _lock:
        _cache[key] = {"time": time.monotonic(), "data": dict(fresh)}
    return fresh


def _forecast_first(payload, name):
    if not isinstance(payload, dict):
        return None
    daily = payload.get("daily")
    values = daily.get(name) if isinstance(daily, dict) else None
    if not isinstance(values, list) or not values:
        return None
    value = values[0]
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return value


def weather() -> dict:
    try:
        latitude = float(os.environ.get("TRIS_LATITUDE", "37.5665"))
        longitude = float(os.environ.get("TRIS_LONGITUDE", "126.9780"))
    except ValueError:
        return {"available": False, "configured": True, "stale": True}
    if (not math.isfinite(latitude) or not math.isfinite(longitude)
            or not -90 <= latitude <= 90 or not -180 <= longitude <= 180):
        return {"available": False, "configured": True, "stale": True}
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
            "today_high_c": _forecast_first(payload, "temperature_2m_max"),
            "today_low_c": _forecast_first(payload, "temperature_2m_min"),
            "rain_chance_percent": _forecast_first(payload, "precipitation_probability_max"),
        }
    return cached("weather:" + query + ":" + label, load, ttl=600)


def github() -> dict:
    raw = os.environ.get("TRIS_GITHUB_REPOS", "iosdevbyul/TrisDashboard")
    token = os.environ.get("TRIS_GITHUB_TOKEN", "").strip()
    auth_headers = {"Authorization": "Bearer " + token} if token else None

    def fetch_github(url):
        if auth_headers:
            return get_json(url, headers=auth_headers)
        return get_json(url)
    repositories = []
    for name in raw.split(","):
        name = name.strip()
        if (len(name.split("/")) == 2 and all(
                part and len(part) <= 100 and all(
                    char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._"
                    for char in part) for part in name.split("/"))):
            if name not in repositories:
                repositories.append(name)
        if len(repositories) == 6:
            break
    if not repositories:
        return {"available": False, "configured": True, "stale": True}

    def load():
        results = []
        successful = 0
        for repo in repositories:
            encoded = "/".join(quote(part, safe="") for part in repo.split("/"))
            try:
                pulls = fetch_github("https://api.github.com/repos/" + encoded + "/pulls?state=open&per_page=20")
                if not isinstance(pulls, list):
                    raise ValueError("Unexpected GitHub response")
                runs_payload = fetch_github("https://api.github.com/repos/" + encoded + "/actions/runs?per_page=1")
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
                results.append({"repository": repo, "available": True,
                                "open_pr_count": len(pulls), "open_pr_count_truncated": len(pulls) == 20,
                                "latest_ci": ci,
                                "open_prs": [{"number": item["number"], "title": item["title"][:120],
                                              "url": item["html_url"]} for item in pulls[:3]]})
                successful += 1
            except (OSError, ValueError, TypeError, KeyError, HTTPError, URLError):
                # One failing repository must not erase the others.
                results.append({"repository": repo, "available": False,
                                "open_pr_count": None, "latest_ci": None, "open_prs": []})
        if not successful and repositories:
            raise ValueError("No repositories could be checked")
        return {"available": True, "repositories": results, "partial": successful < len(repositories)}
    token_scope = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else "public"
    return cached("github:" + ",".join(repositories) + ":" + token_scope, load, ttl=900)


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
            if len(cards) > 100:
                raise ValueError("Unexpected Trello card limit")
            result.append({"name": name, "count": len(cards),
                           "count_truncated": len(cards) == 100,
                           "cards": [str(card.get("name", ""))[:90] for card in cards[:3]]})
        return {"available": True, "configured": True, "lists": result}

    # Credential rotation must invalidate the old result without storing raw secrets.
    credential_scope = hashlib.sha256((key + "\0" + token).encode("utf-8")).hexdigest()
    return cached("trello:" + board + ":" + credential_scope, load, ttl=600)


def quotes() -> dict:
    """Read at most two opt-in provider quotes, with long cache to conserve API credits."""
    raw = os.environ.get("TRIS_QUOTE_SYMBOLS", "").strip()
    token = os.environ.get("TRIS_TWELVEDATA_API_KEY", "").strip()
    if not raw or not token:
        return {"available": False, "configured": False, "stale": False}
    try:
        symbols = quote_symbols(raw)
    except ValueError:
        return {"available": False, "configured": True, "stale": True}
    scope = hashlib.sha256(token.encode("utf-8")).hexdigest()
    key = "quotes:" + ",".join(symbols) + ":" + scope
    now = time.monotonic()
    with _lock:
        blocked = _QUOTE_RETRY_AT.get(key, 0) > now
        previous = _cache.get(key)
    if blocked:
        if previous and now - previous["time"] <= MAX_STALE_SECONDS:
            snapshot = dict(previous["data"])
            snapshot["stale"] = True
            snapshot["rate_limited_retry"] = True
            return refresh_quote_freshness(snapshot)
        return {"available": False, "configured": True, "stale": True,
                "rate_limited_retry": True}
    def load():
        try:
            result = load_quotes(symbols, token, get_json)
        except (OSError, ValueError, TypeError, KeyError, HTTPError, URLError):
            with _lock:
                _QUOTE_RETRY_AT[key] = time.monotonic() + _QUOTE_RETRY_SECONDS
            raise
        with _lock:
            _QUOTE_RETRY_AT.pop(key, None)
        return result
    result = cached(key, load, ttl=1800)
    return refresh_quote_freshness(result)


def overview(timeout_seconds: float = 4.0) -> dict:
    """Collect slow upstreams concurrently without delaying the whole dashboard indefinitely."""
    providers = {"weather": weather, "github": github, "trello": trello, "quotes": quotes}
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
    result["valuation"] = quote_valuation(result["portfolio"], result["quotes"])
    result["fitness"] = fitness()
    result["dividends"] = dividends()
    result["agenda"] = agenda()
    return result

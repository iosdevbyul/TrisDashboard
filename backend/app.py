"""Local-only dashboard server. Bind to the LAN interface at runtime."""
import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from backend.integrations import overview

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
STARTED = time.monotonic()
app = FastAPI(title="TrisDashboard", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


@app.middleware("http")
async def secure_local_responses(request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    # Data and HTML are private to this LAN service. Always refetch after reconnect.
    if request.url.path == "/" or request.url.path.startswith("/api/") or request.url.path == "/healthz":
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html", media_type="text/html")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def dashboard_overview() -> JSONResponse:
    data = overview()
    data["server"] = {
        "available": True,
        "uptime_seconds": max(0, int(time.monotonic() - STARTED)),
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "stale": False,
    }
    return JSONResponse(data, headers={"Cache-Control": "no-store"})

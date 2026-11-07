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
app = FastAPI(title="TrisDashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")


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

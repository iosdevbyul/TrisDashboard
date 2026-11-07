"""Local-only dashboard server. Bind to the LAN interface at runtime."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
app = FastAPI(title="TrisDashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(FRONTEND / "static")), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(FRONTEND / "index.html", media_type="text/html")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

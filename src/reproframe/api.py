from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .models import RunSummary, VisualBrief
from .pipeline import build_pipeline
from .storage import B2ArtifactStore

PACKAGE_ROOT = Path(__file__).parent
settings = get_settings()
pipeline = build_pipeline(settings)

app = FastAPI(
    title="ReproFrame AI",
    version="0.1.0",
    description="Evidence-grounded scientific visuals with replayable provenance.",
)
app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")
app.mount(
    "/artifacts",
    StaticFiles(directory=settings.artifact_dir, check_dir=False),
    name="artifacts",
)
templates = Jinja2Templates(directory=PACKAGE_ROOT / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": settings.mode, "version": app.version}


@app.post("/api/runs", response_model=RunSummary)
def create_run(brief: VisualBrief) -> RunSummary:
    return pipeline.run(brief)


@app.get("/api/artifacts/{key:path}")
def read_cloud_artifact(key: str) -> Response:
    if not isinstance(pipeline.store, B2ArtifactStore):
        raise HTTPException(status_code=404, detail="Cloud artifact store is not active")
    try:
        payload, content_type = pipeline.store.get_bytes(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )

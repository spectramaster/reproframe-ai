from __future__ import annotations

import logging
from pathlib import Path
from threading import BoundedSemaphore
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .models import ReviewDecision, RunDetails, RunSummary, VerificationReport, VisualBrief
from .pipeline import build_pipeline
from .runs import (
    build_bundle,
    list_runs,
    load_run_details,
    normalize_run_id,
    save_review,
    verify_run,
)
from .storage import B2ArtifactStore

PACKAGE_ROOT = Path(__file__).parent
settings = get_settings()
pipeline = build_pipeline(settings)
run_slots = BoundedSemaphore(settings.max_concurrent_runs)
logger = logging.getLogger(__name__)

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


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self'"
    )
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": settings.mode, "version": app.version}


@app.post("/api/runs", response_model=RunSummary)
def create_run(brief: VisualBrief) -> RunSummary:
    if not run_slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="All generation slots are busy; retry shortly.")
    try:
        return pipeline.run(brief)
    except Exception as exc:
        logger.exception("ReproFrame generation failed")
        raise HTTPException(
            status_code=502,
            detail="Generation failed safely; no credentials or provider details were exposed.",
        ) from exc
    finally:
        run_slots.release()


@app.get("/api/runs", response_model=list[RunSummary])
def read_runs(limit: int = Query(default=12, ge=1, le=50)) -> list[RunSummary]:
    return list_runs(pipeline.store, limit=limit)


@app.get("/api/runs/{run_id}", response_model=RunDetails)
def read_run(run_id: UUID) -> RunDetails:
    try:
        return load_run_details(pipeline.store, run_id)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.get("/api/runs/{run_id}/verify", response_model=VerificationReport)
def read_verification(run_id: UUID) -> VerificationReport:
    try:
        return verify_run(pipeline.store, run_id)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@app.post("/api/runs/{run_id}/review", status_code=201)
def create_review(
    run_id: UUID,
    review: ReviewDecision,
    review_token: str | None = Header(default=None, alias="X-ReproFrame-Review-Token"),
) -> dict[str, str]:
    if not settings.review_token or review_token != settings.review_token:
        raise HTTPException(status_code=403, detail="A valid human-review token is required.")
    try:
        url = save_review(pipeline.store, run_id, review)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return {"status": "recorded", "review_url": url}


@app.get("/api/runs/{run_id}/bundle")
def download_bundle(run_id: UUID) -> Response:
    try:
        payload = build_bundle(pipeline.store, run_id)
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="reproframe-{run_id}-evidence.zip"',
            "Cache-Control": "private, no-store",
        },
    )


@app.get("/api/artifacts/{key:path}")
def read_cloud_artifact(key: str) -> Response:
    if not isinstance(pipeline.store, B2ArtifactStore):
        raise HTTPException(status_code=404, detail="Cloud artifact store is not active")
    try:
        first, *_ = key.split("/", 1)
        normalize_run_id(first)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    if ".." in key.split("/"):
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        payload, content_type = pipeline.store.get_bytes(key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )

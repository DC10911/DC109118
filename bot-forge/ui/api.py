"""BOT-FORGE FastAPI web API server."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.config import get_settings
from core.database import JobRepository
from core.logging_setup import setup_logging
from core.models import BotSpec, JobRecord, PipelineStage
from core.pipeline import run_pipeline

app = FastAPI(
    title="BOT-FORGE API",
    description="Meta-bot factory: generate production-ready bots from JSON specs",
    version="1.0.0",
)

_repo: JobRepository | None = None


def _get_repo() -> JobRepository:
    global _repo
    if _repo is None:
        settings = get_settings()
        settings.ensure_dirs()
        _repo = JobRepository(settings.db_path)
    return _repo


@app.on_event("startup")
async def startup() -> None:
    setup_logging(get_settings().log_level)
    await _get_repo().init()


class ForgeRequest(BaseModel):
    """Request to generate a new bot."""
    name: str
    platform: str
    description: str
    features: list[str] = ["echo"]
    dependencies: list[str] = []
    env_vars: list[dict] = []
    include_docker: bool = True
    include_ci: bool = True
    include_tests: bool = True
    logging_level: str = "INFO"


class JobResponse(BaseModel):
    id: str
    bot_name: str
    platform: str
    stage: str
    output_path: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


def _job_to_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        bot_name=job.spec.name,
        platform=job.spec.platform.value,
        stage=job.stage.value,
        output_path=job.output_path,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "bot-forge"}


@app.post("/forge", response_model=JobResponse)
async def forge_bot(req: ForgeRequest):
    """Trigger the bot-generation pipeline."""
    settings = get_settings()
    try:
        spec = BotSpec.model_validate(req.model_dump())
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    repo = _get_repo()
    job = await run_pipeline(spec, repo, settings.templates_dir, settings.output_dir)

    if job.stage == PipelineStage.FAILED:
        raise HTTPException(status_code=500, detail=job.error or "Pipeline failed")

    return _job_to_response(job)


@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    """List recent bot-generation jobs."""
    repo = _get_repo()
    records = await repo.list_all()
    return [_job_to_response(j) for j in records]


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get status of a specific job."""
    repo = _get_repo()
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)

"""Orchestration API. Run: ``uv run uvicorn drama_api.app:app``.

``POST /projects/{id}/run`` enqueues on Redis/RQ when reachable; otherwise the
in-process ``InlineJobQueue`` runs the mock (or configured) pipeline
synchronously so local demo and CI work without Redis.

The Phase 6 workbench is a static SPA at ``/`` (see ``apps/web``).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from drama_core import (
    GENRE_PRESETS,
    RIGHTS_DISCLAIMER,
    LicenseStatus,
    PipelineStage,
    Project,
    ReviewAction,
    ReviewTargetType,
    Settings,
)
from drama_pipeline import Orchestrator, build_orchestrator
from drama_review import OverrideBook
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from drama_api.exports import ExportView, build_export_view
from drama_api.jobs import InlineJobQueue, Job, JobQueue
from drama_api.runtime import build_runtime
from drama_api.store import MemoryProjectStore, ProjectStore
from drama_api.web import mount_workbench


class CreateProjectRequest(BaseModel):
    title: str
    genre: str = Field(description="Preset 都市/玄幻/古言/悬疑/甜宠/爽文 or free-text theme")
    premise: str
    total_words: int = Field(gt=0)
    word_min: int = 2500
    word_max: int = 5000
    license_status: LicenseStatus = LicenseStatus.UNKNOWN
    rights_note: str = ""


class OverrideRequest(BaseModel):
    action: ReviewAction
    target_id: str | None = None
    target_type: ReviewTargetType | None = None
    reason: str = "human override"


class RunRequest(BaseModel):
    override_verdict: ReviewAction | None = None


class ProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    license_status: LicenseStatus
    stage: PipelineStage
    chapters: int
    shots: int
    clips: int
    reviews: int
    failure_reason: str | None = None
    updated_at: datetime
    created_at: datetime

    @classmethod
    def of(cls, p: Project) -> ProjectSummary:
        return cls(
            id=p.id,
            title=p.title,
            genre=p.genre,
            license_status=p.license_status,
            stage=p.stage,
            chapters=len(p.chapters),
            shots=len(p.shots),
            clips=len(p.clips),
            reviews=len(p.reviews),
            failure_reason=p.failure_reason,
            updated_at=_updated_at(p),
            created_at=p.created_at,
        )


def _updated_at(project: Project) -> datetime:
    stamps = [project.created_at]
    if project.stage_history:
        stamps.append(project.stage_history[-1].at)
    if project.reviews:
        stamps.append(project.reviews[-1].created_at)
    return max(stamps)


def _cors_origins() -> list[str]:
    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    extra = os.environ.get("CORS_ORIGINS", "")
    return defaults + [part.strip() for part in extra.split(",") if part.strip()]


def create_app(
    orchestrator: Orchestrator | None = None,
    queue: JobQueue | None = None,
    *,
    store: ProjectStore | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    cfg = settings or Settings.from_env()
    orch = orchestrator or build_orchestrator(cfg)
    # Injected orchestrator without an explicit queue stays in-process so pytest
    # remains offline even if a developer laptop has Redis on localhost.
    if queue is None and store is None and orchestrator is not None and settings is None:
        jobs: JobQueue = InlineJobQueue()
        projects: ProjectStore = MemoryProjectStore()
    elif queue is None and store is None:
        jobs, projects = build_runtime(cfg)
    else:
        jobs = queue or InlineJobQueue()
        projects = store or MemoryProjectStore()
    app = FastAPI(
        title="AI Novel Drama Factory",
        version="0.0.1",
        description="编排 API + Web 工作台。默认 mock，无 Redis / 密钥也可本地使用。",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _project(project_id: str) -> Project:
        found = projects.get(project_id)
        if found is None:
            raise HTTPException(404, "project not found")
        return found

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "queue": jobs.backend}

    @app.get("/genres")
    def list_genres() -> dict[str, object]:
        return {
            "presets": list(GENRE_PRESETS),
            "free_text": True,
            "license_status": [item.value for item in LicenseStatus],
            "rights_disclaimer": RIGHTS_DISCLAIMER,
            "review_actions": [item.value for item in ReviewAction],
            "target_types": [item.value for item in ReviewTargetType],
            "stages": [item.value for item in PipelineStage],
        }

    @app.get("/projects")
    def list_projects() -> list[ProjectSummary]:
        summaries = [ProjectSummary.of(item) for item in projects.list_projects()]
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return summaries

    @app.post("/projects", status_code=201)
    def create_project(req: CreateProjectRequest) -> ProjectSummary:
        p = Project(**req.model_dump())
        projects.put(p)
        return ProjectSummary.of(p)

    @app.get("/projects/{project_id}")
    def get_project(project_id: str) -> Project:
        return _project(project_id)

    @app.get("/projects/{project_id}/exports")
    def get_exports(project_id: str) -> ExportView:
        return build_export_view(_project(project_id), Path(cfg.output_dir))

    @app.post("/projects/{project_id}/override", status_code=200)
    def set_override(project_id: str, req: OverrideRequest) -> dict[str, object]:
        p = _project(project_id)
        book = OverrideBook.from_project(p)
        book.set(
            req.action,
            target_id=req.target_id,
            target_type=req.target_type,
            reason=req.reason,
        )
        book.attach(p)
        projects.put(p)
        return {"project_id": p.id, "overrides": book.to_payload()}

    @app.post("/projects/{project_id}/run", status_code=202)
    def run_project(project_id: str, req: RunRequest | None = None) -> Job:
        p = _project(project_id)
        if req and req.override_verdict is not None:
            book = OverrideBook.from_project(p)
            book.global_action = req.override_verdict
            book.attach(p)
        projects.put(p)
        return jobs.submit(
            Job(kind="pipeline.run", project_id=p.id),
            lambda: orch.run(p).stage is PipelineStage.DONE,
        )

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> Job:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    mount_workbench(app)
    return app


app = create_app()

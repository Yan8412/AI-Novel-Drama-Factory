"""Orchestration API stubs (FastAPI). Run: ``uv run uvicorn drama_api.app:app``."""

from __future__ import annotations

from drama_core import PipelineStage, Project, ReviewAction, ReviewTargetType, Settings
from drama_pipeline import Orchestrator, build_orchestrator
from drama_review import OverrideBook
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from drama_api.jobs import InlineJobQueue, Job, JobQueue


class CreateProjectRequest(BaseModel):
    title: str
    genre: str
    premise: str
    total_words: int = Field(gt=0)
    word_min: int = 2500
    word_max: int = 5000


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
    stage: PipelineStage
    chapters: int
    shots: int
    clips: int
    reviews: int
    failure_reason: str | None = None

    @classmethod
    def of(cls, p: Project) -> ProjectSummary:
        return cls(
            id=p.id,
            title=p.title,
            stage=p.stage,
            chapters=len(p.chapters),
            shots=len(p.shots),
            clips=len(p.clips),
            reviews=len(p.reviews),
            failure_reason=p.failure_reason,
        )


def create_app(orchestrator: Orchestrator | None = None, queue: JobQueue | None = None) -> FastAPI:
    orch = orchestrator or build_orchestrator(Settings.from_env())
    jobs = queue or InlineJobQueue()
    projects: dict[str, Project] = {}
    app = FastAPI(title="AI Novel Drama Factory", version="0.0.1")

    def _project(project_id: str) -> Project:
        if project_id not in projects:
            raise HTTPException(404, "project not found")
        return projects[project_id]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/projects", status_code=201)
    def create_project(req: CreateProjectRequest) -> ProjectSummary:
        p = Project(**req.model_dump())
        projects[p.id] = p
        return ProjectSummary.of(p)

    @app.get("/projects/{project_id}")
    def get_project(project_id: str) -> Project:
        return _project(project_id)

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
        return {"project_id": p.id, "overrides": book.to_payload()}

    @app.post("/projects/{project_id}/run", status_code=202)
    def run_project(project_id: str, req: RunRequest | None = None) -> Job:
        p = _project(project_id)
        if req and req.override_verdict is not None:
            book = OverrideBook.from_project(p)
            book.global_action = req.override_verdict
            book.attach(p)
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

    return app


app = create_app()

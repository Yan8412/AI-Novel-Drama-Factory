"""Orchestration API stubs (FastAPI). Run: ``uv run uvicorn drama_api.app:app``."""

from __future__ import annotations

from drama_core import PipelineStage, Project, Settings
from drama_pipeline import Orchestrator, build_orchestrator
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

    @app.post("/projects/{project_id}/run", status_code=202)
    def run_project(project_id: str) -> Job:
        p = _project(project_id)
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

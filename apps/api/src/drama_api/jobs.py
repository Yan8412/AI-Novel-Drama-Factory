"""Job queue stub. Phase 0 runs jobs inline; swap for Redis/RQ/Celery later."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from drama_core import new_id
from drama_core.models import utcnow
from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: new_id("job"))
    kind: str
    project_id: str
    status: JobStatus = JobStatus.QUEUED
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class JobQueue(Protocol):
    def submit(self, job: Job, fn: Callable[[], bool]) -> Job: ...

    def get(self, job_id: str) -> Job | None: ...


class InlineJobQueue:
    """Executes the job synchronously in ``submit``; ``fn`` returns success."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, job: Job, fn: Callable[[], bool]) -> Job:
        with self._lock:
            self._jobs[job.id] = job
        job.status = JobStatus.RUNNING
        try:
            job.status = JobStatus.SUCCEEDED if fn() else JobStatus.FAILED
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = f"{type(exc).__name__}: {exc}"
        job.finished_at = utcnow()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

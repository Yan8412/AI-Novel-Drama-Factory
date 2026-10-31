"""RQ-backed queue. Import is lazy so CI can run without a live Redis."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from drama_core import public_error_text
from drama_core.models import utcnow

from drama_api.jobs import Job, JobStatus

QUEUE_NAME = "drama"


class RedisUnavailable(RuntimeError):
    pass


def map_rq_status(status: object, result: object = None) -> JobStatus:
    name = str(getattr(status, "value", status) or "").lower()
    if name in {"queued", "deferred", "scheduled"}:
        return JobStatus.QUEUED
    if name in {"started"}:
        return JobStatus.RUNNING
    if name in {"finished"}:
        return JobStatus.SUCCEEDED if result is True else JobStatus.FAILED
    if name in {"failed", "stopped", "canceled", "cancelled"}:
        return JobStatus.FAILED
    return JobStatus.QUEUED


def job_from_rq(rq_job: Any, fallback: Job | None = None) -> Job:
    meta = getattr(rq_job, "meta", None) or {}
    args = tuple(getattr(rq_job, "args", ()) or ())
    kind = str(meta.get("kind") or (fallback.kind if fallback else "pipeline.run"))
    from_args = args[0] if args else ""
    from_fallback = fallback.project_id if fallback else ""
    project_id = str(meta.get("project_id") or from_args or from_fallback)
    created = getattr(rq_job, "created_at", None) or (fallback.created_at if fallback else utcnow())
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    ended = getattr(rq_job, "ended_at", None)
    if hasattr(rq_job, "get_status"):
        status_name = rq_job.get_status()
    else:
        status_name = getattr(rq_job, "status", "")
    result = getattr(rq_job, "result", None)
    mapped = map_rq_status(status_name, result)
    error: str | None = None
    if mapped is JobStatus.FAILED:
        raw = getattr(rq_job, "exc_info", None) or getattr(rq_job, "error", None)
        if raw:
            error = public_error_text(raw)
        elif result is False:
            error = "pipeline did not reach done"
    return Job(
        id=str(getattr(rq_job, "id", "") or (fallback.id if fallback else "")),
        kind=kind,
        project_id=project_id,
        status=mapped,
        error=error,
        created_at=created,
        finished_at=ended,
        backend="redis",
    )


class RedisJobQueue:
    backend = "redis"

    def __init__(self, redis: Any, queue: Any = None) -> None:
        self.connection = redis
        if queue is None:
            from rq import Queue

            queue = Queue(QUEUE_NAME, connection=redis)
        self._queue = queue

    @classmethod
    def connect(cls, url: str) -> RedisJobQueue:
        try:
            from redis import Redis
            from redis.exceptions import RedisError
        except ImportError as exc:  # pragma: no cover - workspace always installs redis
            raise RedisUnavailable("redis package is not installed") from exc
        try:
            client = Redis.from_url(
                url,
                socket_connect_timeout=0.4,
                socket_timeout=2.0,
                decode_responses=False,
            )
            client.ping()
        except (RedisError, OSError, TimeoutError) as exc:
            raise RedisUnavailable(f"Redis not reachable at {url}") from exc
        return cls(client)

    def submit(self, job: Job, fn: Callable[[], bool]) -> Job:
        del fn  # worker reconstructs the pipeline from Settings + the project store
        job.backend = self.backend
        rq_job = self._queue.enqueue(
            "drama_api.worker.run_pipeline_job",
            job.project_id,
            job_id=job.id,
            result_ttl=86400,
            failure_ttl=86400,
            meta={
                "kind": job.kind,
                "project_id": job.project_id,
                "created_at": job.created_at.isoformat(),
            },
        )
        return job_from_rq(rq_job, fallback=job)

    def get(self, job_id: str) -> Job | None:
        from rq.exceptions import NoSuchJobError
        from rq.job import Job as RQJob

        try:
            rq_job = RQJob.fetch(job_id, connection=self.connection)
        except NoSuchJobError:
            return None
        return job_from_rq(rq_job)

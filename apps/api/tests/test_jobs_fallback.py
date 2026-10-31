from types import SimpleNamespace

import pytest
from drama_api.jobs import InlineJobQueue, Job, JobStatus
from drama_api.redis_queue import RedisUnavailable, job_from_rq, map_rq_status
from drama_api.runtime import create_job_queue
from drama_core import Settings


def test_inline_queue_runs_fn() -> None:
    q = InlineJobQueue()
    job = q.submit(Job(kind="pipeline.run", project_id="p1"), lambda: True)
    assert job.status is JobStatus.SUCCEEDED
    assert q.get(job.id) is job
    failed = q.submit(Job(kind="pipeline.run", project_id="p1"), lambda: False)
    assert failed.status is JobStatus.FAILED


def test_auto_queue_falls_back_when_redis_down() -> None:
    q = create_job_queue(Settings(job_queue="auto", redis_url="redis://127.0.0.1:1/0"))
    assert q.backend == "memory"
    assert isinstance(q, InlineJobQueue)


def test_memory_queue_forced() -> None:
    q = create_job_queue(Settings(job_queue="memory", redis_url="redis://127.0.0.1:6379/0"))
    assert q.backend == "memory"


def test_forced_redis_raises_when_unreachable() -> None:
    with pytest.raises(RedisUnavailable, match="JOB_QUEUE"):
        create_job_queue(Settings(job_queue="redis", redis_url="redis://127.0.0.1:1/0"))


def test_map_rq_status() -> None:
    assert map_rq_status("queued") is JobStatus.QUEUED
    assert map_rq_status("started") is JobStatus.RUNNING
    assert map_rq_status("finished", True) is JobStatus.SUCCEEDED
    assert map_rq_status("finished", False) is JobStatus.FAILED
    assert map_rq_status("failed") is JobStatus.FAILED


def test_job_from_rq_redacts_exc_info() -> None:
    rq_job = SimpleNamespace(
        id="job_abc",
        meta={"kind": "pipeline.run", "project_id": "proj_1"},
        args=("proj_1",),
        created_at=None,
        ended_at=None,
        result=None,
        exc_info="Traceback: Authorization: Bearer sk-live-secret-key",
        get_status=lambda: "failed",
    )
    job = job_from_rq(rq_job)
    assert job.status is JobStatus.FAILED
    assert job.backend == "redis"
    assert job.project_id == "proj_1"
    assert job.error is not None
    assert "sk-live-secret-key" not in job.error
    assert "***" in job.error

"""Optional live Redis/RQ enqueue. Skipped in CI unless RUN_LIVE_REDIS=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from drama_api.app import create_app
from drama_api.redis_queue import QUEUE_NAME, RedisJobQueue
from drama_api.store import RedisProjectStore
from drama_core import Settings
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_LIVE_REDIS") != "1", reason="set RUN_LIVE_REDIS=1")
def test_live_redis_enqueue_and_simple_worker(tmp_path: Path) -> None:
    from redis import Redis
    from rq import SimpleWorker

    settings = Settings.from_env().model_copy(update={"output_dir": tmp_path, "job_queue": "redis"})
    redis = Redis.from_url(settings.redis_url)
    redis.ping()
    queue = RedisJobQueue(redis)
    store = RedisProjectStore(redis)
    client = TestClient(create_app(queue=queue, store=store, settings=settings))

    created = client.post(
        "/projects",
        json={
            "title": "t",
            "genre": "都市",
            "premise": "p",
            "total_words": 3000,
            "license_status": "original",
        },
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "queued"
    assert job["backend"] == "redis"

    SimpleWorker([QUEUE_NAME], connection=redis).work(burst=True)

    polled = client.get(f"/jobs/{job['id']}").json()
    assert polled["status"] == "succeeded"
    project = client.get(f"/projects/{pid}").json()
    assert project["stage"] == "done"
    assert project["genre"] == "都市"

"""RQ worker: ``uv run drama-factory-worker`` or ``uv run python -m drama_api.worker``."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from drama_core import PipelineStage, Settings
from drama_pipeline import build_orchestrator

from drama_api.redis_queue import QUEUE_NAME
from drama_api.store import RedisProjectStore


def run_pipeline_job(project_id: str) -> bool:
    """Importable RQ target. Reconstructs engines from ``Settings.from_env()``."""
    settings = Settings.from_env()
    store = RedisProjectStore.from_url(settings.redis_url)
    project = store.get(project_id)
    if project is None:
        raise RuntimeError(f"project {project_id} not found in Redis store")
    result = build_orchestrator(settings).run(project)
    store.put(result)
    return result.stage is PipelineStage.DONE


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    settings = Settings.from_env()
    try:
        from redis import Redis
        from rq import Worker
    except ImportError as exc:
        print(f"redis/rq is required for the worker: {exc}", file=sys.stderr)
        return 2
    redis = Redis.from_url(settings.redis_url)
    redis.ping()
    print(f"drama-factory-worker listening on {settings.redis_url} queue={QUEUE_NAME}")
    Worker([QUEUE_NAME], connection=redis).work()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Choose Redis/RQ when reachable, otherwise the in-process fallback."""

from __future__ import annotations

from drama_core import Settings

from drama_api.jobs import InlineJobQueue, JobQueue
from drama_api.redis_queue import RedisJobQueue, RedisUnavailable
from drama_api.store import MemoryProjectStore, ProjectStore, RedisProjectStore


class RedisForcedUnavailable(RedisUnavailable):
    pass


def create_job_queue(settings: Settings | None = None) -> JobQueue:
    cfg = settings or Settings.from_env()
    mode = (cfg.job_queue or "auto").strip().lower()
    if mode in {"memory", "inline", "sync"}:
        return InlineJobQueue()
    try:
        return RedisJobQueue.connect(cfg.redis_url)
    except RedisUnavailable:
        if mode in {"redis", "rq"}:
            raise RedisForcedUnavailable(
                f"JOB_QUEUE={mode} but Redis is unreachable at {cfg.redis_url}"
            ) from None
        return InlineJobQueue()


def create_project_store_for(
    settings: Settings | None,
    queue: JobQueue,
) -> ProjectStore:
    cfg = settings or Settings.from_env()
    if isinstance(queue, RedisJobQueue):
        return RedisProjectStore(queue.connection)
    if cfg.job_queue.strip().lower() in {"redis", "rq"}:
        return RedisProjectStore.from_url(cfg.redis_url)
    return MemoryProjectStore()


def build_runtime(
    settings: Settings | None = None,
) -> tuple[JobQueue, ProjectStore]:
    cfg = settings or Settings.from_env()
    queue = create_job_queue(cfg)
    return queue, create_project_store_for(cfg, queue)

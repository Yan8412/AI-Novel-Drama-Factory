"""Project persistence shared by the API process and RQ workers."""

from __future__ import annotations

import threading
from typing import Any, Protocol

from drama_core import Project


class ProjectStore(Protocol):
    def put(self, project: Project) -> None: ...

    def get(self, project_id: str) -> Project | None: ...


class MemoryProjectStore:
    """In-process dict. Same object is mutated by the inline queue."""

    def __init__(self) -> None:
        self._items: dict[str, Project] = {}
        self._lock = threading.Lock()

    def put(self, project: Project) -> None:
        with self._lock:
            self._items[project.id] = project

    def get(self, project_id: str) -> Project | None:
        return self._items.get(project_id)


class RedisProjectStore:
    PREFIX = "drama:project:"

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    @classmethod
    def from_url(cls, url: str) -> RedisProjectStore:
        from redis import Redis

        client = Redis.from_url(
            url,
            socket_connect_timeout=0.4,
            socket_timeout=2.0,
            decode_responses=True,
        )
        client.ping()
        return cls(client)

    def put(self, project: Project) -> None:
        self._redis.set(self.PREFIX + project.id, project.model_dump_json())

    def get(self, project_id: str) -> Project | None:
        raw = self._redis.get(self.PREFIX + project_id)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return Project.model_validate_json(raw)

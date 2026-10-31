from pathlib import Path

from drama_api.app import create_app
from drama_api.exports import safe_read_text
from drama_api.store import MemoryProjectStore, RedisProjectStore
from drama_core import Project, Settings
from drama_pipeline import build_orchestrator
from fastapi.testclient import TestClient


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(output_dir=tmp_path)
    return TestClient(create_app(build_orchestrator(settings), settings=settings))


def test_workbench_static_pages(tmp_path: Path) -> None:
    client = _client(tmp_path)
    home = client.get("/")
    assert home.status_code == 200
    assert "工作台" in home.text
    alias = client.get("/workbench")
    assert alias.status_code == 200
    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "运行流水线" in js.text
    css = client.get("/static/styles.css")
    assert css.status_code == 200


def test_list_projects_and_updated_at(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/projects").json() == []
    first = client.post(
        "/projects",
        json={"title": "甲", "genre": "都市", "premise": "p1", "total_words": 3000},
    )
    second = client.post(
        "/projects",
        json={
            "title": "乙",
            "genre": "悬疑",
            "premise": "p2",
            "total_words": 3000,
            "license_status": "original",
        },
    )
    assert first.status_code == 201
    listed = client.get("/projects").json()
    assert [item["title"] for item in listed] == ["乙", "甲"]
    row = next(item for item in listed if item["id"] == second.json()["id"])
    assert row["genre"] == "悬疑"
    assert row["license_status"] == "original"
    assert row["stage"] == "created"
    assert row["updated_at"]
    assert row["created_at"]


def test_exports_after_run_and_traversal(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/projects",
        json={
            "title": "导出",
            "genre": "玄幻",
            "premise": "p",
            "total_words": 3000,
            "license_status": "original",
            "rights_note": "原创短篇占位",
        },
    )
    pid = created.json()["id"]
    before = client.get(f"/projects/{pid}/exports").json()
    assert before["shot_count"] == 0
    assert before["play_md"] is None
    assert all(not item["available"] for item in before["files"])

    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "succeeded"
    after = client.get(f"/projects/{pid}/exports").json()
    assert after["chapter_count"] >= 1
    assert after["shot_count"] >= 1
    assert after["episodes"]
    names = {item["name"]: item for item in after["files"]}
    assert names["PLAY.md"]["available"] is True
    assert names["budget.json"]["available"] is True
    assert after["play_md"] and "ffmpeg" in after["play_md"]
    assert after["budget_json"] and "estimated_usd" in after["budget_json"]

    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    assert safe_read_text(tmp_path / pid, "../secret.txt") is None
    assert safe_read_text(tmp_path / pid, "/etc/passwd") is None


def test_cors_localhost(tmp_path: Path) -> None:
    client = _client(tmp_path)
    res = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_memory_and_fake_redis_list() -> None:
    mem = MemoryProjectStore()
    a = Project(title="a", genre="都市", premise="p", total_words=3000)
    mem.put(a)
    assert [item.id for item in mem.list_projects()] == [a.id]

    class FakeRedis:
        def __init__(self) -> None:
            self.data: dict[str, str] = {}

        def set(self, key: str, value: str) -> None:
            self.data[key] = value

        def get(self, key: str) -> str | None:
            return self.data.get(key)

        def scan_iter(self, match: str = "*") -> list[str]:
            prefix = match.removesuffix("*")
            return [key for key in self.data if key.startswith(prefix)]

    store = RedisProjectStore(FakeRedis())
    store.put(a)
    listed = store.list_projects()
    assert len(listed) == 1
    assert listed[0].title == "a"

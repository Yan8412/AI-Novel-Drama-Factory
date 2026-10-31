from pathlib import Path

from drama_api.app import create_app
from drama_api.store import MemoryProjectStore
from drama_core import (
    Chapter,
    Project,
    Review,
    ReviewAction,
    ReviewTargetType,
    Settings,
)
from drama_pipeline import build_orchestrator
from fastapi.testclient import TestClient


def test_create_run_and_poll(tmp_path: Path) -> None:
    client = TestClient(create_app(build_orchestrator(Settings(output_dir=tmp_path))))
    assert client.get("/health").json() == {"status": "ok", "queue": "memory"}
    genres = client.get("/genres").json()
    assert "都市" in genres["presets"]
    assert genres["free_text"] is True

    created = client.post(
        "/projects",
        json={
            "title": "t",
            "genre": "都市",
            "premise": "p",
            "total_words": 6000,
            "license_status": "original",
            "rights_note": "原创短篇占位",
        },
    )
    assert created.status_code == 201
    assert created.json()["genre"] == "都市"
    assert created.json()["license_status"] == "original"
    pid = created.json()["id"]

    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "succeeded"
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "succeeded"

    project = client.get(f"/projects/{pid}").json()
    assert project["stage"] == "done"
    assert project["genre"] == "都市"
    assert project["license_status"] == "original"
    assert project["rights_note"] == "原创短篇占位"
    assert project["reviews"]
    assert project["episodes"]
    listed = client.get("/projects").json()
    assert listed and listed[0]["id"] == pid
    assert listed[0]["genre"] == "都市"
    assert listed[0]["license_status"] == "original"
    exports = client.get(f"/projects/{pid}/exports").json()
    assert exports["shot_count"] >= 1
    assert exports["play_md"]
    assert client.get("/projects/nope").status_code == 404


def test_override_endpoint_forces_pass(tmp_path: Path) -> None:
    client = TestClient(create_app(build_orchestrator(Settings(output_dir=tmp_path))))
    created = client.post(
        "/projects", json={"title": "t", "genre": "g", "premise": "p", "total_words": 3000}
    )
    pid = created.json()["id"]
    override = client.post(f"/projects/{pid}/override", json={"action": "pass", "reason": "qa"})
    assert override.status_code == 200
    assert override.json()["overrides"]["global"] == "pass"
    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "succeeded"
    project = client.get(f"/projects/{pid}").json()
    assert project["stage"] == "done"
    assert all(r["reviewer"] == "human-override" for r in project["reviews"])


def test_budget_usage_and_review_desk(tmp_path: Path) -> None:
    client = TestClient(create_app(build_orchestrator(Settings(output_dir=tmp_path))))
    created = client.post(
        "/projects", json={"title": "t", "genre": "都市", "premise": "p", "total_words": 3000}
    )
    pid = created.json()["id"]
    empty_usage = client.get("/usage").json()
    assert empty_usage["estimated_usd"] == 0.0
    assert empty_usage["quota"]["blocked"] is False
    assert "token_per_1k_usd" in empty_usage["prices"]

    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "succeeded"
    budget = client.get(f"/projects/{pid}/budget").json()
    assert budget["project_id"] == pid
    assert budget["estimated_usd"] == 0.0
    assert "tokens" in budget["units"]
    assert budget["last_run"]["run_id"]
    desk = client.get(f"/projects/{pid}/reviews").json()
    assert desk["targets"]
    assert desk["pending"] == 0
    assert any(row["target_type"] == "chapter" for row in desk["targets"])
    usage = client.get("/usage").json()
    assert usage["projects"]


def test_pass_pending_writes_target_overrides(tmp_path: Path) -> None:
    store = MemoryProjectStore()
    project = Project(title="t", genre="都市", premise="p", total_words=3000)
    project.chapters.append(
        Chapter(id="ch_desk", index=1, title="开端", body="一二三四五", target_words=3000)
    )
    project.reviews.append(
        Review(
            target_type=ReviewTargetType.CHAPTER,
            target_id="ch_desk",
            attempt=1,
            action=ReviewAction.REVISE,
            reviewer="mock-deterministic",
        )
    )
    project.revision_queue = ["ch_desk"]
    store.put(project)
    settings = Settings(output_dir=tmp_path)
    client = TestClient(create_app(build_orchestrator(settings), store=store, settings=settings))
    desk = client.get(f"/projects/{project.id}/reviews").json()
    assert desk["pending"] == 1
    res = client.post(
        f"/projects/{project.id}/override",
        json={"action": "pass", "pass_pending": True, "reason": "desk pass"},
    )
    assert res.status_code == 200
    assert res.json()["overrides"]["targets"]["ch_desk"] == "pass"
    assert res.json()["desk"]["targets"][0]["override"] == "pass"


def test_resume_after_reject(tmp_path: Path) -> None:
    client = TestClient(create_app(build_orchestrator(Settings(output_dir=tmp_path))))
    created = client.post(
        "/projects", json={"title": "t", "genre": "g", "premise": "p", "total_words": 3000}
    )
    pid = created.json()["id"]
    client.post(f"/projects/{pid}/override", json={"action": "reject", "reason": "qa reject"})
    failed = client.post(f"/projects/{pid}/run").json()
    assert failed["status"] == "failed"
    assert client.get(f"/projects/{pid}").json()["stage"] == "failed"
    assert client.get(f"/projects/{pid}/reviews").json()["failed"] >= 1
    client.post(f"/projects/{pid}/override", json={"action": "pass", "reason": "desk unblock"})
    rerun = client.post(f"/projects/{pid}/run").json()
    assert rerun["status"] == "succeeded"
    assert client.get(f"/projects/{pid}").json()["stage"] == "done"


def test_hard_quota_blocks_live_engines_not_mock(tmp_path: Path) -> None:
    live = Settings(output_dir=tmp_path, novel_engine="cloud", quota_max_usd=0.0)
    live_client = TestClient(create_app(build_orchestrator(live), settings=live))
    created = live_client.post(
        "/projects", json={"title": "t", "genre": "g", "premise": "p", "total_words": 3000}
    )
    blocked = live_client.post(f"/projects/{created.json()['id']}/run")
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "quota_exceeded"

    mock = Settings(output_dir=tmp_path, quota_max_usd=0.0, quota_soft_usd=0.0)
    mock_client = TestClient(create_app(build_orchestrator(mock), settings=mock))
    created_mock = mock_client.post(
        "/projects", json={"title": "t", "genre": "g", "premise": "p", "total_words": 3000}
    )
    job = mock_client.post(f"/projects/{created_mock.json()['id']}/run").json()
    assert job["status"] == "succeeded"
    assert job["warning"]
    usage = mock_client.get("/usage").json()
    assert usage["quota"]["soft_exceeded"] is True
    assert usage["quota"]["blocked"] is False


def test_deslop_scan_endpoint() -> None:
    client = TestClient(create_app())
    genres = client.get("/genres").json()
    assert genres["deslop"]["scan"] == "/deslop/scan"
    info = client.get("/deslop").json()
    assert info["enabled"] is True
    assert any(rule["id"] == "weak_adverb" for rule in info["rules"])
    clean = client.post("/deslop/scan", json={"text": "林晚把门关上。", "title": "一"}).json()
    assert clean["grade"] == "clean"
    assert clean["over_limit"] is False
    sloppy = client.post(
        "/deslop/scan",
        json={"text": "不难看出她微微一笑，又微微点头，再微微转身。"},
    ).json()
    assert sloppy["over_limit"] is True
    assert sloppy["hits"]

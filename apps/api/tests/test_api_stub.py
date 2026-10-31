from pathlib import Path

from drama_api.app import create_app
from drama_core import Settings
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

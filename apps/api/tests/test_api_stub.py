from pathlib import Path

from drama_api.app import create_app
from drama_core import Settings
from drama_pipeline import build_orchestrator
from fastapi.testclient import TestClient


def test_create_run_and_poll(tmp_path: Path) -> None:
    client = TestClient(create_app(build_orchestrator(Settings(output_dir=tmp_path))))
    assert client.get("/health").json() == {"status": "ok"}

    created = client.post(
        "/projects", json={"title": "t", "genre": "g", "premise": "p", "total_words": 6000}
    )
    assert created.status_code == 201
    pid = created.json()["id"]

    job = client.post(f"/projects/{pid}/run").json()
    assert job["status"] == "succeeded"
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "succeeded"

    project = client.get(f"/projects/{pid}").json()
    assert project["stage"] == "done"
    assert project["reviews"]
    assert client.get("/projects/nope").status_code == 404

from pathlib import Path

import httpx
from drama_core import Chapter, Project, Settings, Shot, Storyboard
from drama_tts import CloudTtsEngine, MockTtsEngine, create_subtitle_engine, create_tts_engine
from drama_tts.mock import NullTtsEngine


def _project() -> Project:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    chapter = Chapter(index=1, title="一", body="字" * 10, target_words=3000)
    shot = Shot(index=1, chapter_id=chapter.id, duration_s=8, dialogue="站住")
    project.chapters = [chapter]
    project.storyboards = [Storyboard(chapter_id=chapter.id, shots=[shot])]
    return project


def test_mock_tts_writes_sidecar(tmp_path: Path) -> None:
    project = _project()
    paths = MockTtsEngine().synthesize(project, project.shots, out_dir=tmp_path)
    assert len(paths) == 1
    assert paths[0].name == "shot_001_001.json"
    text = paths[0].read_text(encoding="utf-8")
    assert "站住" in text
    assert "mock sidecar" in text


def test_cloud_tts_falls_back_when_http_fails(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    engine = CloudTtsEngine(
        Settings(
            tts_engine="openai", tts_api_key="sk-test", tts_base_url="https://example.test/v1"
        ),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    paths = engine.synthesize(_project(), _project().shots, out_dir=tmp_path)
    assert paths
    assert paths[0].suffix == ".json"


def test_factories() -> None:
    assert create_tts_engine(Settings()).name == "mock-tts"
    assert isinstance(create_tts_engine(Settings(tts_engine="off")), NullTtsEngine)
    assert create_tts_engine(Settings(tts_engine="openai")).name == "openai-tts"
    assert create_subtitle_engine(Settings(subtitle_format="off")).name == "off"
    assert create_subtitle_engine(Settings()).name == "mock-subtitles"

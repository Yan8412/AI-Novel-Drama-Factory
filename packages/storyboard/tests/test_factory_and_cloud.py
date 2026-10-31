import json
from collections.abc import Mapping, Sequence

import pytest
from drama_core import Chapter, ChapterPlan, Project, Settings
from drama_novel import MockNovelEngine, NovelMemory
from drama_storyboard import (
    CloudStoryboardEngine,
    MockStoryboardEngine,
    StructuredStoryboardEngine,
    create_storyboard_engine,
)


class ScriptedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.4,
        json_mode: bool = True,
    ) -> str:
        self.calls.append([dict(m) for m in messages])
        return self.responses.pop(0)


def _project_with_bible() -> tuple[Project, Chapter]:
    project = Project(title="契约新娘", genre="都市甜宠", premise="契约", total_words=3000)
    bible = MockNovelEngine().create_bible(project)
    project.characters = bible.characters
    project.scenes = bible.scenes
    project.props = bible.props
    chapter = MockNovelEngine().write_chapter(
        project, ChapterPlan(index=1, title="雨夜", summary="对峙", target_words=800), NovelMemory()
    )
    return project, chapter


def test_factory_names() -> None:
    assert isinstance(create_storyboard_engine(Settings()), MockStoryboardEngine)
    assert isinstance(
        create_storyboard_engine(Settings(storyboard_engine="structured")),
        StructuredStoryboardEngine,
    )
    assert isinstance(
        create_storyboard_engine(Settings(storyboard_engine="cloud")), CloudStoryboardEngine
    )
    with pytest.raises(ValueError, match="STORYBOARD_ENGINE"):
        create_storyboard_engine(Settings(storyboard_engine="nope"))


def test_cloud_materializes_named_refs() -> None:
    project, chapter = _project_with_bible()
    payload = {
        "shots": [
            {
                "index": 1,
                "duration_s": 8,
                "camera": "特写 推镜",
                "action": "林晚攥紧玉佩",
                "dialogue": "“我不签。”",
                "character_names": ["林晚"],
                "scene_name": "雨夜街头",
                "prop_names": ["祖传玉佩"],
                "image_prompt": "vertical 9:16 rain street",
                "motion_prompt": "push in",
            },
            {
                "index": 2,
                "duration_s": 7,
                "camera": "中景",
                "action": "对峙",
                "character_names": ["顾沉"],
                "scene_name": "顾氏集团顶层办公室",
                "image_prompt": "office",
            },
        ]
    }
    engine = CloudStoryboardEngine(ScriptedClient([json.dumps(payload, ensure_ascii=False)]))
    board = engine.build(project, chapter)
    assert len(board.shots) == 2
    lin = next(c for c in project.characters if c.name == "林晚")
    assert board.shots[0].character_ids == [lin.id]
    prompt = board.shots[1].image_prompt
    assert "9:16" in prompt or "vertical" in prompt.lower()


def test_cloud_falls_back_when_json_empty() -> None:
    project, chapter = _project_with_bible()
    engine = CloudStoryboardEngine(ScriptedClient([json.dumps({"shots": []})]))
    board = engine.build(project, chapter)
    assert board.shots
    assert all(s.aspect_ratio == "9:16" for s in board.shots)

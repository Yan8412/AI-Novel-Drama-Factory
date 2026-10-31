from pathlib import Path

from drama_core import (
    Appearance,
    Asset,
    AssetKind,
    Character,
    CharacterIdentity,
    Clip,
    Project,
    Scene,
    Shot,
)
from drama_video import (
    CONTINUITY_LIMITATIONS,
    clip_review_request,
    clip_rule_issues,
    is_mock_clip_uri,
    motion_prompt,
    write_video_export,
)
from drama_video.mock import MockVideoEngine


def _project() -> Project:
    char = Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷", hair="黑长直", outfit="米白风衣"),
    )
    scene = Scene(name="雨夜街头", description="霓虹", time_of_day="夜")
    project = Project(
        title="契约",
        genre="都市",
        premise="p",
        total_words=3000,
        characters=[char],
        scenes=[scene],
    )
    return project


def test_motion_prompt_embeds_identity_and_previous_shot() -> None:
    project = _project()
    char = project.characters[0]
    shot = Shot(
        index=2,
        chapter_id="c",
        scene_id=project.scenes[0].id,
        character_ids=[char.id],
        duration_s=8,
        camera="over-shoulder",
        action="回头",
        motion_prompt="slow push-in on her face",
        image_prompt="vertical 9:16 rain",
    )
    keyframe = Asset(
        kind=AssetKind.SHOT_KEYFRAME,
        owner_id=shot.id,
        uri="mock://kf.png",
        prompt="vertical 9:16 keyframe",
    )
    sheet = Asset(
        kind=AssetKind.CHARACTER_NINE_VIEW,
        owner_id=char.id,
        uri="mock://sheet.png",
        prompt="identity lock: 林晚; outfit: 米白风衣",
        views=["front"],
    )
    prev = Clip(
        shot_id="shot_prev",
        source_asset_id="a",
        uri="mock://video/prev.mp4",
        duration_s=7,
        prompt="vertical 9:16 first beat",
    )
    text = motion_prompt(
        project,
        shot,
        keyframe,
        characters=project.characters,
        identity_refs=[sheet],
        previous_clip=prev,
        feedback="hold the coat color",
    )
    assert "vertical 9:16" in text
    assert "identity lock: 林晚" in text
    assert "mock://video/prev.mp4" in text
    assert "character_nine_view mock://sheet.png" in text
    assert "Revision notes: hold the coat color" in text
    assert "PuLID" in CONTINUITY_LIMITATIONS or "previous-shot" in CONTINUITY_LIMITATIONS.lower()


def test_clip_rule_issues_aspect_duration_refs() -> None:
    project = _project()
    keyframe = Asset(kind=AssetKind.SHOT_KEYFRAME, owner_id="s1", uri="mock://kf.png")
    project.assets.append(keyframe)
    shot = Shot(id="s1", index=2, chapter_id="c", duration_s=8, action="走")
    project.storyboards = []
    # attach shot via a tiny storyboard-less path: clip_rule_issues looks at project.shots
    from drama_core import Storyboard

    project.storyboards = [Storyboard(chapter_id="c", shots=[shot])]
    bad = Clip(
        shot_id=shot.id,
        source_asset_id="missing",
        uri="",
        duration_s=20,
        width=1920,
        height=1080,
        prompt="landscape wide shot",
    )
    messages = [i.message for i in clip_rule_issues(project, bad)]
    assert any("not 9:16" in m or "size" in m for m in messages)
    assert any("duration_s=20" in m for m in messages)
    assert any("missing keyframe" in m for m in messages)
    assert any("empty uri" in m for m in messages)

    good = Clip(
        shot_id=shot.id,
        source_asset_id=keyframe.id,
        uri="mock://video/x.mp4",
        duration_s=8,
        width=1080,
        height=1920,
        prompt="vertical 9:16 slow push-in identity lock",
    )
    majors = [i for i in clip_rule_issues(project, good) if i.severity in {"major", "blocker"}]
    assert majors == []


def test_clip_review_request_and_mock_engine() -> None:
    project = _project()
    char = project.characters[0]
    shot = Shot(
        index=1,
        chapter_id="c",
        character_ids=[char.id],
        duration_s=9,
        action="推门",
        motion_prompt="dolly in",
    )
    keyframe = Asset(kind=AssetKind.SHOT_KEYFRAME, owner_id=shot.id, uri="mock://kf.png")
    clip = MockVideoEngine().image_to_video(project, shot, keyframe)
    assert is_mock_clip_uri(clip.uri)
    assert clip.prompt.startswith("vertical 9:16")
    req = clip_review_request(project, clip)
    assert req.target_id == clip.id
    assert req.context["duration_s"] == 9
    assert req.content.startswith("mock://")


def test_write_video_export_materializes_stubs(tmp_path: Path) -> None:
    from drama_core import Chapter, Storyboard

    project = _project()
    chapter = Chapter(index=1, title="一", body="字" * 20, target_words=3000)
    project.chapters = [chapter]
    shot = Shot(index=1, chapter_id=chapter.id, duration_s=8, action="走")
    project.storyboards = [Storyboard(chapter_id=chapter.id, shots=[shot])]
    keyframe = Asset(kind=AssetKind.SHOT_KEYFRAME, owner_id=shot.id, uri="mock://kf.png")
    project.assets = [keyframe]
    project.clips = [MockVideoEngine().image_to_video(project, shot, keyframe)]
    path = write_video_export(tmp_path, project)
    assert path.name == "clips.json"
    data = path.read_text(encoding="utf-8")
    assert project.clips[0].id in data
    stubs = list((tmp_path / "videos").glob("*.mp4"))
    assert len(stubs) == 1
    assert stubs[0].read_bytes().startswith(b"drama-factory mock clip")
    assert list((tmp_path / "videos").glob("shot_001_001_r0.json"))

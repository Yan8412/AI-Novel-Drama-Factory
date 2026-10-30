"""Chapter -> vertical (9:16) storyboard of 5-15s shots."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drama_core import Chapter, Project, Shot, Storyboard


@runtime_checkable
class StoryboardEngine(Protocol):
    name: str

    def build(self, project: Project, chapter: Chapter) -> Storyboard: ...


class MockStoryboardEngine:
    """Splits every chapter into a fixed number of shots cycling through scenes and cast."""

    name = "mock-storyboard"
    _DURATIONS = (6.0, 8.0, 10.0, 12.0)
    _CAMERAS = ("特写 推镜", "中景 跟拍", "近景 仰拍", "全景 摇镜")

    def __init__(self, shots_per_chapter: int = 3) -> None:
        if shots_per_chapter < 1:
            raise ValueError("shots_per_chapter must be >= 1")
        self.shots_per_chapter = shots_per_chapter

    def build(self, project: Project, chapter: Chapter) -> Storyboard:
        shots: list[Shot] = []
        cast = project.characters
        for i in range(self.shots_per_chapter):
            k = chapter.index + i
            scene = project.scenes[k % len(project.scenes)] if project.scenes else None
            chars = (
                [cast[k % len(cast)].id, cast[(k + 1) % len(cast)].id]
                if len(cast) > 1
                else [c.id for c in cast]
            )
            names = "、".join(c.name for c in cast if c.id in chars)
            where = scene.name if scene else "未知场景"
            shots.append(
                Shot(
                    index=i + 1,
                    chapter_id=chapter.id,
                    scene_id=scene.id if scene else None,
                    character_ids=chars,
                    prop_ids=[it.prop_id for it in scene.inventory] if scene else [],
                    duration_s=self._DURATIONS[k % len(self._DURATIONS)],
                    camera=self._CAMERAS[k % len(self._CAMERAS)],
                    action=f"{names}在{where}对峙",
                    dialogue="“这一次，我不会再退。”" if i == self.shots_per_chapter - 1 else "",
                    image_prompt=f"vertical 9:16, {where}, {names}, cinematic, short drama",
                    motion_prompt="slow push-in, subtle hair movement, rain particles",
                )
            )
        return Storyboard(chapter_id=chapter.id, shots=shots)


def to_markdown(project: Project, storyboard: Storyboard) -> str:
    """Human-editable shot list (markdown table), the hand-off format for I2V."""
    names = {c.id: c.name for c in project.characters}
    scenes = {s.id: s.name for s in project.scenes}
    chapter = next((c for c in project.chapters if c.id == storyboard.chapter_id), None)
    lines = [
        f"# 分镜 · {chapter.title if chapter else storyboard.chapter_id}",
        "",
        "| # | 时长(s) | 场景 | 角色 | 镜头 | 动作 | 台词 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in storyboard.shots:
        cast = "、".join(names.get(c, c) for c in s.character_ids)
        scene = scenes.get(s.scene_id or "", "")
        cells = (s.index, f"{s.duration_s:g}", scene, cast, s.camera, s.action, s.dialogue)
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"


__all__ = ["MockStoryboardEngine", "StoryboardEngine", "to_markdown"]

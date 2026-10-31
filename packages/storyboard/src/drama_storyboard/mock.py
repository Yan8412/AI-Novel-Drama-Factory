"""Deterministic offline storyboard: fixed shot count, cycles cast and scenes."""

from __future__ import annotations

from drama_core import VERTICAL_ASPECT_RATIO, Chapter, Project, Shot, Storyboard

from drama_storyboard.refs import fallback_cast, fallback_scene


class MockStoryboardEngine:
    """Splits every chapter into a fixed number of 9:16 shots (CI / demo baseline)."""

    name = "mock-storyboard"
    _DURATIONS = (6.0, 8.0, 10.0, 12.0)
    _CAMERAS = ("特写 推镜", "中景 跟拍", "近景 仰拍", "全景 摇镜")

    def __init__(self, shots_per_chapter: int = 3) -> None:
        if shots_per_chapter < 1:
            raise ValueError("shots_per_chapter must be >= 1")
        self.shots_per_chapter = shots_per_chapter

    def build(
        self,
        project: Project,
        chapter: Chapter,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Storyboard:
        shots: list[Shot] = []
        for i in range(self.shots_per_chapter):
            k = chapter.index + i + revision
            scene_id = fallback_scene(project, k)
            scene = next((s for s in project.scenes if s.id == scene_id), None)
            chars = fallback_cast(project, k)
            names = "、".join(c.name for c in project.characters if c.id in chars)
            where = scene.name if scene else "未知场景"
            shots.append(
                Shot(
                    index=i + 1,
                    chapter_id=chapter.id,
                    scene_id=scene_id,
                    character_ids=chars,
                    prop_ids=[it.prop_id for it in scene.inventory] if scene else [],
                    duration_s=self._DURATIONS[k % len(self._DURATIONS)],
                    camera=self._CAMERAS[k % len(self._CAMERAS)],
                    action=f"{names}在{where}对峙",
                    dialogue="“这一次，我不会再退。”" if i == self.shots_per_chapter - 1 else "",
                    image_prompt=(
                        f"vertical {VERTICAL_ASPECT_RATIO}, {where}, {names}, "
                        "cinematic lighting, short-drama still, 9:16 portrait"
                    ),
                    motion_prompt="slow push-in, subtle hair movement, rain particles",
                    aspect_ratio=project.aspect_ratio or VERTICAL_ASPECT_RATIO,
                )
            )
        return Storyboard(chapter_id=chapter.id, shots=shots, revision=revision)

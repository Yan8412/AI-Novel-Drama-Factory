"""Offline storyboard: split chapter prose into short-drama beats and 9:16 shots."""

from __future__ import annotations

from drama_core import VERTICAL_ASPECT_RATIO, Chapter, Project, Shot, Storyboard

from drama_storyboard.pacing import Beat, cluster_beats, plan_duration, plan_shot_count, split_beats
from drama_storyboard.refs import resolve_refs

_CAMERAS = (
    "特写 推镜",
    "中景 跟拍",
    "近景 仰拍",
    "半身 固定",
    "全景 摇镜",
    "过肩 近景",
)
_MOTIONS = (
    "slow push-in, handheld micro-shake",
    "gentle pan, rain particles",
    "hold then snap zoom",
    "parallax background, hair movement",
)


class StructuredStoryboardEngine:
    """Rule-based beat packer. No network. Suitable for CI and as a cloud fallback."""

    name = "structured-storyboard"

    def __init__(self, shots_per_chapter: int | None = None) -> None:
        if shots_per_chapter is not None and shots_per_chapter < 1:
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
        beats = split_beats(chapter.body)
        n = self.shots_per_chapter or plan_shot_count(chapter.word_count)
        groups = cluster_beats(beats, n)
        shots: list[Shot] = []
        for i, group in enumerate(groups):
            text = "".join(b.text for b in group) or chapter.summary or chapter.title
            dialogue = next((b.dialogue for b in reversed(group) if b.dialogue), "")
            chars, scene_id, props = resolve_refs(project, text, index=chapter.index + i + revision)
            scene = next((s for s in project.scenes if s.id == scene_id), None)
            names = "、".join(c.name for c in project.characters if c.id in chars)
            where = scene.name if scene else "室内"
            action = _action(group, names, where, chapter.summary)
            if feedback and revision:
                action = f"{action}（按审核修订）"
            packed_words = sum(b.word_count for b in group)
            shots.append(
                Shot(
                    index=i + 1,
                    chapter_id=chapter.id,
                    scene_id=scene_id,
                    character_ids=chars,
                    prop_ids=props,
                    duration_s=plan_duration(packed_words),
                    camera=_CAMERAS[(i + revision) % len(_CAMERAS)],
                    action=action,
                    dialogue=dialogue,
                    image_prompt=_image_prompt(project, where, names, action),
                    motion_prompt=_MOTIONS[(i + revision) % len(_MOTIONS)],
                    aspect_ratio=project.aspect_ratio or VERTICAL_ASPECT_RATIO,
                )
            )
        return Storyboard(chapter_id=chapter.id, shots=shots, revision=revision)


def _action(group: list[Beat], names: str, where: str, summary: str) -> str:
    snippet = "".join(b.text for b in group).strip()
    if snippet:
        clipped = snippet if len(snippet) <= 48 else snippet[:47] + "…"
        return clipped
    who = names or "角色"
    return f"{who}在{where}推进剧情：{summary}" if summary else f"{who}在{where}"


def _image_prompt(project: Project, where: str, names: str, action: str) -> str:
    return (
        f"vertical {project.aspect_ratio}, 9:16 portrait short-drama still, "
        f"{where}, {names}, {action}, cinematic lighting, shallow depth of field"
    )

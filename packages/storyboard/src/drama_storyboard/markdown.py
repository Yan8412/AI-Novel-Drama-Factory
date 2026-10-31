"""Human-editable shot list (markdown table + per-shot prompts)."""

from __future__ import annotations

from drama_core import Project, Storyboard


def to_markdown(project: Project, storyboard: Storyboard) -> str:
    """Hand-off format for I2V: table plus 9:16 prompts and continuity refs."""
    names = {c.id: c.name for c in project.characters}
    scenes = {s.id: s.name for s in project.scenes}
    props = {p.id: p.name for p in project.props}
    chapter = next((c for c in project.chapters if c.id == storyboard.chapter_id), None)
    lines = [
        f"# 分镜 · {chapter.title if chapter else storyboard.chapter_id}",
        "",
        f"画幅：{project.aspect_ratio}  修订：{storyboard.revision}",
        "",
        "| # | 时长(s) | 场景 | 角色 | 镜头 | 动作 | 台词 |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in storyboard.shots:
        cast = "、".join(names.get(c, c) for c in s.character_ids)
        scene = scenes.get(s.scene_id or "", "")
        cells = (s.index, f"{s.duration_s:g}", scene, cast, s.camera, s.action, s.dialogue)
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    if storyboard.shots:
        lines.append("")
        lines.append("## 镜头提示词")
        for s in storyboard.shots:
            prop_names = "、".join(props.get(p, p) for p in s.prop_ids) or "（无）"
            lines.extend(
                [
                    "",
                    f"### Shot {s.index}",
                    f"- 道具: {prop_names}",
                    f"- 画幅: {s.aspect_ratio}",
                    f"- 起点: {s.start_state}",
                    f"- 唯一动作: {s.primary_action or s.action}",
                    f"- 终点: {s.end_state}",
                    f"- 角色锁: {s.character_lock}",
                    f"- 造型锁: {s.wardrobe_lock}",
                    f"- 场景锁: {s.scene_lock}",
                    f"- 画面: {s.image_prompt}",
                    f"- 运动: {s.motion_prompt}",
                ]
            )
    return "\n".join(lines) + "\n"

"""Resolve character / scene / prop ids mentioned in a beat or shot prompt."""

from __future__ import annotations

from drama_core import Character, Project, Prop, Scene


def match_characters(text: str, characters: list[Character]) -> list[str]:
    return [c.id for c in characters if c.name and c.name in text]


def match_scenes(text: str, scenes: list[Scene]) -> list[str]:
    hits: list[str] = []
    for scene in scenes:
        tokens = [scene.name, *scene.description.split("，"), scene.time_of_day]
        if any(token and token in text for token in tokens if len(token) >= 2):
            hits.append(scene.id)
    return hits


def match_props(text: str, props: list[Prop]) -> list[str]:
    return [p.id for p in props if p.name and p.name in text]


def fallback_cast(project: Project, index: int) -> list[str]:
    cast = project.characters
    if not cast:
        return []
    if len(cast) == 1:
        return [cast[0].id]
    return [cast[index % len(cast)].id, cast[(index + 1) % len(cast)].id]


def fallback_scene(project: Project, index: int) -> str | None:
    if not project.scenes:
        return None
    return project.scenes[index % len(project.scenes)].id


def resolve_refs(
    project: Project, text: str, *, index: int
) -> tuple[list[str], str | None, list[str]]:
    """Return (character_ids, scene_id, prop_ids) with sensible fallbacks."""
    chars = match_characters(text, project.characters) or fallback_cast(project, index)
    scenes = match_scenes(text, project.scenes)
    scene_id = scenes[0] if scenes else fallback_scene(project, index)
    props = match_props(text, project.props)
    if not props and scene_id:
        scene = next((s for s in project.scenes if s.id == scene_id), None)
        if scene is not None:
            props = [item.prop_id for item in scene.inventory]
    return chars, scene_id, props

"""Short-drama continuity locks: character / wardrobe / scene + start→action→end."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from drama_core import Character, Project, Scene, Shot

_SPLIT_MARKERS = ("然后", "接着", "同时", "随后")


@dataclass(frozen=True)
class ContinuityLock:
    character_lock: str
    wardrobe_lock: str
    scene_lock: str
    start_state: str
    primary_action: str
    end_state: str

    def as_verbatim(self) -> str:
        parts = [
            self.character_lock,
            f"wardrobe lock: {self.wardrobe_lock}" if self.wardrobe_lock else "",
            f"scene lock: {self.scene_lock}" if self.scene_lock else "",
        ]
        body = "; ".join(part for part in parts if part)
        return f"Continuity lock (verbatim): {body}" if body else ""

    def state_chain(self) -> str:
        start = self.start_state or "hold the established blocking"
        action = self.primary_action or "one visible beat"
        end = self.end_state or "hold the end pose"
        return f"start: {start}. single motion: {action}. end: {end}."


def primary_action_of(action: str) -> str:
    text = (action or "").strip()
    if not text:
        return ""
    cut = len(text)
    for marker in _SPLIT_MARKERS:
        index = text.find(marker)
        if index > 0:
            cut = min(cut, index)
    clipped = text[:cut].strip(" ，,。；;")
    if len(clipped) > 48:
        return clipped[:47] + "…"
    return clipped


def lock_from_shot(project: Project, shot: Shot) -> ContinuityLock:
    chars = [c for c in project.characters if c.id in shot.character_ids]
    scene = next((s for s in project.scenes if s.id == shot.scene_id), None)
    return build_continuity_lock(
        characters=chars,
        scene=scene,
        action=shot.primary_action or shot.action,
        props=_prop_names(project, shot.prop_ids),
        character_lock=shot.character_lock,
        wardrobe_lock=shot.wardrobe_lock,
        scene_lock=shot.scene_lock,
        start_state=shot.start_state,
        end_state=shot.end_state,
        primary_action=shot.primary_action,
    )


def build_continuity_lock(
    *,
    characters: Sequence[Character] = (),
    scene: Scene | None = None,
    action: str = "",
    props: Sequence[str] = (),
    character_lock: str = "",
    wardrobe_lock: str = "",
    scene_lock: str = "",
    start_state: str = "",
    end_state: str = "",
    primary_action: str = "",
) -> ContinuityLock:
    names = "、".join(c.name for c in characters) or "ensemble"
    where = scene.name if scene is not None else "interior"
    holding = "、".join(props)
    derived_action = primary_action or primary_action_of(action) or action
    derived_start = start_state or (
        f"{names} at {where}" + (f", holding {holding}" if holding else "")
    )
    derived_end = end_state or f"after {derived_action}: {names} remain at {where}"
    return ContinuityLock(
        character_lock=character_lock.strip() or _character_lock(characters),
        wardrobe_lock=wardrobe_lock.strip() or _wardrobe_lock(characters),
        scene_lock=scene_lock.strip() or _scene_lock(scene),
        start_state=derived_start,
        primary_action=derived_action,
        end_state=derived_end,
    )


def apply_continuity(project: Project, shot: Shot) -> Shot:
    """Fill empty continuity fields on a shot; keep any caller-supplied locks."""
    lock = lock_from_shot(project, shot)
    return shot.model_copy(
        update={
            "primary_action": shot.primary_action or lock.primary_action,
            "start_state": shot.start_state or lock.start_state,
            "end_state": shot.end_state or lock.end_state,
            "character_lock": shot.character_lock or lock.character_lock,
            "wardrobe_lock": shot.wardrobe_lock or lock.wardrobe_lock,
            "scene_lock": shot.scene_lock or lock.scene_lock,
        }
    )


def multi_action_markers(action: str) -> list[str]:
    return [marker for marker in _SPLIT_MARKERS if marker in (action or "")]


def _character_lock(characters: Sequence[Character]) -> str:
    blocks: list[str] = []
    for char in characters:
        app = char.appearance
        face = app.description or char.name
        hair = app.hair or "unspecified hair"
        eyes = app.eyes or "unspecified eyes"
        marks = ", ".join(app.distinguishing_marks) or "none"
        blocks.append(
            f"identity lock: {char.name}; face: {face}; hair: {hair}; eyes: {eyes}; marks: {marks}"
        )
    return " ".join(blocks)


def _wardrobe_lock(characters: Sequence[Character]) -> str:
    parts = []
    for char in characters:
        outfit = char.appearance.outfit or "unspecified outfit"
        parts.append(f"{char.name}: {outfit}")
    return "; ".join(parts)


def _scene_lock(scene: Scene | None) -> str:
    if scene is None:
        return ""
    time = scene.time_of_day or "unspecified"
    return f"{scene.name}: {scene.description}; time-of-day: {time}"


def _prop_names(project: Project, prop_ids: Sequence[str]) -> list[str]:
    by_id = {prop.id: prop.name for prop in project.props}
    return [by_id[item] for item in prop_ids if item in by_id]

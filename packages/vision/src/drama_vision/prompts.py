"""Structured image prompts: 9-view sheets, scene multi-views, props, keyframes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from drama_core import (
    VERTICAL_ASPECT_RATIO,
    Asset,
    Character,
    Project,
    Prop,
    Scene,
    Shot,
)

NINE_VIEWS: tuple[str, ...] = (
    "front",
    "front_left_45",
    "left",
    "back_left_45",
    "back",
    "back_right_45",
    "right",
    "front_right_45",
    "face_closeup",
)

SCENE_VIEWS: tuple[str, ...] = (
    "establishing_wide",
    "medium_eyeline",
    "detail_foreground",
    "left_45",
    "right_45",
    "high_angle",
    "day",
    "golden_hour",
    "night",
)

PROP_VIEWS: tuple[str, ...] = ("hero_front", "three_quarter", "detail_macro")

_PALETTE_HINTS: tuple[tuple[str, str], ...] = (
    ("黑", "charcoal black"),
    ("白", "ivory white"),
    ("米白", "warm ivory"),
    ("灰", "cool gray"),
    ("酒红", "burgundy"),
    ("红", "crimson"),
    ("深灰", "slate gray"),
    ("棕", "warm brown"),
    ("金", "antique gold"),
    ("蓝", "navy"),
)


@dataclass(frozen=True)
class IdentityAnchors:
    name: str
    face: str
    hair: str
    eyes: str
    outfit: str
    distinguishing_marks: tuple[str, ...]
    color_palette: tuple[str, ...]

    def as_prompt_block(self) -> str:
        marks = ", ".join(self.distinguishing_marks) or "none"
        palette = ", ".join(self.color_palette)
        return (
            f"identity lock: {self.name}; face: {self.face}; hair: {self.hair}; "
            f"eyes: {self.eyes}; outfit: {self.outfit}; marks: {marks}; "
            f"color palette: [{palette}]"
        )


def identity_anchors(character: Character) -> IdentityAnchors:
    app = character.appearance
    face = app.description or f"{character.identity.gender or ''} {character.identity.age or ''}"
    palette = _palette(app.hair, app.eyes, app.outfit, app.description)
    return IdentityAnchors(
        name=character.name,
        face=face.strip() or character.name,
        hair=app.hair or "unspecified hair",
        eyes=app.eyes or "unspecified eyes",
        outfit=app.outfit or "unspecified outfit",
        distinguishing_marks=tuple(app.distinguishing_marks),
        color_palette=palette,
    )


def character_nine_view_prompt(character: Character, *, feedback: str = "") -> str:
    anchors = identity_anchors(character)
    views = ", ".join(NINE_VIEWS)
    extra = f" Revision notes: {feedback}." if feedback else ""
    return (
        f"character turnaround 3x3 grid, nine views ({views}), "
        f"consistent identity, full body except face_closeup, "
        f"neutral studio lighting, seamless gray backdrop, "
        f"{anchors.as_prompt_block()}.{extra}"
    )


def scene_multiview_prompt(scene: Scene, *, feedback: str = "") -> str:
    views = ", ".join(SCENE_VIEWS)
    inventory = ", ".join(item.placement for item in scene.inventory if item.placement)
    extra = f" Revision notes: {feedback}." if feedback else ""
    time = scene.time_of_day or "unspecified"
    props = f" continuity props: {inventory}." if inventory else ""
    return (
        f"environment design sheet, nine views ({views}), "
        f"location: {scene.name}, {scene.description}, time-of-day base: {time}, "
        f"vertical short-drama set, no characters, matching architecture and palette."
        f"{props}{extra}"
    )


def prop_prompt(prop: Prop, owner_name: str | None = None, *, feedback: str = "") -> str:
    extra = f" Revision notes: {feedback}." if feedback else ""
    owner = f" owned by {owner_name}," if owner_name else ""
    views = ", ".join(PROP_VIEWS)
    return (
        f"hero prop turnaround ({views}),{owner} {prop.name}: {prop.description}, "
        f"product-style lighting, continuity lock, isolated on gray."
        f"{extra}"
    )


def shot_keyframe_prompt(
    project: Project,
    shot: Shot,
    *,
    character_names: list[str],
    scene_name: str,
    feedback: str = "",
    references: Sequence[Asset] | None = None,
    characters: Sequence[Character] | None = None,
) -> str:
    extra = f" Revision notes: {feedback}." if feedback else ""
    cast = ", ".join(character_names) or "ensemble"
    where = scene_name or "interior"
    base = shot.image_prompt or shot.action
    anchors = []
    for char in characters or ():
        if char.id in shot.character_ids:
            anchors.append(identity_anchors(char).as_prompt_block())
    lock = f" {'; '.join(anchors)}." if anchors else ""
    ref_bits = []
    for asset in references or ():
        snippet = (asset.prompt or "").strip() or asset.uri
        ref_bits.append(f"{asset.kind.value} {asset.uri}: {snippet[:360]}")
    refs = f" Continuity refs: {' | '.join(ref_bits)}." if ref_bits else ""
    return (
        f"vertical {project.aspect_ratio or VERTICAL_ASPECT_RATIO} short-drama keyframe, "
        f"{where}, {cast}, {shot.camera}, {base},{lock} "
        f"match character 9-view identity lock and scene multi-view palette.{refs}{extra}"
    )


def _palette(*parts: str) -> tuple[str, ...]:
    found: list[str] = []
    blob = " ".join(parts)
    for needle, color in _PALETTE_HINTS:
        if needle in blob and color not in found:
            found.append(color)
        if len(found) >= 4:
            break
    if not found:
        found = ["charcoal", "ivory", "warm gray"]
    return tuple(found)

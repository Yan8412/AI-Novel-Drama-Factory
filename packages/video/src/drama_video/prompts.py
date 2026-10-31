"""I2V motion prompts: 9:16, identity locks, previous-shot continuity."""

from __future__ import annotations

from collections.abc import Sequence

from drama_core import VERTICAL_ASPECT_RATIO, Asset, Character, Clip, Project, Shot
from drama_vision import identity_anchors

# Cloud / local I2V backends typically accept one start frame + text.
# Previous-shot *video* is passed as a URI/text hint, not a guaranteed first-frame lock.
CONTINUITY_LIMITATIONS = (
    "Most I2V APIs accept one keyframe (or none) plus a text prompt. Identity locks "
    "from Phase 2 (9-view / scene / prop URIs and face-outfit-palette text) are "
    "embedded in the prompt; they are not pixel-level ID embeddings unless a Comfy "
    "graph binds PuLID/IPAdapter nodes. Previous-shot clips are referenced by URI "
    "and a short motion recap so the next clip can rhyme, but providers rarely "
    "condition on the prior MP4 itself."
)


def motion_prompt(
    project: Project,
    shot: Shot,
    keyframe: Asset,
    *,
    characters: Sequence[Character] = (),
    identity_refs: Sequence[Asset] = (),
    previous_clip: Clip | None = None,
    feedback: str = "",
) -> str:
    """Build a vertical I2V prompt that carries Phase 2 locks and shot-to-shot refs."""
    aspect = project.aspect_ratio or VERTICAL_ASPECT_RATIO
    motion = shot.motion_prompt or shot.action or shot.image_prompt
    names = [c.name for c in characters if c.id in shot.character_ids]
    cast = ", ".join(names) or "ensemble"
    scene = next((s.name for s in project.scenes if s.id == shot.scene_id), "")
    where = scene or "interior"
    anchors = [
        identity_anchors(char).as_prompt_block()
        for char in characters
        if char.id in shot.character_ids
    ]
    lock = f" {' '.join(anchors)}" if anchors else ""
    ref_bits = [f"keyframe {keyframe.uri}"]
    for asset in identity_refs:
        snippet = (asset.prompt or "").strip() or asset.uri
        ref_bits.append(f"{asset.kind.value} {asset.uri}: {snippet[:240]}")
    prev = ""
    if previous_clip is not None:
        recap = (previous_clip.prompt or previous_clip.uri).strip()
        prev = (
            f" Continue from previous clip {previous_clip.uri} "
            f"(duration {previous_clip.duration_s:g}s): {recap[:240]}."
        )
    extra = f" Revision notes: {feedback}." if feedback else ""
    return (
        f"vertical {aspect} short-drama shot, {shot.duration_s:g}s, "
        f"{where}, {cast}, camera: {shot.camera or 'handheld medium'}, "
        f"motion: {motion}.{lock} "
        f"Hold character 9-view identity lock and scene palette. "
        f"Refs: {' | '.join(ref_bits)}.{prev}{extra}"
    )

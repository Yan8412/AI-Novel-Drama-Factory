from drama_core import (
    Appearance,
    Character,
    CharacterIdentity,
    Project,
    Scene,
    Shot,
)
from drama_deslop import apply_continuity, multi_action_markers, primary_action_of


def test_apply_continuity_fills_start_action_end_and_locks() -> None:
    char = Character(
        name="林晚",
        identity=CharacterIdentity(role="女主"),
        appearance=Appearance(description="清冷", hair="黑长直", outfit="米白风衣"),
    )
    scene = Scene(name="雨夜街头", description="霓虹", time_of_day="夜")
    project = Project(
        title="t",
        genre="都市",
        premise="p",
        total_words=3000,
        characters=[char],
        scenes=[scene],
    )
    shot = Shot(
        index=1,
        chapter_id="c",
        scene_id=scene.id,
        character_ids=[char.id],
        duration_s=8,
        action="林晚回头看合同，然后把伞合上再推门",
    )
    filled = apply_continuity(project, shot)
    assert filled.primary_action
    assert "然后" not in filled.primary_action
    assert "林晚" in filled.start_state
    assert "雨夜街头" in filled.scene_lock
    assert "identity lock: 林晚" in filled.character_lock
    assert "米白风衣" in filled.wardrobe_lock
    assert filled.end_state.startswith("after")
    assert multi_action_markers(shot.action) == ["然后"]
    assert primary_action_of(shot.action) == "林晚回头看合同"

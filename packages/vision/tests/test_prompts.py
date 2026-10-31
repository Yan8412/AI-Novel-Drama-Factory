from drama_core import (
    Appearance,
    Character,
    CharacterIdentity,
    InventoryItem,
    Project,
    Prop,
    Scene,
)
from drama_vision import (
    NINE_VIEWS,
    SCENE_VIEWS,
    asset_prompt_issues,
    character_nine_view_prompt,
    identity_anchors,
    prop_prompt,
    scene_multiview_prompt,
)
from drama_vision.mock import MockVisionEngine


def _character() -> Character:
    return Character(
        name="林晚",
        identity=CharacterIdentity(role="女主", gender="女", age=24),
        appearance=Appearance(
            description="清冷气质，杏眼",
            hair="黑色长直发",
            eyes="深棕",
            outfit="米白风衣",
            distinguishing_marks=["左耳垂小痣"],
        ),
    )


def test_identity_anchors_and_nine_view_prompt() -> None:
    char = _character()
    anchors = identity_anchors(char)
    assert anchors.name == "林晚"
    assert "米白风衣" in anchors.outfit
    assert anchors.color_palette
    prompt = character_nine_view_prompt(char)
    assert all(view in prompt for view in NINE_VIEWS)
    assert "identity lock" in prompt
    assert "林晚" in prompt


def test_scene_and_prop_prompts() -> None:
    jade = Prop(name="祖传玉佩", description="白玉")
    scene = Scene(
        name="雨夜街头",
        description="霓虹倒影",
        time_of_day="夜",
        inventory=[InventoryItem(prop_id=jade.id, placement="林晚手中")],
    )
    scene_prompt = scene_multiview_prompt(scene)
    assert all(view in scene_prompt for view in SCENE_VIEWS)
    assert "雨夜街头" in scene_prompt
    assert "continuity props" in scene_prompt
    assert "祖传玉佩" in prop_prompt(jade, "林晚")


def test_mock_assets_satisfy_prompt_rules() -> None:
    project = Project(title="t", genre="g", premise="p", total_words=3000)
    char = _character()
    engine = MockVisionEngine()
    grid = engine.character_nine_view(project, char)
    assert grid.views == list(NINE_VIEWS)
    assert grid.uri.startswith("mock://")
    assert asset_prompt_issues(grid) == []
    scene = Scene(name="雨夜街头", description="霓虹", time_of_day="夜")
    sc = engine.scene_image(project, scene)
    assert sc.views == list(SCENE_VIEWS)
    assert not [i for i in asset_prompt_issues(sc) if i.severity in {"major", "blocker"}]
    prop = Prop(name="玉佩", description="白玉")
    pr = engine.prop_image(project, prop)
    assert not [i for i in asset_prompt_issues(pr) if i.severity in {"major", "blocker"}]

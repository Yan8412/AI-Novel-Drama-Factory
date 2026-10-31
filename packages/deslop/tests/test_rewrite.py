from drama_deslop import (
    ARCHITECTURE_PASS,
    DISCOURSE_PASS,
    WORDING_PASS,
    novel_deslop_system_suffix,
    novel_deslop_user_reminder,
    storyboard_deslop_system_suffix,
)


def test_three_pass_templates_cover_architecture_discourse_wording() -> None:
    block = novel_deslop_system_suffix()
    assert "第1层" in block and ARCHITECTURE_PASS[:6] in block
    assert "第2层" in block and "对白" in DISCOURSE_PASS
    assert "第3层" in block and "微微" in WORDING_PASS
    assert "心中暗道" in block
    assert novel_deslop_user_reminder()
    story = storyboard_deslop_system_suffix()
    assert "起点→唯一动作→终点" in story
    assert "不烧录字幕" in story

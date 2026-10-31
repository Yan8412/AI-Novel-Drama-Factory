"""Genre presets and a documentation-only rights placeholder."""

from __future__ import annotations

from enum import StrEnum

GENRE_PRESETS: tuple[str, ...] = (
    "都市",
    "玄幻",
    "古言",
    "悬疑",
    "甜宠",
    "爽文",
)

_GENRE_ALIASES: dict[str, str] = {
    "urban": "都市",
    "city": "都市",
    "fantasy": "玄幻",
    "xuanhuan": "玄幻",
    "xianxia": "玄幻",
    "historical": "古言",
    "ancient": "古言",
    "ancient-romance": "古言",
    "mystery": "悬疑",
    "suspense": "悬疑",
    "romance": "甜宠",
    "sweet": "甜宠",
    "power-fantasy": "爽文",
    "爽": "爽文",
}

_STYLE_HINTS: dict[str, str] = {
    "甜宠": "高甜互动、吃醋与守护，冲突点到为止，对白轻快。",
    "爽文": "打脸、逆袭、节奏快，每章给一次情绪兑现。",
    "悬疑": "线索、反转、不可靠叙述，每章结尾必须留扣。",
    "古言": "古代言情：礼法、权谋与情感拉扯，称谓与器物贴合朝代。",
    "玄幻": "修真/灵气体系、境界冲突、秘境与功法，对白带古风余韵。",
    "都市": "当代都市节奏：职场、阶层落差、现实对白，少仙侠设定。",
}

# More specific tags first so「都市甜宠」resolves to 甜宠, not 都市.
_FAMILY_ORDER: tuple[str, ...] = ("甜宠", "爽文", "悬疑", "古言", "玄幻", "都市")

RIGHTS_DISCLAIMER = (
    "license_status / rights_note 仅为项目文档占位，不构成权利声明、授权证明或法律意见。"
)


class LicenseStatus(StrEnum):
    """Documentation-only rights marker. Not a legal determination."""

    UNKNOWN = "unknown"
    ORIGINAL = "original"
    LICENSED = "licensed"


def normalize_genre(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("genre is required")
    if text in GENRE_PRESETS:
        return text
    return _GENRE_ALIASES.get(text.lower(), text)


def genre_family(genre: str) -> str | None:
    for family in _FAMILY_ORDER:
        if family in genre:
            return family
    return None


def genre_style_hint(genre: str) -> str:
    """Prompt fragment so mock/cloud writers stay on-theme."""
    family = genre_family(genre)
    hint = _STYLE_HINTS.get(family or "", "语气与设定保持统一，避免串题材。")
    return f"题材「{genre}」：{hint}"

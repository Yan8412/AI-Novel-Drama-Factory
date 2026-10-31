import pytest
from drama_core import (
    LicenseStatus,
    Project,
    genre_family,
    genre_style_hint,
    normalize_genre,
    public_error_text,
)
from pydantic import ValidationError


def test_normalize_genre_presets_and_aliases() -> None:
    assert normalize_genre(" 玄幻 ") == "玄幻"
    assert normalize_genre("urban") == "都市"
    assert normalize_genre("Mystery") == "悬疑"
    assert normalize_genre("赛博朋克") == "赛博朋克"
    with pytest.raises(ValueError, match="required"):
        normalize_genre("   ")


def test_genre_family_prefers_specific_tag() -> None:
    assert genre_family("都市甜宠") == "甜宠"
    assert genre_family("都市") == "都市"
    assert genre_family("赛博朋克") is None
    assert "甜宠" in genre_style_hint("都市甜宠")
    assert "玄幻" in genre_style_hint("玄幻")


def test_project_accepts_genre_and_rights_placeholder() -> None:
    p = Project(
        title="t",
        genre="xuanhuan",
        premise="p",
        total_words=3000,
        license_status=LicenseStatus.ORIGINAL,
        rights_note="原创短篇，仅文档占位",
    )
    assert p.genre == "玄幻"
    assert p.license_status is LicenseStatus.ORIGINAL
    assert p.rights_note.startswith("原创")
    clone = Project.model_validate_json(p.model_dump_json())
    assert clone.license_status is LicenseStatus.ORIGINAL


def test_project_defaults_rights_to_unknown() -> None:
    p = Project(title="t", genre="g", premise="p", total_words=3000)
    assert p.license_status is LicenseStatus.UNKNOWN
    assert p.rights_note == ""


def test_empty_genre_rejected() -> None:
    with pytest.raises(ValidationError):
        Project(title="t", genre="  ", premise="p", total_words=3000)


def test_public_error_text_redacts_secrets() -> None:
    raw = "Bearer sk-abcdefg123456 Authorization: Bearer tok video HTTP 401: api_key=super-secret"
    text = public_error_text(raw)
    assert "sk-abcdefg123456" not in text
    assert "super-secret" not in text
    assert "***" in text

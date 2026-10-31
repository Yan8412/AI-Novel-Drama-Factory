import pytest
from drama_core import Settings
from drama_novel import CloudNovelEngine, MockNovelEngine, NovelEngine, create_novel_engine


def test_default_novel_engine_is_mock() -> None:
    engine = create_novel_engine(Settings())
    assert isinstance(engine, MockNovelEngine)
    assert isinstance(engine, NovelEngine)


def test_cloud_aliases() -> None:
    for name in ("cloud", "openai", "deepseek", "qwen"):
        engine = create_novel_engine(Settings(novel_engine=name))
        assert isinstance(engine, CloudNovelEngine)
        assert engine.name == "cloud-novel"


def test_unknown_novel_engine() -> None:
    with pytest.raises(ValueError, match="NOVEL_ENGINE"):
        create_novel_engine(Settings(novel_engine="nope"))

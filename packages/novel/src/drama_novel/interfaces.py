from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from drama_core import Chapter, ChapterPlan, Character, Outline, Project, Prop, Review, Scene

from drama_novel.memory import NovelMemory


@dataclass
class StoryBible:
    """Genre + cast + world produced before outlining."""

    characters: list[Character]
    scenes: list[Scene]
    props: list[Prop] = field(default_factory=list)


@runtime_checkable
class NovelEngine(Protocol):
    """Planning + writing backend. Phase 1 implements this with cloud LLM APIs."""

    name: str

    def create_bible(self, project: Project) -> StoryBible: ...

    def write_outline(self, project: Project, chapter_targets: list[int]) -> Outline: ...

    def write_chapter(
        self, project: Project, plan: ChapterPlan, memory: NovelMemory
    ) -> Chapter: ...

    def revise_chapter(
        self, project: Project, chapter: Chapter, review: Review, memory: NovelMemory
    ) -> Chapter: ...

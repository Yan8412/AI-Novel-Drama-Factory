"""Storyboard engine protocol (mock / structured / cloud share this)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from drama_core import Chapter, Project, Storyboard


@runtime_checkable
class StoryboardEngine(Protocol):
    name: str

    def build(
        self,
        project: Project,
        chapter: Chapter,
        *,
        revision: int = 0,
        feedback: str = "",
    ) -> Storyboard: ...

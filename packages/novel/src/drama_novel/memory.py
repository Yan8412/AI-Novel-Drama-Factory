"""Long-term story memory accumulated chapter by chapter.

Mirrors the "memory as plain files" idea (see docs/opensource.md, novel-bot):
memory is human-readable markdown that can be diffed, edited and fed back into
the next chapter's prompt.
"""

from __future__ import annotations

from pathlib import Path

from drama_core import MemoryDelta
from pydantic import BaseModel, Field


class NovelMemory(BaseModel):
    facts: list[str] = Field(default_factory=list)
    character_states: dict[str, str] = Field(default_factory=dict)
    open_threads: list[str] = Field(default_factory=list)
    chapter_summaries: dict[int, str] = Field(default_factory=dict)

    def apply(self, chapter_index: int, summary: str, delta: MemoryDelta) -> None:
        self.chapter_summaries[chapter_index] = summary
        self.facts.extend(f for f in delta.new_facts if f not in self.facts)
        self.character_states.update(delta.character_updates)
        for t in delta.open_threads:
            if t not in self.open_threads:
                self.open_threads.append(t)
        self.open_threads = [t for t in self.open_threads if t not in delta.closed_threads]

    def to_markdown(self) -> str:
        lines = ["# 故事记忆", "", "## 已知事实"]
        lines += [f"- {f}" for f in self.facts] or ["- （无）"]
        lines += ["", "## 人物状态"]
        lines += [f"- {k}: {v}" for k, v in self.character_states.items()] or ["- （无）"]
        lines += ["", "## 未解伏笔"]
        lines += [f"- {t}" for t in self.open_threads] or ["- （无）"]
        lines += ["", "## 章节摘要"]
        lines += [f"- 第{i}章: {s}" for i, s in sorted(self.chapter_summaries.items())]
        return "\n".join(lines) + "\n"

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "memory.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")
        path = directory / "memory.md"
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path

    @classmethod
    def load(cls, directory: Path) -> NovelMemory:
        return cls.model_validate_json((directory / "memory.json").read_text(encoding="utf-8"))

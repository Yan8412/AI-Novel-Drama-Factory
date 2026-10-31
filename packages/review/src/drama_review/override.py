"""Human verdict overrides: skip the model and force pass / revise / reject."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from drama_core import Project, Review, ReviewAction, ReviewIssue, ReviewTargetType, Settings

from drama_review.contracts import Reviewer, ReviewRequest

OVERRIDE_REVIEWER = "human-override"

_ACTIONS = {item.value: item for item in ReviewAction}


def parse_action(raw: str | None) -> ReviewAction | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text or text in {"none", "null", "auto", "-"}:
        return None
    if text not in _ACTIONS:
        raise ValueError(f"unknown review action {raw!r} (expected pass|revise|reject)")
    return _ACTIONS[text]


@dataclass
class OverrideBook:
    """Lookup order: target id → target type → global."""

    global_action: ReviewAction | None = None
    by_type: dict[ReviewTargetType, ReviewAction] = field(default_factory=dict)
    by_id: dict[str, ReviewAction] = field(default_factory=dict)
    reason: str = "human override"

    def lookup(self, target_type: ReviewTargetType, target_id: str) -> ReviewAction | None:
        if target_id in self.by_id:
            return self.by_id[target_id]
        if target_type in self.by_type:
            return self.by_type[target_type]
        return self.global_action

    def set(
        self,
        action: ReviewAction,
        *,
        target_id: str | None = None,
        target_type: ReviewTargetType | None = None,
        reason: str | None = None,
    ) -> None:
        if reason:
            self.reason = reason
        if target_id:
            self.by_id[target_id] = action
            return
        if target_type is not None:
            self.by_type[target_type] = action
            return
        self.global_action = action

    def merge(self, other: OverrideBook) -> OverrideBook:
        global_action = (
            other.global_action if other.global_action is not None else self.global_action
        )
        merged = OverrideBook(
            global_action=global_action,
            by_type={**self.by_type, **other.by_type},
            by_id={**self.by_id, **other.by_id},
            reason=other.reason or self.reason,
        )
        return merged

    def to_payload(self) -> dict[str, Any]:
        return {
            "global": None if self.global_action is None else self.global_action.value,
            "types": {k.value: v.value for k, v in self.by_type.items()},
            "targets": {k: v.value for k, v in self.by_id.items()},
            "reason": self.reason,
        }

    @classmethod
    def from_payload(cls, data: Mapping[str, Any] | None) -> OverrideBook:
        if not data:
            return cls()
        types: dict[ReviewTargetType, ReviewAction] = {}
        for key, raw in dict(data.get("types") or {}).items():
            action = parse_action(str(raw))
            if action is None:
                continue
            types[ReviewTargetType(str(key))] = action
        targets: dict[str, ReviewAction] = {}
        for key, raw in dict(data.get("targets") or {}).items():
            action = parse_action(str(raw))
            if action is None:
                continue
            targets[str(key)] = action
        raw_global = data.get("global")
        return cls(
            global_action=parse_action(raw_global if isinstance(raw_global, str) else None),
            by_type=types,
            by_id=targets,
            reason=str(data.get("reason") or "human override"),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> OverrideBook:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("override file must be a JSON object")
        return cls.from_payload(payload)

    @classmethod
    def from_settings(cls, settings: Settings) -> OverrideBook:
        book = cls()
        if settings.review_override_file:
            book = book.merge(cls.from_file(settings.review_override_file))
        if settings.review_override:
            book.global_action = parse_action(settings.review_override)
        return book

    @classmethod
    def from_project(cls, project: Project) -> OverrideBook:
        raw = project.metadata.get("review_overrides")
        if isinstance(raw, Mapping):
            return cls.from_payload(raw)
        return cls()

    def attach(self, project: Project) -> None:
        project.metadata["review_overrides"] = self.to_payload()


def forced_review(
    request: ReviewRequest,
    action: ReviewAction,
    *,
    reason: str = "human override",
) -> Review:
    return Review(
        target_type=request.target_type,
        target_id=request.target_id,
        attempt=request.attempt,
        scores={},
        issues=[
            ReviewIssue(
                severity="minor",
                message=f"{reason}: {action.value}",
                suggestion="human verdict; models were not called",
            )
        ],
        action=action,
        reviewer=OVERRIDE_REVIEWER,
    )


class OverrideReviewer:
    """Wrap a reviewer and short-circuit when a human verdict is set."""

    name = OVERRIDE_REVIEWER

    def __init__(self, inner: Reviewer, book: OverrideBook | None = None) -> None:
        self.inner = inner
        self.book = book or OverrideBook()

    def review(self, request: ReviewRequest) -> Review:
        action = self.book.lookup(request.target_type, request.target_id)
        if action is not None:
            return forced_review(request, action, reason=self.book.reason)
        return self.inner.review(request)


def resolve_overrides(
    settings: Settings | None = None,
    *,
    project: Project | None = None,
    extra: OverrideBook | None = None,
) -> OverrideBook:
    book = OverrideBook()
    if settings is not None:
        book = book.merge(OverrideBook.from_settings(settings))
    if project is not None:
        book = book.merge(OverrideBook.from_project(project))
    if extra is not None:
        book = book.merge(extra)
    return book

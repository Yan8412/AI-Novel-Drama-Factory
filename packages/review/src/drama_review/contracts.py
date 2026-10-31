"""Reviewer protocol and the request object shared by every review stage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from drama_core import Review, ReviewTargetType

ReviewVerdict = Review


@dataclass(frozen=True)
class ReviewRequest:
    target_type: ReviewTargetType
    target_id: str
    attempt: int
    content: str = ""
    context: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Reviewer(Protocol):
    name: str

    def review(self, request: ReviewRequest) -> Review: ...

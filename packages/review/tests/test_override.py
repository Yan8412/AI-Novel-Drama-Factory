import json
from pathlib import Path

from drama_core import ReviewAction, ReviewTargetType, Settings
from drama_review import DeterministicMockReviewer, OverrideBook, OverrideReviewer, ReviewRequest


def _req(target_id: str = "ch_1", attempt: int = 1) -> ReviewRequest:
    return ReviewRequest(target_type=ReviewTargetType.CHAPTER, target_id=target_id, attempt=attempt)


def test_override_skips_inner_reviewer() -> None:
    inner = DeterministicMockReviewer()
    book = OverrideBook(global_action=ReviewAction.PASS, reason="qa sign-off")
    wrapped = OverrideReviewer(inner, book)
    review = wrapped.review(_req())
    assert review.action is ReviewAction.PASS
    assert review.reviewer == "human-override"
    assert review.attempt == 1
    assert inner.review(_req()).action is ReviewAction.REVISE


def test_override_lookup_order() -> None:
    book = OverrideBook(
        global_action=ReviewAction.PASS,
        by_type={ReviewTargetType.CHAPTER: ReviewAction.REVISE},
        by_id={"clip_x": ReviewAction.REJECT},
    )
    assert book.lookup(ReviewTargetType.CLIP, "clip_x") is ReviewAction.REJECT
    assert book.lookup(ReviewTargetType.CHAPTER, "ch_1") is ReviewAction.REVISE
    assert book.lookup(ReviewTargetType.ASSET, "a") is ReviewAction.PASS


def test_override_file_and_settings(tmp_path: Path) -> None:
    path = tmp_path / "ovr.json"
    path.write_text(
        json.dumps({"global": "pass", "types": {"clip": "revise"}, "targets": {"x": "reject"}}),
        encoding="utf-8",
    )
    book = OverrideBook.from_settings(
        Settings(review_override_file=str(path), review_override="pass")
    )
    assert book.global_action is ReviewAction.PASS
    assert book.lookup(ReviewTargetType.CLIP, "other") is ReviewAction.REVISE
    assert book.lookup(ReviewTargetType.CLIP, "x") is ReviewAction.REJECT

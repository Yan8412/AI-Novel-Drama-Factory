from drama_core import (
    Asset,
    AssetKind,
    Chapter,
    Clip,
    Project,
    Review,
    ReviewAction,
    ReviewIssue,
    ReviewTargetType,
    Storyboard,
)
from drama_review import OverrideBook, list_review_targets, pending_targets, review_desk_payload


def _chapter_project() -> Project:
    project = Project(title="t", genre="都市", premise="p", total_words=3000)
    project.chapters.append(
        Chapter(id="ch_1", index=1, title="开端", body="一二三四五", target_words=3000, revision=1)
    )
    project.storyboards.append(Storyboard(id="sb_1", chapter_id="ch_1", shots=[], revision=0))
    project.assets.append(
        Asset(
            id="asset_1",
            kind=AssetKind.SCENE,
            owner_id="scene_x",
            uri="mock://scene",
            revision=2,
        )
    )
    project.clips.append(
        Clip(
            id="clip_1",
            shot_id="missing",
            source_asset_id="asset_1",
            uri="mock://clip",
            duration_s=8,
            revision=0,
        )
    )
    project.reviews.append(
        Review(
            target_type=ReviewTargetType.CHAPTER,
            target_id="ch_1",
            attempt=2,
            scores={"coherence": 6.0},
            issues=[ReviewIssue(message="节奏偏慢", suggestion="加快开场")],
            action=ReviewAction.REVISE,
            reviewer="mock-deterministic",
        )
    )
    project.reviews.append(
        Review(
            target_type=ReviewTargetType.ASSET,
            target_id="asset_1",
            attempt=1,
            action=ReviewAction.REJECT,
            reviewer="mock-deterministic",
        )
    )
    project.revision_queue = ["ch_1"]
    return project


def test_desk_lists_pending_and_failed() -> None:
    project = _chapter_project()
    desk = review_desk_payload(project)
    assert desk["pending"] == 1
    assert desk["failed"] == 1
    by_id = {row["target_id"]: row for row in desk["targets"]}
    assert by_id["ch_1"]["status"] == "pending"
    assert by_id["ch_1"]["attempts"] == 2
    assert by_id["ch_1"]["revision"] == 1
    assert by_id["ch_1"]["rerun_stage"] == "chapters"
    assert by_id["ch_1"]["label"].startswith("第1章")
    assert by_id["asset_1"]["status"] == "rejected"
    assert by_id["sb_1"]["status"] == "unreviewed"
    assert pending_targets(project)[0]["target_id"] == "ch_1"


def test_desk_exposes_override() -> None:
    project = _chapter_project()
    book = OverrideBook()
    book.set(ReviewAction.PASS, target_id="ch_1", reason="qa")
    book.attach(project)
    row = next(item for item in list_review_targets(project) if item["target_id"] == "ch_1")
    assert row["override"] == "pass"

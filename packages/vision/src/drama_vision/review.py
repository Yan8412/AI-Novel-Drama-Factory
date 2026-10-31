"""Rule checks for asset prompts (9-view / scene multi-view / continuity)."""

from __future__ import annotations

from drama_core import Asset, AssetKind, ReviewIssue

from drama_vision.prompts import NINE_VIEWS, SCENE_VIEWS


def is_mock_placeholder(uri: str) -> bool:
    return uri.startswith("mock://")


def asset_prompt_issues(asset: Asset) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    prompt = asset.prompt or ""
    if not prompt.strip():
        issues.append(
            ReviewIssue(
                severity="major",
                message=f"asset {asset.id} has an empty prompt",
                suggestion="rebuild the structured prompt before rendering",
            )
        )
        return issues
    if asset.kind is AssetKind.CHARACTER_NINE_VIEW:
        missing = [v for v in NINE_VIEWS if v not in asset.views]
        if missing:
            issues.append(
                ReviewIssue(
                    severity="major",
                    message=f"9-view sheet missing views: {', '.join(missing)}",
                    suggestion="emit the full 3x3 turnaround labels",
                )
            )
        if "identity lock" not in prompt.lower() and "identity" not in prompt.lower():
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message="character sheet prompt lacks identity anchors",
                    suggestion="include face / outfit / color palette lock text",
                )
            )
    elif asset.kind is AssetKind.SCENE:
        if not asset.views:
            issues.append(
                ReviewIssue(
                    severity="major",
                    message="scene asset has no multi-view labels",
                    suggestion=f"attach views: {', '.join(SCENE_VIEWS)}",
                )
            )
        if "environment" not in prompt.lower() and "multi" not in prompt.lower():
            issues.append(
                ReviewIssue(
                    severity="minor",
                    message="scene prompt does not read as a multi-view sheet",
                    suggestion="describe angles and time-of-day variants",
                )
            )
    elif asset.kind is AssetKind.PROP and "prop" not in prompt.lower():
        issues.append(
            ReviewIssue(
                severity="minor",
                message="prop prompt missing continuity wording",
                suggestion="label it as a hero prop turnaround",
            )
        )
    return issues

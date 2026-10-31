"""Walks a ``Project`` through the pipeline FSM using pluggable engines.

All state lives on the ``Project`` (stage, revision queue, reviews), so a run can
be persisted between steps and resumed by any worker.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TypeVar

from drama_assemble import Assembler, MockAssembler, write_playbook
from drama_core import (
    TERMINAL_STAGES,
    Asset,
    AssetKind,
    Chapter,
    Character,
    Clip,
    ExportResult,
    PipelineStage,
    Project,
    Prop,
    Review,
    ReviewAction,
    ReviewTargetType,
    Scene,
    Shot,
    StageTransition,
    Storyboard,
    new_id,
    plan_chapter_lengths,
    transition,
)
from drama_novel import (
    NovelEngine,
    NovelMemory,
    chapter_review_request,
    merge_chapter_review,
)
from drama_review import (
    OVERRIDE_REVIEWER,
    OverrideBook,
    PriceBook,
    RetryPolicy,
    Reviewer,
    ReviewRequest,
    budget_payload,
    forced_review,
    record_review,
    record_step,
    resolve_overrides,
)
from drama_storyboard import (
    StoryboardEngine,
    storyboard_review_request,
    storyboard_rule_issues,
    to_markdown,
)
from drama_tts import MockSubtitleEngine, MockTtsEngine, SubtitleEngine, TtsEngine
from drama_video import (
    VideoEngine,
    clip_review_request,
    clip_rule_issues,
    write_video_export,
)
from drama_vision import VisionEngine, asset_prompt_issues, identity_anchors

log = logging.getLogger(__name__)

S = PipelineStage
TransitionListener = Callable[[Project, StageTransition], None]
ReviewListener = Callable[[Project, Review], None]
_Item = TypeVar("_Item", Chapter, Storyboard, Asset, Clip)
_Owned = TypeVar("_Owned", Character, Scene, Prop, Shot)


class PipelineError(RuntimeError):
    pass


class Orchestrator:
    def __init__(
        self,
        *,
        novel: NovelEngine,
        storyboard: StoryboardEngine,
        vision: VisionEngine,
        video: VideoEngine,
        reviewer: Reviewer,
        assembler: Assembler | None = None,
        subtitles: SubtitleEngine | None = None,
        tts: TtsEngine | None = None,
        policy: RetryPolicy | None = None,
        overrides: OverrideBook | None = None,
        output_dir: Path = Path("output"),
        on_transition: TransitionListener | None = None,
        on_review: ReviewListener | None = None,
        prices: PriceBook | None = None,
        deslop_enabled: bool = True,
        deslop_strict: bool = False,
    ) -> None:
        self.novel = novel
        self.storyboard = storyboard
        self.vision = vision
        self.video = video
        self.reviewer = reviewer
        self.assembler = assembler or MockAssembler()
        self.subtitles = subtitles or MockSubtitleEngine()
        self.tts = tts or MockTtsEngine()
        self.policy = policy or RetryPolicy()
        self.overrides = overrides or OverrideBook()
        self.output_dir = output_dir
        self.on_transition = on_transition
        self.on_review = on_review
        self.prices = prices or PriceBook()
        self.deslop_enabled = deslop_enabled
        self.deslop_strict = deslop_strict
        self._handlers: dict[PipelineStage, Callable[[Project], None]] = {
            S.CREATED: self._created,
            S.CHARACTERS: self._characters,
            S.OUTLINE: self._outline,
            S.CHAPTERS: self._chapters,
            S.NOVEL_REVIEW: self._novel_review,
            S.STORYBOARD: self._storyboard,
            S.STORYBOARD_REVIEW: self._storyboard_review,
            S.ASSETS: self._assets,
            S.IMAGE_REVIEW: self._image_review,
            S.VIDEO: self._video,
            S.VIDEO_REVIEW: self._video_review,
            S.EXPORT: self._export,
        }

    # ------------------------------------------------------------------ driver

    def run(self, project: Project, *, max_steps: int = 1000) -> Project:
        self._resume_from_failure(project)
        project.budget.max_retries = self.policy.max_attempts
        run_id = new_id("run")
        project.metadata["last_run_id"] = run_id
        project.metadata["billing"] = self.prices.to_payload()
        project.budget.last_run_id = run_id
        book = resolve_overrides(project=project, extra=self.overrides)
        book.attach(project)
        for _ in range(max_steps):
            if project.stage in TERMINAL_STAGES:
                return project
            self.step(project)
        self._fail(project, f"exceeded max_steps={max_steps}")
        return project

    def step(self, project: Project) -> None:
        if project.stage in TERMINAL_STAGES:
            return
        try:
            self._handlers[project.stage](project)
        except Exception as exc:
            log.exception("stage %s failed", project.stage)
            self._fail(project, f"{project.stage.value}: {type(exc).__name__}: {exc}")

    def _go(self, project: Project, dst: PipelineStage, reason: str = "") -> None:
        record = transition(project, dst, reason)
        if self.on_transition:
            self.on_transition(project, record)

    def _fail(self, project: Project, reason: str) -> None:
        project.failure_reason = reason
        self._go(project, S.FAILED, reason)

    def _resume_from_failure(self, project: Project) -> None:
        """FAILED is terminal in the FSM; human override + re-run jumps back to the last stage."""
        if project.stage is not S.FAILED or not project.stage_history:
            return
        last = project.stage_history[-1]
        if last.to_stage is not S.FAILED:
            return
        rejected: list[str] = []
        if last.reason.startswith("rejected:"):
            rejected = [
                part.strip()
                for part in last.reason.removeprefix("rejected:").split(",")
                if part.strip()
            ]
        project.stage = last.from_stage
        project.failure_reason = None
        if rejected:
            project.revision_queue = rejected

    def _record_step(
        self,
        project: Project,
        *,
        stage: str,
        engine: str,
        engine_obj: object | None = None,
        target_id: str = "",
        attempt: int = 1,
        note: str = "",
    ) -> None:
        record_step(
            project,
            stage=stage,
            engine=engine,
            target_id=target_id,
            attempt=attempt,
            note=note,
            prices=self.prices,
            engine_obj=engine_obj,
        )

    # ------------------------------------------------------------------ novel

    def _created(self, project: Project) -> None:
        self._go(project, S.CHARACTERS, f"genre={project.genre}")

    def _characters(self, project: Project) -> None:
        bible = self.novel.create_bible(project)
        project.characters = bible.characters
        project.scenes = bible.scenes
        project.props = bible.props
        self._go(project, S.OUTLINE, f"{len(bible.characters)} characters")

    def _outline(self, project: Project) -> None:
        targets = plan_chapter_lengths(
            project.total_words, word_min=project.word_min, word_max=project.word_max
        )
        project.outline = self.novel.write_outline(project, targets)
        self._go(project, S.CHAPTERS, f"{len(targets)} chapters planned")

    def _chapters(self, project: Project) -> None:
        if project.revision_queue:
            for i, ch in enumerate(project.chapters):
                if ch.id in project.revision_queue:
                    review = project.reviews_for(ch.id)[-1]
                    memory = self._memory(project, before=ch.index)
                    project.chapters[i] = self.novel.revise_chapter(project, ch, review, memory)
            self._record_step(
                project,
                stage="novel",
                engine=self.novel.name,
                engine_obj=self.novel,
                attempt=2,
                note=f"revised {len(project.revision_queue)} chapters",
            )
            self._go(project, S.NOVEL_REVIEW, f"revised {len(project.revision_queue)} chapters")
            return
        if project.outline is None:
            raise PipelineError("outline missing")
        for plan in project.outline.chapters:
            memory = self._memory(project, before=plan.index)
            project.chapters.append(self.novel.write_chapter(project, plan, memory))
        self._record_step(
            project,
            stage="novel",
            engine=self.novel.name,
            engine_obj=self.novel,
            note=f"wrote {len(project.chapters)} chapters",
        )
        self._go(project, S.NOVEL_REVIEW, f"wrote {len(project.chapters)} chapters")

    def _memory(self, project: Project, *, before: int) -> NovelMemory:
        memory = NovelMemory()
        for ch in sorted(project.chapters, key=lambda c: c.index):
            if ch.index < before:
                memory.apply(ch.index, ch.summary, ch.memory_delta)
        return memory

    def _novel_review(self, project: Project) -> None:
        def extra(review: Review, ch: Chapter) -> Review:
            return merge_chapter_review(
                project,
                ch,
                review,
                deslop_enabled=self.deslop_enabled,
                deslop_strict=self.deslop_strict,
            )

        def request_fn(ch: Chapter) -> ReviewRequest:
            return chapter_review_request(project, ch, self._memory(project, before=ch.index))

        chapters = self._pending(project, project.chapters)
        self._review_round(
            project,
            [
                self._verdict_for(
                    project,
                    ch,
                    target_type=ReviewTargetType.CHAPTER,
                    attempt=ch.revision + 1,
                    request_fn=request_fn,
                    extra_fn=extra,
                )
                for ch in chapters
            ],
            revise_stage=S.CHAPTERS,
            next_stage=S.STORYBOARD,
        )

    # ------------------------------------------------------------------ storyboard + images

    def _storyboard(self, project: Project) -> None:
        if project.revision_queue:
            for i, sb in enumerate(project.storyboards):
                if sb.id in project.revision_queue:
                    chapter = next(c for c in project.chapters if c.id == sb.chapter_id)
                    rebuilt = self.storyboard.build(
                        project,
                        chapter,
                        revision=sb.revision + 1,
                        feedback=_feedback(project.reviews_for(sb.id)),
                    )
                    project.storyboards[i] = rebuilt.model_copy(update={"id": sb.id})
            self._record_step(
                project,
                stage="storyboard",
                engine=self.storyboard.name,
                engine_obj=self.storyboard,
                attempt=2,
                note=f"revised {len(project.revision_queue)} storyboards",
            )
            self._go(
                project, S.STORYBOARD_REVIEW, f"revised {len(project.revision_queue)} storyboards"
            )
            return
        project.storyboards = [self.storyboard.build(project, ch) for ch in project.chapters]
        self._record_step(
            project,
            stage="storyboard",
            engine=self.storyboard.name,
            engine_obj=self.storyboard,
            note=f"{len(project.shots)} shots",
        )
        self._go(project, S.STORYBOARD_REVIEW, f"{len(project.shots)} shots")

    def _storyboard_review(self, project: Project) -> None:
        def extra(review: Review, sb: Storyboard) -> Review:
            issues = [
                i for i in storyboard_rule_issues(project, sb) if i.severity in {"major", "blocker"}
            ]
            if not issues:
                return review
            return review.model_copy(
                update={"issues": [*review.issues, *issues], "action": ReviewAction.REVISE}
            )

        def request_fn(sb: Storyboard) -> ReviewRequest:
            return storyboard_review_request(project, sb)

        boards = self._pending(project, project.storyboards)
        self._review_round(
            project,
            [
                self._verdict_for(
                    project,
                    sb,
                    target_type=ReviewTargetType.STORYBOARD,
                    attempt=sb.revision + 1,
                    request_fn=request_fn,
                    extra_fn=extra,
                )
                for sb in boards
            ],
            revise_stage=S.STORYBOARD,
            next_stage=S.ASSETS,
        )

    def _assets(self, project: Project) -> None:
        if project.revision_queue:
            for i, asset in enumerate(project.assets):
                if asset.id in project.revision_queue:
                    project.assets[i] = self._rerender(project, asset)
            self._record_step(
                project,
                stage="vision",
                engine=self.vision.name,
                engine_obj=self.vision,
                attempt=2,
                note=f"re-rendered {len(project.revision_queue)} assets",
            )
            self._go(project, S.IMAGE_REVIEW, f"re-rendered {len(project.revision_queue)} assets")
            return

        v = self.vision
        for ch in project.characters:
            grid = v.character_nine_view(project, ch)
            project.assets.append(grid)
            ch.visual_lock.nine_view_asset_id = grid.id
            ch.visual_lock.locked = True
            if ch.visual_lock.id_method is None:
                ch.visual_lock.id_method = "sheet"
        for sc in project.scenes:
            img = v.scene_image(project, sc)
            project.assets.append(img)
            sc.reference_asset_id = img.id
        for pr in project.props:
            img = v.prop_image(project, pr)
            project.assets.append(img)
            pr.reference_asset_id = img.id
        for shot in project.shots:
            kf = v.shot_keyframe(
                project, shot, self._references(project, shot.character_ids, shot.scene_id)
            )
            project.assets.append(kf)
            shot.keyframe_asset_id = kf.id
        self._record_step(
            project,
            stage="vision",
            engine=self.vision.name,
            engine_obj=self.vision,
            note=f"rendered {len(project.assets)} assets",
        )
        self._go(project, S.IMAGE_REVIEW, f"rendered {len(project.assets)} assets")

    def _references(
        self, project: Project, character_ids: list[str], scene_id: str | None
    ) -> list[Asset]:
        wanted = {
            c.visual_lock.nine_view_asset_id for c in project.characters if c.id in character_ids
        }
        wanted |= {s.reference_asset_id for s in project.scenes if s.id == scene_id}
        return [a for a in project.assets if a.id in wanted]

    def _rerender(self, project: Project, asset: Asset) -> Asset:
        rev = asset.revision + 1
        fb = _feedback(project.reviews_for(asset.id))
        v = self.vision
        match asset.kind:
            case AssetKind.CHARACTER_NINE_VIEW:
                char = _by_id(project.characters, asset.owner_id)
                new = v.character_nine_view(project, char, revision=rev, feedback=fb)
            case AssetKind.SCENE:
                new = v.scene_image(
                    project, _by_id(project.scenes, asset.owner_id), revision=rev, feedback=fb
                )
            case AssetKind.PROP:
                new = v.prop_image(
                    project, _by_id(project.props, asset.owner_id), revision=rev, feedback=fb
                )
            case AssetKind.SHOT_KEYFRAME:
                shot = _by_id(project.shots, asset.owner_id)
                refs = self._references(project, shot.character_ids, shot.scene_id)
                new = v.shot_keyframe(project, shot, refs, revision=rev, feedback=fb)
        # Keep the id stable so reviews and references follow the asset across revisions.
        return new.model_copy(update={"id": asset.id})

    def _image_review(self, project: Project) -> None:
        def extra(review: Review, asset: Asset) -> Review:
            issues = [i for i in asset_prompt_issues(asset) if i.severity in {"major", "blocker"}]
            if not issues:
                return review
            return review.model_copy(
                update={"issues": [*review.issues, *issues], "action": ReviewAction.REVISE}
            )

        def request_fn(asset: Asset) -> ReviewRequest:
            return ReviewRequest(
                target_type=ReviewTargetType.ASSET,
                target_id=asset.id,
                attempt=asset.revision + 1,
                content=asset.uri,
                context={"kind": asset.kind.value, "prompt": asset.prompt},
            )

        assets = self._pending(project, project.assets)
        self._review_round(
            project,
            [
                self._verdict_for(
                    project,
                    a,
                    target_type=ReviewTargetType.ASSET,
                    attempt=a.revision + 1,
                    request_fn=request_fn,
                    extra_fn=extra,
                )
                for a in assets
            ],
            revise_stage=S.ASSETS,
            next_stage=S.VIDEO,
        )

    # ------------------------------------------------------------------ video

    def _video(self, project: Project) -> None:
        assets = {a.id: a for a in project.assets}
        shots = {s.id: s for s in project.shots}
        if project.revision_queue:
            for i, clip in enumerate(project.clips):
                if clip.id in project.revision_queue:
                    shot = shots[clip.shot_id]
                    new = self.video.image_to_video(
                        project,
                        shot,
                        assets[clip.source_asset_id],
                        revision=clip.revision + 1,
                        feedback=_feedback(project.reviews_for(clip.id)),
                        previous_clip=self._previous_clip(project, shot),
                        identity_refs=self._shot_identity_refs(project, shot),
                    )
                    project.clips[i] = new.model_copy(update={"id": clip.id})
            self._record_step(
                project,
                stage="video",
                engine=self.video.name,
                engine_obj=self.video,
                attempt=2,
                note=f"re-generated {len(project.revision_queue)} clips",
            )
            self._go(project, S.VIDEO_REVIEW, f"re-generated {len(project.revision_queue)} clips")
            return
        previous: Clip | None = None
        for shot in project.shots:
            if shot.keyframe_asset_id is None:
                raise PipelineError(f"shot {shot.id} has no keyframe")
            clip = self.video.image_to_video(
                project,
                shot,
                assets[shot.keyframe_asset_id],
                previous_clip=previous,
                identity_refs=self._shot_identity_refs(project, shot),
            )
            project.clips.append(clip)
            previous = clip
        self._record_step(
            project,
            stage="video",
            engine=self.video.name,
            engine_obj=self.video,
            note=f"generated {len(project.clips)} clips",
        )
        self._go(project, S.VIDEO_REVIEW, f"generated {len(project.clips)} clips")

    def _shot_identity_refs(self, project: Project, shot: Shot) -> list[Asset]:
        refs = self._references(project, shot.character_ids, shot.scene_id)
        wanted_props = set(shot.prop_ids)
        refs.extend(
            a
            for a in project.assets
            if a.kind is AssetKind.PROP and a.owner_id in wanted_props and a not in refs
        )
        return refs

    def _previous_clip(self, project: Project, shot: Shot) -> Clip | None:
        ordered = list(project.shots)
        idx = next((i for i, s in enumerate(ordered) if s.id == shot.id), -1)
        if idx <= 0:
            return None
        prev_id = ordered[idx - 1].id
        return next((c for c in project.clips if c.shot_id == prev_id), None)

    def _video_review(self, project: Project) -> None:
        def extra(review: Review, clip: Clip) -> Review:
            issues = [
                i for i in clip_rule_issues(project, clip) if i.severity in {"major", "blocker"}
            ]
            if not issues:
                return review
            return review.model_copy(
                update={"issues": [*review.issues, *issues], "action": ReviewAction.REVISE}
            )

        def request_fn(clip: Clip) -> ReviewRequest:
            return clip_review_request(project, clip)

        clips = self._pending(project, project.clips)
        self._review_round(
            project,
            [
                self._verdict_for(
                    project,
                    c,
                    target_type=ReviewTargetType.CLIP,
                    attempt=c.revision + 1,
                    request_fn=request_fn,
                    extra_fn=extra,
                )
                for c in clips
            ],
            revise_stage=S.VIDEO,
            next_stage=S.EXPORT,
        )

    # ------------------------------------------------------------------ export

    def _export(self, project: Project) -> None:
        out = self.output_dir / project.id
        (out / "storyboards").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(parents=True, exist_ok=True)
        self._memory(project, before=10**9).save(out)
        _write_asset_sheets(out / "assets", project)
        videos_manifest = write_video_export(out, project)
        chapter_index = {c.id: c.index for c in project.chapters}
        for sb in project.storyboards:
            idx = chapter_index[sb.chapter_id]
            (out / "storyboards" / f"chapter_{idx:03d}.md").write_text(
                to_markdown(project, sb), encoding="utf-8"
            )
        clips_by_shot = {c.shot_id: c for c in project.clips}
        clip_paths = {
            rec["clip_id"]: rec.get("path")
            for rec in json.loads(videos_manifest.read_text(encoding="utf-8")).get("clips", [])
        }
        timeline: list[dict[str, object]] = [
            {
                "chapter": chapter_index[s.chapter_id],
                "shot": s.index,
                "clip_id": clips_by_shot[s.id].id,
                "uri": clips_by_shot[s.id].uri,
                "path": clip_paths.get(clips_by_shot[s.id].id),
                "duration_s": clips_by_shot[s.id].duration_s,
                "previous_clip_id": clips_by_shot[s.id].previous_clip_id,
            }
            for s in project.shots
        ]
        subtitle_paths = self.subtitles.write_track(project, project.shots, out_dir=out)
        tts_paths = self.tts.synthesize(project, project.shots, out_dir=out)
        self._record_step(
            project,
            stage="tts",
            engine=self.tts.name,
            engine_obj=self.tts,
            note=f"{len(tts_paths)} cues" if tts_paths else "off",
        )
        episodes = self.assembler.assemble(project, out_dir=out, timeline=timeline)
        subtitle_rel = None
        if subtitle_paths:
            subtitle_rel = str(subtitle_paths[0].relative_to(out))
            for episode in episodes:
                episode.subtitle_path = subtitle_rel
            write_playbook(
                out / "episode",
                concat_full=out / "episode" / "concat_full.txt",
                episode_full=out / "episode" / "full.mp4",
                subtitle=subtitle_paths[0],
            )
        project.episodes = episodes
        self._record_step(
            project,
            stage="assemble",
            engine=self.assembler.name,
            engine_obj=self.assembler,
            note=f"{len(episodes)} episode packages",
        )
        budget_path = out / "budget.json"
        budget_path.write_text(
            json.dumps(budget_payload(project), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        manifest = {
            "project_id": project.id,
            "title": project.title,
            "aspect_ratio": project.aspect_ratio,
            "resolution": [project.width, project.height],
            "timeline": timeline,
            "episodes": [
                {
                    "id": e.id,
                    "kind": e.kind.value,
                    "title": e.title,
                    "path": e.path,
                    "concat_path": e.concat_path,
                    "subtitle_path": e.subtitle_path,
                    "duration_s": e.duration_s,
                    "clip_ids": e.clip_ids,
                }
                for e in episodes
            ],
            "subtitles": [str(p.relative_to(out)) for p in subtitle_paths],
            "reviews": {
                t.value: sum(1 for r in project.reviews if r.target_type is t)
                for t in ReviewTargetType
            },
            "budget": {
                "max_retries": project.budget.max_retries,
                "estimated_usd": project.budget.estimated_usd,
                "estimated_cny": project.budget.estimated_cny,
                "recorded_usd": project.budget.recorded_usd,
                "units": {
                    "tokens": project.budget.tokens,
                    "images": project.budget.images,
                    "video_seconds": project.budget.video_seconds,
                    "tts_chars": project.budget.tts_chars,
                },
                "layers": project.budget.layer_counts(),
            },
        }
        manifest_path = out / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        project.export = ExportResult(
            output_dir=str(out),
            manifest_path=str(manifest_path),
            clip_count=len(timeline),
            total_duration_s=sum(c.duration_s for c in project.clips),
            episode_count=len(episodes),
            episode_dir=str(out / "episode"),
            concat_path=str(out / "episode" / "concat_full.txt"),
            subtitle_path=str(out / subtitle_rel) if subtitle_rel else None,
            budget_path=str(budget_path),
        )
        self._go(project, S.DONE, f"exported {len(timeline)} clips / {len(episodes)} episodes")
        (out / "project.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ review plumbing

    @staticmethod
    def _pending(project: Project, items: list[_Item]) -> list[_Item]:
        if not project.revision_queue:
            return list(items)
        return [x for x in items if x.id in project.revision_queue]

    def _verdict_for(
        self,
        project: Project,
        item: _Item,
        *,
        target_type: ReviewTargetType,
        attempt: int,
        request_fn: Callable[[_Item], ReviewRequest],
        extra_fn: Callable[[Review, _Item], Review] | None = None,
    ) -> tuple[str, Review]:
        def request() -> ReviewRequest:
            return request_fn(item)

        def extra(review: Review) -> Review:
            assert extra_fn is not None
            return extra_fn(review, item)

        return item.id, self._verdict(
            project,
            target_type=target_type,
            target_id=item.id,
            attempt=attempt,
            request=request,
            extra=extra if extra_fn is not None else None,
        )

    def _verdict(
        self,
        project: Project,
        *,
        target_type: ReviewTargetType,
        target_id: str,
        attempt: int,
        request: Callable[[], ReviewRequest],
        extra: Callable[[Review], Review] | None = None,
    ) -> Review:
        book = resolve_overrides(project=project, extra=self.overrides)
        forced = book.lookup(target_type, target_id)
        if forced is not None:
            review = forced_review(
                ReviewRequest(target_type=target_type, target_id=target_id, attempt=attempt),
                forced,
                reason=book.reason,
            )
        else:
            review = self.reviewer.review(request())
            if extra is not None:
                review = extra(review)
        record_review(
            project,
            review,
            engine=review.reviewer,
            prices=self.prices,
            engine_obj=None if forced is not None else self.reviewer,
        )
        return review

    def _review_round(
        self,
        project: Project,
        raw: Iterable[tuple[str, Review]],
        *,
        revise_stage: PipelineStage,
        next_stage: PipelineStage,
    ) -> None:
        revise: list[str] = []
        rejected: list[str] = []
        for target_id, review in raw:
            verdict = (
                review if review.reviewer == OVERRIDE_REVIEWER else self.policy.resolve(review)
            )
            project.reviews.append(verdict)
            if self.on_review:
                self.on_review(project, verdict)
            if verdict.action is ReviewAction.REVISE:
                revise.append(target_id)
            elif verdict.action is ReviewAction.REJECT:
                rejected.append(target_id)
        if rejected:
            project.revision_queue = []
            self._fail(project, f"rejected: {', '.join(rejected)}")
        elif revise:
            project.revision_queue = revise
            self._go(project, revise_stage, f"{len(revise)} need revision")
        else:
            project.revision_queue = []
            self._go(project, next_stage, "all passed")


def _feedback(reviews: list[Review]) -> str:
    chunks: list[str] = []
    for review in reviews:
        bits = [i.suggestion or i.message for i in review.issues if i.suggestion or i.message]
        if bits:
            chunks.append(f"attempt {review.attempt} ({review.action.value}): " + "; ".join(bits))
    return " | ".join(chunks)


def _by_id(items: list[_Owned], target_id: str) -> _Owned:
    for x in items:
        if getattr(x, "id", None) == target_id:
            return x
    raise PipelineError(f"id {target_id} not found")


def _write_asset_sheets(folder: Path, project: Project) -> None:
    chars = {c.id: c for c in project.characters}
    scenes = {s.id: s for s in project.scenes}
    props = {p.id: p for p in project.props}
    for asset in project.assets:
        if asset.kind is AssetKind.SHOT_KEYFRAME:
            continue
        title = asset.owner_id
        extra = ""
        if asset.kind is AssetKind.CHARACTER_NINE_VIEW and asset.owner_id in chars:
            char = chars[asset.owner_id]
            title = char.name
            extra = identity_anchors(char).as_prompt_block()
        elif asset.kind is AssetKind.SCENE and asset.owner_id in scenes:
            title = scenes[asset.owner_id].name
        elif asset.kind is AssetKind.PROP and asset.owner_id in props:
            title = props[asset.owner_id].name
        slug = "".join(ch if ch.isalnum() else "_" for ch in title) or asset.id
        body = [
            f"# {asset.kind.value} · {title}",
            "",
            f"- uri: {asset.uri}",
            f"- engine: {asset.engine}",
            f"- views: {', '.join(asset.views) or '（无）'}",
            "",
            "## Prompt",
            "",
            asset.prompt or "（空）",
            "",
        ]
        if extra:
            body.extend(["## Identity anchors", "", extra, ""])
        (folder / f"{asset.kind.value}_{slug}.md").write_text("\n".join(body), encoding="utf-8")

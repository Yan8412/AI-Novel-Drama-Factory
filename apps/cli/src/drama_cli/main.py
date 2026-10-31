"""`drama-factory demo`: run the full mock pipeline and print each stage hop."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from drama_core import PipelineStage, Project, Review, Settings, StageTransition
from drama_pipeline import build_orchestrator
from drama_review.override import OverrideBook
from drama_review.override import parse_action as parse_override_action


def _print_transition(_: Project, t: StageTransition) -> None:
    print(f"  [{t.from_stage.value:>12}] -> [{t.to_stage.value:<12}] {t.reason}")


def _print_review(_: Project, r: Review) -> None:
    print(
        f"      review {r.target_type.value:<7} {r.target_id} attempt={r.attempt} "
        f"score={r.mean_score:.1f} -> {r.action.value}"
    )


def _demo(args: argparse.Namespace) -> int:
    updates: dict[str, object] = {"output_dir": Path(args.out)}
    if args.override_file:
        updates["review_override_file"] = args.override_file
    if args.override_verdict:
        updates["review_override"] = args.override_verdict
    settings = Settings.from_env().model_copy(update=updates)
    book = OverrideBook.from_settings(settings)
    if args.override_verdict:
        book.global_action = parse_override_action(args.override_verdict)
    orchestrator = build_orchestrator(
        settings,
        on_transition=_print_transition,
        on_review=_print_review if args.verbose else None,
        overrides=book,
    )
    project = Project(
        title=args.title, genre=args.genre, premise=args.premise, total_words=args.total_words
    )
    print(f"项目 {project.id}《{project.title}》 total_words={project.total_words}")
    print(
        f"引擎: NOVEL_ENGINE={settings.novel_engine} REVIEW_ENGINE={settings.review_engine} "
        f"STORYBOARD_ENGINE={settings.storyboard_engine} VISION_ENGINE={settings.vision_engine} "
        f"VIDEO_ENGINE={settings.video_engine} ASSEMBLE_ENGINE={settings.assemble_engine} "
        f"TTS_ENGINE={settings.tts_engine}"
    )
    if book.global_action or book.by_id or book.by_type:
        print(f"人工覆盖: {book.to_payload()}")
    orchestrator.run(project)

    if project.stage is not PipelineStage.DONE or project.export is None:
        print(f"FAILED: {project.failure_reason}", file=sys.stderr)
        return 1
    print(
        f"\n完成: {len(project.chapters)} 章 / {len(project.shots)} 镜头 / "
        f"{len(project.reviews)} 条审核记录 / {len(project.episodes)} 集 / "
        f"总时长 {project.export.total_duration_s:g}s"
    )
    print(f"导出目录: {project.export.output_dir}")
    if project.export.concat_path:
        print(f"拼接清单: {project.export.concat_path}")
    if project.export.subtitle_path:
        print(f"字幕: {project.export.subtitle_path}")
    if project.export.budget_path:
        print(f"成本/重试账本: {project.export.budget_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="drama-factory", description="AI 小说 → 竖屏短剧 工厂")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="跑完整流水线（默认 mock；可用环境变量切换引擎）")
    demo.add_argument("--title", default="契约新娘的反击")
    demo.add_argument("--genre", default="都市甜宠")
    demo.add_argument(
        "--premise", default="落魄设计师与冷面总裁签下一年契约婚姻，却牵出二十年前的旧案"
    )
    demo.add_argument("--total-words", type=int, default=12000)
    demo.add_argument("--out", default=str(Settings.from_env().output_dir))
    demo.add_argument("-v", "--verbose", action="store_true", help="打印每条审核记录")
    demo.add_argument(
        "--override-verdict",
        choices=("pass", "revise", "reject"),
        help="强制全部审核结论，不跑模型（pass|revise|reject）",
    )
    demo.add_argument(
        "--override-file",
        help="JSON 覆盖文件：{global, types, targets} → pass|revise|reject",
    )
    demo.set_defaults(func=_demo)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())

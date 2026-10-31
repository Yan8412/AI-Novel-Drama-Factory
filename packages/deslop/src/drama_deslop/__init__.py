"""Anti-AI-flavor helpers shared by novel, storyboard, and prompt builders."""

from drama_deslop.constraints import (
    NO_BURNED_IN_TEXT,
    NO_REDISCRIBE,
    ONE_MOTION,
    SHARED_NEGATIVES,
    has_identity_refs,
    prompt_constraint_issues,
    prompt_guardrails,
)
from drama_deslop.continuity import (
    ContinuityLock,
    apply_continuity,
    build_continuity_lock,
    lock_from_shot,
    multi_action_markers,
    primary_action_of,
)
from drama_deslop.lexicon import LEXICON, SOURCES, lexicon_catalog
from drama_deslop.rewrite import (
    ARCHITECTURE_PASS,
    CHAPTER_CHECKLIST,
    DISCOURSE_PASS,
    WORDING_PASS,
    novel_deslop_system_suffix,
    novel_deslop_user_reminder,
    storyboard_deslop_system_suffix,
)
from drama_deslop.scan import ScanHit, ScanReport, scan_text

__all__ = [
    "ARCHITECTURE_PASS",
    "CHAPTER_CHECKLIST",
    "DISCOURSE_PASS",
    "LEXICON",
    "NO_BURNED_IN_TEXT",
    "NO_REDISCRIBE",
    "ONE_MOTION",
    "SHARED_NEGATIVES",
    "SOURCES",
    "WORDING_PASS",
    "ContinuityLock",
    "ScanHit",
    "ScanReport",
    "apply_continuity",
    "build_continuity_lock",
    "has_identity_refs",
    "lexicon_catalog",
    "lock_from_shot",
    "multi_action_markers",
    "novel_deslop_system_suffix",
    "novel_deslop_user_reminder",
    "primary_action_of",
    "prompt_constraint_issues",
    "prompt_guardrails",
    "scan_text",
    "storyboard_deslop_system_suffix",
]

"""Short-drama (9:16) shot-density planning — not feature-film coverage."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from drama_core import count_words
from drama_core.models import SHOT_MAX_SECONDS, SHOT_MIN_SECONDS

# One 5–15s vertical beat should carry a scene, not a chapter.
WORDS_PER_SHOT_MIN = 250
WORDS_PER_SHOT_MAX = 800
WORDS_PER_SHOT_TARGET = 500
SHOTS_PER_CHAPTER_MIN = 2
SHOTS_PER_CHAPTER_MAX = 10
TARGET_SHOT_SECONDS = 8.0

# Do not split on 。 that sits inside “……” — keep the quoted line intact.
_SENTENCE_SPLIT = re.compile(r"(?<=[。！？…])(?![”\"])|(?<=[。！？…][”\"])|(?<=\n)")
_DIALOGUE = re.compile(r"[“\"]([^”\"]+)[”\"]")


@dataclass(frozen=True)
class Beat:
    text: str
    word_count: int
    dialogue: str = ""


def plan_shot_count(word_count: int) -> int:
    """How many 5–15s vertical shots a chapter of ``word_count`` should become."""
    if word_count <= 0:
        return SHOTS_PER_CHAPTER_MIN
    lo = max(SHOTS_PER_CHAPTER_MIN, math.ceil(word_count / WORDS_PER_SHOT_MAX))
    hi = min(SHOTS_PER_CHAPTER_MAX, max(SHOTS_PER_CHAPTER_MIN, word_count // WORDS_PER_SHOT_MIN))
    if lo > hi:
        return min(max(lo, SHOTS_PER_CHAPTER_MIN), SHOTS_PER_CHAPTER_MAX)
    return min(max(round(word_count / WORDS_PER_SHOT_TARGET), lo), hi)


def plan_duration(beat_words: int) -> float:
    """Map packed-beat size onto the legal 5–15s window (half-second steps)."""
    raw = SHOT_MIN_SECONDS + (max(beat_words, 0) / WORDS_PER_SHOT_MAX) * (
        TARGET_SHOT_SECONDS - SHOT_MIN_SECONDS + 4.0
    )
    snapped = round(raw * 2) / 2
    return min(SHOT_MAX_SECONDS, max(SHOT_MIN_SECONDS, snapped))


def split_beats(body: str) -> list[Beat]:
    """Split chapter prose into dialogue/action beats (Chinese-first)."""
    chunks = [part.strip() for part in _SENTENCE_SPLIT.split(body) if part and part.strip()]
    if not chunks and body.strip():
        chunks = [body.strip()]
    quoted = [f"“{text}”" for text in _DIALOGUE.findall(body)]
    beats: list[Beat] = []
    for chunk in chunks:
        found = _DIALOGUE.findall(chunk)
        dialogue = f"“{found[-1]}”" if found else next((q for q in quoted if q[1:-1] in chunk), "")
        beats.append(Beat(text=chunk, word_count=count_words(chunk), dialogue=dialogue))
    return beats


def cluster_beats(beats: list[Beat], shot_count: int) -> list[list[Beat]]:
    """Pack beats into ``shot_count`` groups with roughly even word counts."""
    if shot_count < 1:
        raise ValueError("shot_count must be >= 1")
    if not beats:
        return [[] for _ in range(shot_count)]
    if len(beats) <= shot_count:
        groups: list[list[Beat]] = [[b] for b in beats]
        while len(groups) < shot_count:
            groups.append([beats[-1]])
        return groups

    total = sum(b.word_count for b in beats) or len(beats)
    target = max(1, total / shot_count)
    groups = []
    current: list[Beat] = []
    acc = 0
    for i, beat in enumerate(beats):
        current.append(beat)
        acc += beat.word_count or 1
        remaining_after = len(beats) - (i + 1)
        need_more_groups = shot_count - len(groups) - 1
        if need_more_groups <= 0:
            continue
        # Close early if leftover beats must seed the remaining shots,
        # even when this group is still under the word-count target.
        must_reserve = remaining_after <= need_more_groups
        if remaining_after >= need_more_groups and (acc >= target or must_reserve):
            groups.append(current)
            current = []
            acc = 0
    if current:
        groups.append(current)
    while len(groups) < shot_count:
        groups.append([beats[-1]])
    return groups[:shot_count]


def words_per_shot(word_count: int, shot_count: int) -> float:
    if shot_count <= 0:
        return 0.0
    return word_count / shot_count

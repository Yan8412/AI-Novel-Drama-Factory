import math

DEFAULT_WORD_MIN = 2500
DEFAULT_WORD_MAX = 5000
DEFAULT_WORD_TARGET = 3500


def plan_chapter_lengths(
    total_words: int,
    *,
    word_min: int = DEFAULT_WORD_MIN,
    word_max: int = DEFAULT_WORD_MAX,
    target: int = DEFAULT_WORD_TARGET,
) -> list[int]:
    """Split ``total_words`` into per-chapter targets, each within ``[word_min, word_max]``.

    Picks the chapter count whose average length is closest to ``target`` while
    keeping every chapter inside the bounds, then distributes the remainder so
    chapter lengths differ by at most one word.
    """
    if word_min <= 0 or word_max < word_min:
        raise ValueError(f"invalid bounds: word_min={word_min}, word_max={word_max}")
    if total_words < word_min:
        raise ValueError(
            f"total_words={total_words} is below a single chapter's word_min={word_min}"
        )

    lo = math.ceil(total_words / word_max)
    hi = total_words // word_min
    if lo > hi:
        raise ValueError(
            f"total_words={total_words} cannot be split into {word_min}-{word_max} word chapters"
        )
    target = min(max(target, word_min), word_max)
    count = min(max(round(total_words / target), lo), hi)

    base, remainder = divmod(total_words, count)
    return [base + 1 if i < remainder else base for i in range(count)]

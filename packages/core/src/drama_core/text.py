import re

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002ffff]")
_LATIN_WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")


def count_words(text: str) -> int:
    """Chinese-first word count: each CJK character counts as one, each Latin token as one.

    Punctuation and whitespace are not counted, matching how Chinese web-novel
    platforms report 字数.
    """
    cjk = len(_CJK.findall(text))
    latin = len(_LATIN_WORD.findall(_CJK.sub(" ", text)))
    return cjk + latin

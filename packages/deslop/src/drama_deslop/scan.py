"""Deterministic deslop scan: density / cluster counts with quoted evidence.

Does not emit an AI-probability or author-identity score. A single isolated
hit is not treated as a defect when the rule limit is at least 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from drama_core import ReviewIssue, count_words

from drama_deslop.lexicon import LEXICON, LexiconRule

_HEAD_CHARS = 180
_TAIL_CHARS = 240
_DENSITY_MIN_WORDS = 200


@dataclass(frozen=True)
class ScanHit:
    rule_id: str
    label: str
    term: str
    count: int
    severity: str
    mode: str
    limit: float
    over_limit: bool
    evidence: tuple[str, ...]
    suggestion: str

    def to_payload(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "label": self.label,
            "term": self.term,
            "count": self.count,
            "severity": self.severity,
            "mode": self.mode,
            "limit": self.limit,
            "over_limit": self.over_limit,
            "evidence": list(self.evidence),
            "suggestion": self.suggestion,
        }


@dataclass
class ScanReport:
    title: str = ""
    word_count: int = 0
    grade: str = "clean"
    banned_per_1k: float = 0.0
    hits: list[ScanHit] = field(default_factory=list)

    @property
    def over_limit(self) -> bool:
        return any(hit.over_limit and hit.severity == "hard" for hit in self.hits)

    def to_payload(self) -> dict[str, object]:
        return {
            "title": self.title,
            "word_count": self.word_count,
            "grade": self.grade,
            "banned_per_1k": self.banned_per_1k,
            "over_limit": self.over_limit,
            "hits": [hit.to_payload() for hit in self.hits],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# 去AI味扫描{f' · {self.title}' if self.title else ''}",
            "",
            f"字数：{self.word_count}  分档：{self.grade}  禁语/千字：{self.banned_per_1k}",
            f"超标硬项：{'是' if self.over_limit else '否'}（单次命中不成证据）",
            "",
        ]
        if not self.hits:
            lines.append("未发现成簇表面层命中。")
            return "\n".join(lines) + "\n"
        lines.extend(
            [
                "| 规则 | 词 | 次数 | 超标 | 证据 |",
                "|---|---|---|---|---|",
            ]
        )
        for hit in self.hits:
            evidence = " / ".join(hit.evidence) if hit.evidence else "—"
            flag = "yes" if hit.over_limit else ""
            lines.append(f"| {hit.rule_id} | {hit.term} | {hit.count} | {flag} | {evidence} |")
        return "\n".join(lines) + "\n"

    def as_review_issues(self) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []
        for hit in self.hits:
            if not hit.over_limit:
                continue
            snippet = hit.evidence[0] if hit.evidence else hit.term
            severity = "minor"
            if hit.severity == "hard":
                severity = "blocker" if hit.limit == 0 else "major"
            issues.append(
                ReviewIssue(
                    severity=severity,
                    message=(
                        f"deslop {hit.rule_id}: {hit.term} x{hit.count} "
                        f"(mode={hit.mode} limit={hit.limit:g}) evidence={snippet}"
                    ),
                    suggestion=hit.suggestion,
                )
            )
        return issues


def scan_text(text: str, *, title: str = "") -> ScanReport:
    words = count_words(text)
    hits: list[ScanHit] = []
    banned_hits = 0
    for rule in LEXICON:
        scoped = _scope_text(text, rule.scope)
        hits.extend(_apply_rule(rule, scoped, words))
        if rule.severity == "hard":
            banned_hits += _rule_raw_count(rule, scoped)
    per_1k = round(banned_hits / max(words / 1000.0, 0.001), 2)
    return ScanReport(
        title=title,
        word_count=words,
        grade=_grade(per_1k, banned_hits),
        banned_per_1k=per_1k,
        hits=hits,
    )


def _grade(per_1k: float, banned_hits: int) -> str:
    if banned_hits == 0:
        return "clean"
    if per_1k <= 5:
        return "light"
    if per_1k <= 15:
        return "mid"
    return "heavy"


def _scope_text(text: str, scope: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if scope == "head":
        return stripped[:_HEAD_CHARS]
    if scope == "tail":
        return stripped[-_TAIL_CHARS:]
    return stripped


def _apply_rule(rule: LexiconRule, text: str, words: int) -> list[ScanHit]:
    if not text:
        return []
    counted = [(term, _count_term(text, term, regex=rule.regex)) for term in rule.terms]
    detailed = [(term, count, _evidence(text, term, regex=rule.regex)) for term, count in counted]
    live = [(term, count, evidence) for term, count, evidence in detailed if count]
    if not live:
        return []

    if rule.mode == "each":
        return [
            ScanHit(
                rule_id=rule.id,
                label=rule.label,
                term=term,
                count=count,
                severity=rule.severity,
                mode=rule.mode,
                limit=rule.limit,
                over_limit=count > rule.limit,
                evidence=evidence,
                suggestion=rule.suggestion,
            )
            for term, count, evidence in live
        ]

    total = sum(count for _, count, _ in live)
    evidence = tuple(item for _, _, ev in live for item in ev)[:4]
    terms = " / ".join(term for term, _, _ in live)
    over = _density_over(total, words, rule.limit) if rule.mode == "density" else total > rule.limit
    return [
        ScanHit(
            rule_id=rule.id,
            label=rule.label,
            term=terms,
            count=total,
            severity=rule.severity,
            mode=rule.mode,
            limit=rule.limit,
            over_limit=over,
            evidence=evidence,
            suggestion=rule.suggestion,
        )
    ]


def _rule_raw_count(rule: LexiconRule, text: str) -> int:
    return sum(_count_term(text, term, regex=rule.regex) for term in rule.terms)


def _density_over(count: int, words: int, limit: float) -> bool:
    if words < _DENSITY_MIN_WORDS:
        return count > limit
    return (count / (words / 1000.0)) > limit


def _count_term(text: str, term: str, *, regex: bool) -> int:
    if regex:
        return len(re.findall(term, text))
    if not term:
        return 0
    return text.count(term)


def _evidence(text: str, term: str, *, regex: bool, limit: int = 3) -> tuple[str, ...]:
    snippets: list[str] = []
    if regex:
        for match in re.finditer(term, text):
            snippets.append(_window(text, match.start(), match.end()))
            if len(snippets) >= limit:
                break
        return tuple(snippets)
    start = 0
    while len(snippets) < limit:
        index = text.find(term, start)
        if index < 0:
            break
        snippets.append(_window(text, index, index + len(term)))
        start = index + max(len(term), 1)
    return tuple(snippets)


def _window(text: str, start: int, end: int, radius: int = 12) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return text[lo:hi].replace("\n", " ")

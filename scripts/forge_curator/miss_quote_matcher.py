"""Detect likely narrative quote spans for miss rolls."""

from __future__ import annotations

import re
from dataclasses import dataclass

from scripts.forge_curator.evidence_scorer import score_paragraph


MISS_WINDOW_BEFORE = 800
MISS_WINDOW_AFTER = 6500

_MISS_LANGUAGE = re.compile(
    r"(?i)\b(?:miss(?:ed|es|ing)?|fail(?:ed|s|ing)?|pass(?:ed|es|ing)?|"
    r"fl(?:y|ew|ies|ying)|sw(?:u|i)ng(?:ing)?)\b|"
    r"\b(?:mov(?:e|ed|es|ing)|drift(?:ed|s|ing)?)\s+(?:by|past|on)\b|"
    r"without\s+a\s+connection|"
    r"no\s+connection|connection\s+(?:was\s+)?missed|"
    r"missed\s+(?:a\s+)?connection"
)


@dataclass(frozen=True)
class MissQuoteVariant:
    text: str
    char_start: int
    char_end: int
    word_index: int
    label: str


@dataclass(frozen=True)
class MissQuoteCandidate:
    text: str
    char_start: int
    char_end: int
    word_index: int
    score: int
    reason_tags: tuple[str, ...]
    variants: tuple[MissQuoteVariant, ...] = ()


@dataclass(frozen=True)
class _SentenceSpan:
    text: str
    char_start: int
    char_end: int
    word_index: int
    paragraph_text: str
    sentence_text: str | None = None
    sentence_char_start: int | None = None
    sentence_char_end: int | None = None


def find_miss_quote_candidates(
    text: str,
    word_offsets: list[tuple[int, int]],
    *,
    constellation: str,
    anchor_word_index: int,
    window_before: int = MISS_WINDOW_BEFORE,
    window_after: int = MISS_WINDOW_AFTER,
) -> list[MissQuoteCandidate]:
    """Return ranked sentence spans that look like miss evidence."""
    constellation_pattern = _constellation_pattern(constellation)
    if constellation_pattern is None:
        return []
    lower_bound = max(0, int(anchor_word_index) - int(window_before))
    upper_bound = int(anchor_word_index) + int(window_after)
    candidates = _collect_candidates(
        text,
        word_offsets,
        constellation_pattern=constellation_pattern,
        anchor_word_index=int(anchor_word_index),
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        include_adjacent=False,
    )
    if not candidates:
        candidates = _collect_candidates(
            text,
            word_offsets,
            constellation_pattern=constellation_pattern,
            anchor_word_index=int(anchor_word_index),
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            include_adjacent=True,
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            abs(candidate.word_index - int(anchor_word_index)),
            candidate.word_index,
        ),
    )


def _collect_candidates(
    text: str,
    word_offsets: list[tuple[int, int]],
    *,
    constellation_pattern: re.Pattern[str],
    anchor_word_index: int,
    lower_bound: int,
    upper_bound: int,
    include_adjacent: bool,
) -> list[MissQuoteCandidate]:
    candidates: list[MissQuoteCandidate] = []
    seen: set[tuple[int, int]] = set()
    for span in _sentence_and_adjacent_spans(
        text, word_offsets, include_adjacent=include_adjacent
    ):
        if span.word_index < lower_bound or span.word_index > upper_bound:
            continue
        if (span.char_start, span.char_end) in seen:
            continue
        if not constellation_pattern.search(span.text):
            continue
        if not _MISS_LANGUAGE.search(span.text):
            continue
        seen.add((span.char_start, span.char_end))
        distance = span.word_index - int(anchor_word_index)
        paragraph_score, _terms = score_paragraph(span.paragraph_text)
        reasons = ["constellation", "miss_language"]
        if paragraph_score >= 4:
            reasons.append("evidence_paragraph")
        if distance >= 0:
            reasons.append("after_roll")
        score = 100 - min(abs(distance), 5000) // 50
        if distance >= 0:
            score += 20
        if paragraph_score >= 4:
            score += min(paragraph_score, 12)
        if re.search(r"(?i)miss(?:ed|es|ing)?\s+(?:a\s+)?connection", span.text):
            score += 12
        if re.search(r"(?i)without\s+a\s+connection|no\s+connection", span.text):
            score += 8
        focused = _focused_miss_span(span, word_offsets, constellation_pattern)
        variants = _candidate_variants(focused, span)
        candidates.append(MissQuoteCandidate(
            text=focused.text.strip(),
            char_start=focused.char_start,
            char_end=focused.char_end,
            word_index=focused.word_index,
            score=score,
            reason_tags=tuple(reasons),
            variants=variants,
        ))
    return candidates


def _candidate_variants(
    focused: _SentenceSpan,
    wide: _SentenceSpan,
) -> tuple[MissQuoteVariant, ...]:
    variants = [
        MissQuoteVariant(
            text=focused.text.strip(),
            char_start=focused.char_start,
            char_end=focused.char_end,
            word_index=focused.word_index,
            label="focused",
        )
    ]
    if (
        focused.char_start != wide.char_start
        or focused.char_end != wide.char_end
    ):
        variants.append(MissQuoteVariant(
            text=wide.text.strip(),
            char_start=wide.char_start,
            char_end=wide.char_end,
            word_index=wide.word_index,
            label="sentence",
        ))
    return tuple(variants)


def _constellation_pattern(constellation: str | None) -> re.Pattern[str] | None:
    if not constellation:
        return None
    terms = [str(constellation)]
    if str(constellation).lower() == "magitech":
        terms.append("Magictech")
    escaped = [re.escape(term).replace(r"\ ", r"\s+") for term in terms]
    return re.compile(r"(?i)(?<![A-Za-z])(?:" + "|".join(escaped) + r")(?![A-Za-z])")


def _focused_miss_span(
    span: _SentenceSpan,
    word_offsets: list[tuple[int, int]],
    constellation_pattern: re.Pattern[str],
) -> _SentenceSpan:
    sentence_text = span.sentence_text or span.text
    sentence_start = (
        span.sentence_char_start
        if span.sentence_char_start is not None else span.char_start
    )
    sentence_end = (
        span.sentence_char_end
        if span.sentence_char_end is not None else span.char_end
    )
    text = sentence_text.strip()
    leading_offset = len(sentence_text) - len(sentence_text.lstrip())
    base_start = sentence_start + leading_offset

    relative = _focused_miss_relative_span(text, constellation_pattern)
    if relative is None:
        return span
    rel_start, rel_end = relative
    char_start = base_start + rel_start
    char_end = base_start + rel_end
    word_index = _word_index_for_char(word_offsets, char_start)
    if word_index is None:
        return span
    return _SentenceSpan(
        text=text[rel_start:rel_end].strip(),
        char_start=char_start,
        char_end=char_end,
        word_index=word_index,
        paragraph_text=span.paragraph_text,
        sentence_text=sentence_text,
        sentence_char_start=sentence_start,
        sentence_char_end=sentence_end,
    )


def _focused_miss_relative_span(
    sentence: str,
    constellation_pattern: re.Pattern[str],
) -> tuple[int, int] | None:
    constellation = constellation_pattern.search(sentence)
    miss = _MISS_LANGUAGE.search(sentence)
    if constellation is None or miss is None:
        return None

    cf = re.search(r"(?i)(?:\bI\s+watched\s+as\s+)?\bthe\s+Celestial\s+Forge\b", sentence)
    if cf is not None and cf.start() <= miss.start():
        end = _trim_end_after(sentence, constellation.end())
        return _strip_span(sentence, cf.start(), end)

    start = _article_start(sentence, constellation.start())
    end = _trim_end_after(sentence, max(constellation.end(), _miss_phrase_end(sentence, miss)))
    return _strip_span(sentence, start, end)


def _miss_phrase_end(sentence: str, miss: re.Match[str]) -> int:
    tail = sentence[miss.start():]
    patterns = (
        r"(?is)\Apass(?:ed|es|ing)?(?:\s+by)?(?:\s+without\s+a\s+connection)?",
        r"(?is)\Amiss(?:ed|es|ing)?(?:\s+(?:a\s+)?connection)?",
        r"(?is)\Afail(?:ed|s|ing)?(?:\s+to\s+secure\s+a\s+connection)?",
        r"(?is)\A(?:mov(?:e|ed|es|ing)|drift(?:ed|s|ing)?)\s+(?:by|past|on)"
        r"(?:\s+as\s+the\s+Celestial\s+Forge\s+fail(?:ed|s|ing)?"
        r"\s+to\s+secure\s+a\s+connection)?",
        r"(?is)\Ano\s+connection\s+formed\s+before\s+it\s+moved\s+on",
        r"(?is)\Aconnection\s+(?:was\s+)?missed",
    )
    for pattern in patterns:
        phrase = re.search(pattern, tail)
        if phrase is not None:
            return miss.start() + phrase.end()
    return miss.end()


def _article_start(sentence: str, start: int) -> int:
    prefix = sentence[:start]
    match = re.search(r"(?i)(?:^|\s)(?:the|a|an)\s+$", prefix)
    if match is None:
        return start
    return match.start() + (1 if prefix[match.start():].startswith(" ") else 0)


def _trim_end_after(sentence: str, end: int) -> int:
    suffix = sentence[end:]
    boundary = re.search(r"(?i)\s+as\s+(?:I|he|she|they|we|the|a|an)\b", suffix)
    if boundary is not None:
        return end + boundary.start()
    while end > 0 and sentence[end - 1] in ".!?":
        end -= 1
    return end


def _strip_span(sentence: str, start: int, end: int) -> tuple[int, int]:
    while start < end and sentence[start].isspace():
        start += 1
    while end > start and sentence[end - 1].isspace():
        end -= 1
    if start == 0:
        suffix = sentence[end:].strip()
        if suffix and all(char in ".!?" for char in suffix):
            end += len(sentence[end:])
        return start, end
    while end > start and sentence[end - 1] in ".!?":
        end -= 1
    return start, end


def _sentence_and_adjacent_spans(
    text: str,
    word_offsets: list[tuple[int, int]],
    *,
    include_adjacent: bool,
) -> list[_SentenceSpan]:
    spans: list[_SentenceSpan] = []
    for paragraph in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", text):
        sentences = _sentence_spans(paragraph.group(0), paragraph.start(), word_offsets)
        spans.extend(sentences)
        if not include_adjacent:
            continue
        for left, right in zip(sentences, sentences[1:]):
            joined = text[left.char_start:right.char_end].strip()
            spans.append(_SentenceSpan(
                text=joined,
                char_start=left.char_start,
                char_end=right.char_end,
                word_index=left.word_index,
                paragraph_text=paragraph.group(0),
                sentence_text=joined,
                sentence_char_start=left.char_start,
                sentence_char_end=right.char_end,
            ))
    return spans


def _sentence_spans(
    paragraph: str,
    paragraph_start: int,
    word_offsets: list[tuple[int, int]],
) -> list[_SentenceSpan]:
    spans: list[_SentenceSpan] = []
    for match in re.finditer(r"(?s).*?(?:[.!?](?=\s+|$)|$)", paragraph):
        raw = match.group(0)
        if not raw.strip():
            continue
        start = paragraph_start + match.start()
        end = paragraph_start + match.end()
        while start < end and paragraph[start - paragraph_start].isspace():
            start += 1
        while end > start and paragraph[end - paragraph_start - 1].isspace():
            end -= 1
        word_index = _word_index_for_char(word_offsets, start)
        if word_index is not None:
            spans.append(_SentenceSpan(
                text=paragraph[start - paragraph_start:end - paragraph_start].strip(),
                char_start=start,
                char_end=end,
                word_index=word_index,
                paragraph_text=paragraph,
                sentence_text=paragraph[start - paragraph_start:end - paragraph_start],
                sentence_char_start=start,
                sentence_char_end=end,
            ))
        if match.end() >= len(paragraph):
            break
    return spans


def _word_index_for_char(
    word_offsets: list[tuple[int, int]], char_offset: int,
) -> int | None:
    for idx, (_start, end) in enumerate(word_offsets):
        if char_offset < end:
            return idx
    return len(word_offsets) - 1 if word_offsets else None

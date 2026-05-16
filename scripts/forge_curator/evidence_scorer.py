"""Paragraph scorer for likely Celestial Forge narrative evidence.

The Forge Curator uses this as a low-noise navigation aid: paragraphs
that score at or above ``EVIDENCE_CANDIDATE_THRESHOLD`` get an ``N``
gutter mark and are the targets for ``n`` / ``N`` navigation.

Tuning notes:
* Matching is case-insensitive, so sentence-start capitalization does
  not need special-case terms.
* Terms are word-bounded to avoid false positives such as matching
  ``pass`` inside ``passenger``.
* The threshold is intentionally low enough to catch compact anchors
  like "constellation passed by without connection"; continuation
  quote fragments such as perk names are left to curator judgment after
  jumping to the anchor paragraph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


EVIDENCE_CANDIDATE_THRESHOLD = 4

TERM_WEIGHTS: dict[str, int] = {
    "core": 3,
    "roll_object": 2,
    "roll_action": 1,
    "power_context": 1,
}

TERM_PATTERNS: dict[str, tuple[str, ...]] = {
    "core": (
        r"celestial\s+forge",
        r"the\s+forge",
    ),
    "roll_object": (
        r"constellations?",
        r"motes?",
    ),
    "roll_action": (
        r"latch(?:ed|es|ing)?",
        r"connect(?:ed|s|ing|ion|ions)?",
        r"link(?:ed|s|ing)?",
        r"grasp(?:ed|s|ing)?",
        r"grab(?:bed|s|bing)?",
        r"fail(?:ed|s|ing)?",
        r"miss(?:ed|es|ing)?",
        r"pass(?:ed|es|ing)?",
        r"sw(?:u|i)ng(?:ing)?",
        r"approach(?:ed|es|ing)?",
        r"reach(?:ed|es|ing)?",
        r"bring(?:ing|s)?",
        r"mov(?:e|ed|es|ing)",
        r"pull(?:ed|s|ing)?",
    ),
    "power_context": (
        r"my\s+power",
        r"powers?",
        r"abilit(?:y|ies)",
        r"passenger",
    ),
}


@dataclass(frozen=True)
class EvidenceCandidate:
    paragraph_index: int
    char_start: int
    char_end: int
    word_index: int
    score: int
    matched_terms: tuple[str, ...]


def evidence_candidates(
    text: str,
    word_offsets: list[tuple[int, int]],
    *,
    threshold: int = EVIDENCE_CANDIDATE_THRESHOLD,
) -> list[EvidenceCandidate]:
    """Return paragraph starts whose keyword score reaches ``threshold``."""
    candidates: list[EvidenceCandidate] = []
    for paragraph_index, match in enumerate(_paragraph_matches(text)):
        paragraph = match.group(0)
        score, matched_terms = score_paragraph(paragraph)
        if score < threshold:
            continue
        word_index = _word_index_for_char(word_offsets, match.start())
        if word_index is None:
            continue
        candidates.append(EvidenceCandidate(
            paragraph_index=paragraph_index,
            char_start=match.start(),
            char_end=match.end(),
            word_index=word_index,
            score=score,
            matched_terms=tuple(matched_terms),
        ))
    return candidates


def score_paragraph(paragraph: str) -> tuple[int, list[str]]:
    """Score one paragraph and return matched display terms.

    Each term group contributes its weight for up to two distinct matches.
    That keeps long paragraphs with repeated terms from overwhelming the
    score while still rewarding combinations like "constellation" plus
    "missed connection".
    """
    score = 0
    matched_terms: list[str] = []
    for group, patterns in TERM_PATTERNS.items():
        group_matches: list[str] = []
        for pattern in patterns:
            found = re.search(_word_bounded(pattern), paragraph, re.IGNORECASE)
            if found is not None:
                group_matches.append(found.group(0))
        score += TERM_WEIGHTS[group] * min(2, len(group_matches))
        matched_terms.extend(group_matches[:3])
    return score, matched_terms


def _paragraph_matches(text: str) -> list[re.Match[str]]:
    return list(re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", text))


def _word_bounded(pattern: str) -> str:
    return rf"(?<![A-Za-z])(?:{pattern})(?![A-Za-z])"


def _word_index_for_char(
    word_offsets: list[tuple[int, int]], char_offset: int,
) -> int | None:
    for idx, (_start, end) in enumerate(word_offsets):
        if char_offset < end:
            return idx
    return len(word_offsets) - 1 if word_offsets else None

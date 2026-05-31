"""Strict quote classification for Forge Curator roll metadata autofill."""

from __future__ import annotations

import re
from dataclasses import dataclass


KNOWN_CONSTELLATIONS = [
    "Alchemy", "Capstone", "Clothing", "Crafting", "Knowledge",
    "Magic", "Magitech", "Personal Reality", "Quality",
    "Resources and Durability", "Size", "Time", "Toolkits", "Vehicles",
]

CONSTELLATION_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(
        re.escape(name) for name in sorted(KNOWN_CONSTELLATIONS, key=len, reverse=True)
    )
    + r")(?![A-Za-z])"
)

_MISS_LANGUAGE = re.compile(
    r"(?i)\b(?:miss(?:ed|es|ing)?|fail(?:ed|s|ing)?)\b|"
    r"\bpass(?:ed|es|ing)?\s+(?:by|past)\b|"
    r"\b(?:mov(?:e|ed|es|ing)|drift(?:ed|s|ing)?)\s+(?:by|past)\b|"
    r"\bwithout\s+a\s+connection\b|"
    r"\bno\s+connection\b|"
    r"\bconnection\s+(?:was\s+)?missed\b|"
    r"\bmissed\s+(?:a\s+)?connection\b"
)

_HIT_LANGUAGE = re.compile(
    r"(?i)\bconnection\s+(?:formed|solidified|locked|made|completed|established)\b|"
    r"\bconnection\s+being\s+made\b|"
    r"\bconnection\s+(?:formed|solidified|locked|made|completed|established)"
    r"\s+with\b|"
    r"\b(?:formed|solidified|locked|made|completed|established)\s+"
    r"(?:a\s+)?connection\b|"
    r"\blatched\s+onto\b|"
    r"\bdescended\s+upon\b|"
    r"\bflood(?:ed|ing)\s+my\s+mind\b|"
    r"\b(?:acquir(?:ed|ing)|gain(?:ed|ing)?)\b"
)


@dataclass(frozen=True)
class QuoteAutofillSuggestion:
    outcome: str
    constellation: str


def classify_quote_autofill(quote: str) -> QuoteAutofillSuggestion | None:
    """Return strict autofill metadata for unambiguous roll-evidence quotes."""
    constellation = single_constellation_reference(quote)
    if constellation is None:
        return None

    has_miss = _MISS_LANGUAGE.search(quote or "") is not None
    has_hit = _HIT_LANGUAGE.search(quote or "") is not None
    if has_miss == has_hit:
        return None

    return QuoteAutofillSuggestion(
        outcome="miss" if has_miss else "hit",
        constellation=constellation,
    )


def single_constellation_reference(quote: str) -> str | None:
    """Return the sole explicit constellation reference in a quote, if any."""
    matches = [
        match for match in CONSTELLATION_NAME_PATTERN.finditer(quote or "")
        if _is_constellation_reference(quote or "", match)
    ]
    if len(matches) != 1:
        return None
    return matches[0].group(0)


def _is_constellation_reference(text: str, match: re.Match[str]) -> bool:
    before = text[:match.start()]
    after = text[match.end():]
    return (
        re.search(r"(?i)\bconstellation\s+$", before) is not None
        or re.match(r"(?i)\s+constellation\b", after) is not None
    )

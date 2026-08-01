"""Deterministic mechanical verification of curated roll data against
source prose and existing pipeline primitives (Phase 2, D-01..D-13).

Pure module — no argparse, no file I/O in ``verify_roll()``. Zero fuzzy
matching anywhere (REQUIREMENTS.md Out of Scope): quote verification is
exact-substring, two normalization tiers, full stop.

Phase 3's confidence gate imports ``verify_roll()``/``build_obtained_perks_index()``
directly. There is no CLI in this plan — the pure API is Task 1's whole
deliverable; a thin CLI convenience wrapper (loading the real corpus and
writing a JSON report) is out of this plan's scope and is built in a
later plan. NOT wired into scripts/pipeline.py and NOT manifest-registered
(D-09) — this is a QA instrument, not a pipeline input.
"""

from __future__ import annotations

import bisect
import re

# Measured against the full 118-chapter hand-curated corpus (2026-07-26):
# max real distance 41 CP-earning words after nearest-occurrence
# disambiguation; 50 gives roughly 20% headroom (D-04).
POSITION_TOLERANCE_WORDS = 50

# D-06(d) AMENDMENT: both enums are null-tolerant — `None` is the corpus's
# dominant, structurally-valid default (541/681 rolls have outcome: null;
# 598/681 have display_position_policy: null). Only a genuinely different
# string value is a failure.
_VALID_OUTCOMES = {"hit", "miss"}
_VALID_DISPLAY_POSITION_POLICIES = {
    "mention", "mechanical", "section_start", "source_marker", "section_end",
}

# Tier-2 confusable-character folding: the specific confusable sets named
# by D-03 — dash, quote (single/double), ellipsis variants. Each maps to a
# fixed character-class or alternation group covering both forms.
_DASH_CHARS = "-–—"          # - – —
_APOSTROPHE_CHARS = "'‘’"     # ' ‘ ’
_DOUBLE_QUOTE_CHARS = '"“”'   # " “ ”
_ELLIPSIS_ALTERNATION = "(?:…|\\.\\.\\.)"  # … or ...

_DASH_CLASS = "[-–—]"
_APOSTROPHE_CLASS = "['‘’]"
_DOUBLE_QUOTE_CLASS = '["“”]'


def _build_tier2_pattern(quote_text: str) -> re.Pattern[str]:
    """Build a single tolerant regex directly from ``quote_text`` (a
    character walk, not a `.replace()` chain on an already-escaped
    string — avoids the replacement text itself being re-matched by a
    later substitution): whitespace runs become `\\s+`; the named
    confusable characters (dash/quote/ellipsis variants) become
    alternation/character-class groups covering both forms; every other
    character is individually `re.escape`d. Compiled with re.IGNORECASE.
    No nested quantifiers, no attacker-controlled alternation depth
    (T-02-04) — every group here is a fixed, bounded literal set.
    """
    parts: list[str] = []
    i = 0
    n = len(quote_text)
    while i < n:
        ch = quote_text[i]
        if ch.isspace():
            j = i
            while j < n and quote_text[j].isspace():
                j += 1
            parts.append(r"\s+")
            i = j
            continue
        if quote_text[i:i + 3] == "...":
            parts.append(_ELLIPSIS_ALTERNATION)
            i += 3
            continue
        if ch == "…":
            parts.append(_ELLIPSIS_ALTERNATION)
            i += 1
            continue
        if ch in _DASH_CHARS:
            parts.append(_DASH_CLASS)
            i += 1
            continue
        if ch in _APOSTROPHE_CHARS:
            parts.append(_APOSTROPHE_CLASS)
            i += 1
            continue
        if ch in _DOUBLE_QUOTE_CHARS:
            parts.append(_DOUBLE_QUOTE_CLASS)
            i += 1
            continue
        parts.append(re.escape(ch))
        i += 1
    return re.compile("".join(parts), re.IGNORECASE)


def _verify_quote(
    quote: dict, chapter_html: str, word_index: list[int],
) -> dict | None:
    """Verify a single evidence quote against its resolved chapter's
    prose. Returns an issue dict on failure, or None on success.
    """
    text = quote.get("text")
    if not text or not str(text).strip():
        return {
            "code": "quote_text_empty",
            "severity": "error",
            "message": "Evidence quote text is empty or whitespace-only.",
        }
    text = str(text)

    claimed_pos = quote.get("mention_word_position")
    if claimed_pos is None:
        return {
            "code": "position_missing",
            "severity": "error",
            "message": (
                f"Evidence quote {text[:60]!r} has no mention_word_position."
            ),
        }

    # Tier 1: exact substring search against the raw, un-normalized HTML —
    # never a whitespace-collapsed copy, which would invalidate the
    # char-offset-to-word-index mapping the position check depends on.
    offsets = [m.start() for m in re.finditer(re.escape(text), chapter_html)]
    if not offsets:
        # Tier 2: single tolerant regex (whitespace + confusable folding),
        # searched against the SAME raw chapter_html.
        pattern = _build_tier2_pattern(text)
        offsets = [m.start() for m in pattern.finditer(chapter_html)]

    if not offsets:
        return {
            "code": "quote_not_found",
            "severity": "error",
            "message": f"Evidence quote {text[:60]!r} not found in claimed chapter's prose.",
        }

    # Nearest-occurrence disambiguation (never first-match — see D-04 /
    # RESEARCH.md Pitfall 2, duplicate-quote false failures).
    best_distance: int | None = None
    for off in offsets:
        word_idx = bisect.bisect_right(word_index, off) - 1
        distance = abs(word_idx - int(claimed_pos))
        if best_distance is None or distance < best_distance:
            best_distance = distance

    if best_distance is not None and best_distance > POSITION_TOLERANCE_WORDS:
        return {
            "code": "position_out_of_tolerance",
            "severity": "error",
            "message": (
                f"Evidence quote {text[:60]!r} matched {best_distance} words "
                f"from its claimed mention_word_position {claimed_pos} "
                f"(tolerance {POSITION_TOLERANCE_WORDS})."
            ),
        }
    return None


def build_obtained_perks_index(obtained_perks_doc: dict) -> dict[tuple[str, str], dict]:
    """Index obtained_perks.json's ``perks`` rows by ``(chapter_num, perk_name)``.

    This is the D-06(c) CORRECTION's cost-determination source: a row's
    ``cost`` field distinguishes a paid perk (resolves through the
    perk_name_resolver.py ladder) from a cost-0 free ride-along (resolves
    by presence in this index alone — perk_directory.json is never
    consulted for it).
    """
    index: dict[tuple[str, str], dict] = {}
    for row in obtained_perks_doc.get("perks") or []:
        key = (str(row.get("chapter_num")), str(row.get("perk_name")))
        index[key] = row
    return index


def _verify_perk(
    name: str,
    chapter_num: str,
    roll: dict,
    directory_index,
    obtained_perks_index: dict[tuple[str, str], dict],
) -> dict | None:
    """Resolve a single perk name via the paid/free-aware branch
    (D-06(c) CORRECTION). Returns an issue dict on failure, or None on
    success.
    """
    row = obtained_perks_index.get((chapter_num, name))
    if row is None:
        mention_chapter = roll.get("mention_chapter_num")
        if mention_chapter is not None and str(mention_chapter) != str(chapter_num):
            row = obtained_perks_index.get((str(mention_chapter), name))

    if row is not None and row.get("cost") == 0:
        # Cost-0 free ride-along: resolved by presence in obtained_perks_index
        # alone. Never call directory_index.lookup for it; a
        # perk_directory.json miss for a free name is never a failure.
        return None

    # Either no row found at all (genuinely paid, untracked name), or a
    # row found with cost > 0: resolve through the existing, unchanged
    # perk_name_resolver.py ladder. jump is always None — override roll
    # objects carry no jump field.
    resolved = directory_index.lookup(
        name, jump=None, constellation=roll.get("constellation"),
    )
    if resolved is None:
        return {
            "code": "perk_unresolved",
            "severity": "error",
            "message": f"Perk name {name!r} did not resolve via the directory ladder.",
        }
    return None


def verify_roll(
    chapter_num: str,
    roll_index: int,
    roll: dict,
    *,
    prose_loader,
    directory_index,
    obtained_perks_index: dict[tuple[str, str], dict],
) -> dict:
    """Verify one curated roll object against source prose and the
    pipeline's existing primitives.

    ``prose_loader`` is a callable ``chapter_num -> (chapter_html, word_index)``
    the caller constructs (lazily loading + caching per chapter).
    ``directory_index`` is a ``perk_name_resolver.DirectoryMatchIndex``.
    ``obtained_perks_index`` is the dict returned by
    ``build_obtained_perks_index()``.

    Returns ``{chapter_num, roll_index, status, issues}`` where status is
    one of ``pass``/``fail``/``no_evidence`` (D-05) and each issue is
    ``{code, severity, message}`` (reusing derive_roll_facts.py's
    ``_manual_override_issues`` reason-code shape verbatim).
    """
    issues: list[dict] = []

    evidence_quotes = roll.get("evidence_quotes") or []
    for quote in evidence_quotes:
        quote_chapter = quote.get("mention_chapter_num") or chapter_num
        chapter_html, word_index = prose_loader(str(quote_chapter))
        issue = _verify_quote(quote, chapter_html, word_index)
        if issue is not None:
            issues.append(issue)

    for name in roll.get("perks") or []:
        issue = _verify_perk(
            name, chapter_num, roll, directory_index, obtained_perks_index,
        )
        if issue is not None:
            issues.append(issue)

    word_position = roll.get("word_position")
    if word_position is not None:
        chapter_html, word_index = prose_loader(chapter_num)
        if not (0 <= int(word_position) < len(word_index)):
            issues.append({
                "code": "word_position_out_of_range",
                "severity": "error",
                "message": (
                    f"roll word_position {word_position} out of range "
                    f"for chapter {chapter_num} ({len(word_index)} CP-earning words)."
                ),
            })

    outcome = roll.get("outcome")
    if outcome is not None and outcome not in _VALID_OUTCOMES:
        issues.append({
            "code": "bad_outcome_enum",
            "severity": "error",
            "message": f"outcome {outcome!r} is not null or one of {sorted(_VALID_OUTCOMES)}.",
        })

    display_position_policy = roll.get("display_position_policy")
    if (
        display_position_policy is not None
        and display_position_policy not in _VALID_DISPLAY_POSITION_POLICIES
    ):
        issues.append({
            "code": "bad_display_position_policy",
            "severity": "error",
            "message": (
                f"display_position_policy {display_position_policy!r} is not "
                f"null or one of {sorted(_VALID_DISPLAY_POSITION_POLICIES)}."
            ),
        })

    if not evidence_quotes and not issues:
        status = "no_evidence"
    elif issues:
        status = "fail"
    else:
        status = "pass"

    return {
        "chapter_num": chapter_num,
        "roll_index": roll_index,
        "status": status,
        "issues": issues,
    }

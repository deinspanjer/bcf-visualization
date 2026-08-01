"""Deterministic mechanical verification of curated roll data against
source prose and existing pipeline primitives (Phase 2, D-01..D-13).

Pure module — no argparse, no file I/O in ``verify_roll()``/``verify_chapter()``.
Zero fuzzy matching anywhere (REQUIREMENTS.md Out of Scope): quote
verification is exact-substring, two normalization tiers, full stop.

Phase 3's confidence gate imports ``verify_roll()``/``verify_chapter()``/
``build_obtained_perks_index()`` directly. The ``if __name__ == "__main__":``
block below is a thin CLI convenience wrapper that loads the real corpus
(epub + chapter_roll_overrides.json + perk_directory.json + perk_aliases.json
+ obtained_perks.json) and writes a JSON report. This module is NOT wired
into the data-regen DAG and NOT registered in the runtime data manifest
(D-09) — it is a QA instrument, not a pipeline input.
"""

from __future__ import annotations

import argparse
import bisect
import html
import json
import re
from pathlib import Path

from cp_word_index import _chapter_word_index, _strip_to_spaces, load_chapter_html
from data_paths import DERIVED, MANUAL, RAW
from perk_name_resolver import build_directory_match_index, load_perk_aliases

# Entities appearing in raw chapter HTML (e.g. "&amp;" for a literal "&"
# inside a compound perk-name quote like "Weapon & Item Storage Chest").
# Hand-curated evidence quotes always carry the DECODED character, never
# the raw entity (measured: RESEARCH.md's entity_intrusion check found
# zero literal entities inside quote text across all 864 corpus quotes).
# A byte-exact/confusable-tolerant search against the raw, un-decoded
# HTML would therefore always miss a quote that happens to straddle an
# entity. Length-preserving decode (pad the decoded form with trailing
# spaces back to the entity's original span) keeps every downstream
# character offset — and therefore the word-index bisect lookup — valid.
_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")


def _decode_entities_preserving_length(chapter_html: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        decoded = html.unescape(m.group(0))
        pad = len(m.group(0)) - len(decoded)
        if pad < 0:
            # A decoded form longer than its entity span is not observed
            # in this corpus; truncate defensively rather than corrupt
            # every later offset in the chapter.
            return decoded[: len(m.group(0))]
        return decoded + (" " * pad)

    return _ENTITY_RE.sub(_replace, chapter_html)


def _prose_search_text(chapter_html: str) -> str:
    """Build the text evidence quotes are searched against: HTML tags and
    entities removed/decoded, every character offset preserved 1:1
    against ``chapter_html`` (so a match's offset stays valid input to
    the same ``word_index`` the tokenizer built from the raw HTML).

    A quote that straddles a paragraph boundary (``</p><p>`` — zero
    literal whitespace in the raw HTML, but the curated quote's own text
    carries a "\\n\\n" paragraph break there) only matches once tags are
    blanked to whitespace; a quote straddling an HTML entity only
    matches once the entity is decoded to its real character. Both
    transforms are length-preserving, so composing them is safe.
    """
    return _strip_to_spaces(_decode_entities_preserving_length(chapter_html))

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

    # Tier 1: exact substring search against the prose-search text — HTML
    # tags blanked to whitespace and entities decoded, both
    # length-preserving (see _prose_search_text), so every offset stays
    # valid against word_index exactly as it would against raw
    # chapter_html. This is NOT a whitespace-collapsing normalization —
    # a quote's internal spacing must still match exactly at Tier 1;
    # only cross-tag/cross-entity boundaries are bridged.
    search_text = _prose_search_text(chapter_html)
    offsets = [m.start() for m in re.finditer(re.escape(text), search_text)]
    if not offsets:
        # Tier 2: single tolerant regex (whitespace + confusable folding),
        # searched against the SAME prose-search text.
        pattern = _build_tier2_pattern(text)
        offsets = [m.start() for m in pattern.finditer(search_text)]

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
    if resolved is not None:
        return None

    # The ladder is the primary paid-perk resolution mechanism and stays
    # unchanged (D-06(c)). It can still fail to disambiguate a genuinely
    # real, confirmed acquisition when perk_directory.json catalogs the
    # same name under a constellation other than the roll's own trigger
    # constellation, or under several constellations at once (a
    # cataloging property of the directory, not a curation error — e.g.
    # a repeatable facility customization like "Entrance Hall - <variant>"
    # is only cataloged under its base name's constellation, and
    # "Synchronicity Event" is cataloged under three constellations, none
    # of which is the roll's own). When that happens, `row` — already
    # looked up above from obtained_perks.json for the cost
    # determination, an independent authoritative source, not a second
    # name-matching implementation — is itself confirmation the name was
    # really acquired in this chapter (or its mention_chapter_num
    # fallback). Only consulted when the ladder alone can't resolve.
    if row is not None:
        return None

    return {
        "code": "perk_unresolved",
        "severity": "error",
        "message": f"Perk name {name!r} did not resolve via the directory ladder.",
    }


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


def verify_chapter(
    chapter_num: str,
    override_entry: dict,
    *,
    prose_loader,
    directory_index,
    obtained_perks_index: dict[tuple[str, str], dict],
) -> dict:
    """Verify every roll in one chapter's ``chapter_roll_overrides.json``
    entry, aggregating per-roll results into a per-chapter pass/fail/
    no_evidence count.

    Returns ``{chapter_num, rolls, counts}`` where ``rolls`` is a list of
    ``verify_roll()`` results (in roll order) and ``counts`` is
    ``{"pass": n, "fail": n, "no_evidence": n}``.
    """
    rolls: list[dict] = []
    counts = {"pass": 0, "fail": 0, "no_evidence": 0}
    for roll_index, roll in enumerate(override_entry.get("rolls") or []):
        result = verify_roll(
            chapter_num, roll_index, roll,
            prose_loader=prose_loader,
            directory_index=directory_index,
            obtained_perks_index=obtained_perks_index,
        )
        rolls.append(result)
        counts[result["status"]] += 1

    return {
        "chapter_num": chapter_num,
        "rolls": rolls,
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# CLI — QA convenience wrapper (D-09: not DAG-wired, not manifest-
# registered). Loads the real corpus, runs verify_chapter() over every
# chapter in chapter_roll_overrides.json, and writes a plain JSON report
# (a bare json.dumps write — deliberately not schema-validated/registered).
# ---------------------------------------------------------------------------

DEFAULT_OVERRIDES = MANUAL / "chapter_roll_overrides.json"
DEFAULT_CHAPTERS = DERIVED / "chapters.json"
DEFAULT_PERK_DIRECTORY = DERIVED / "perk_directory.json"
DEFAULT_PERK_ALIASES = MANUAL / "perk_aliases.json"
DEFAULT_OBTAINED_PERKS = DERIVED / "obtained_perks.json"
DEFAULT_EPUB = RAW / "Brocktons_Celestial_Forge.epub"
DEFAULT_OUTPUT = DERIVED / "mechanical_verification_report.json"
DEFAULT_SECTION_CLASSIFICATIONS = MANUAL / "section_classifications.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--overrides", type=Path, default=DEFAULT_OVERRIDES,
        help="Path to chapter_roll_overrides.json (default: %(default)s)",
    )
    p.add_argument(
        "--chapters", type=Path, default=DEFAULT_CHAPTERS,
        help="Path to chapters.json (default: %(default)s)",
    )
    p.add_argument(
        "--perk-directory", type=Path, default=DEFAULT_PERK_DIRECTORY,
        help="Path to perk_directory.json (default: %(default)s)",
    )
    p.add_argument(
        "--perk-aliases", type=Path, default=DEFAULT_PERK_ALIASES,
        help="Path to perk_aliases.json (default: %(default)s)",
    )
    p.add_argument(
        "--obtained-perks", type=Path, default=DEFAULT_OBTAINED_PERKS,
        help="Path to obtained_perks.json (default: %(default)s)",
    )
    p.add_argument(
        "--epub", type=Path, default=DEFAULT_EPUB,
        help="Path to the source epub (default: %(default)s)",
    )
    p.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Path for the JSON report (default: %(default)s)",
    )
    return p.parse_args(argv)


def _build_prose_loader(epub_path: Path, chapters_doc: dict, classifications_doc: dict):
    """Build a lazy-caching ``chapter_num -> (html, word_index)`` closure
    over the real epub, matching ``verify_roll()``'s ``prose_loader``
    contract.
    """
    href_by_chapter = {
        c["chapter_num"]: c["epub_href"] for c in chapters_doc["chapters"]
    }
    classifications = classifications_doc["classifications"]
    cache: dict[str, tuple[str, list[int]]] = {}

    def _load(chapter_num: str) -> tuple[str, list[int]]:
        if chapter_num not in cache:
            href = href_by_chapter[chapter_num]
            html = load_chapter_html(epub_path, href)
            word_index = _chapter_word_index(html, classifications, chapter_num)
            cache[chapter_num] = (html, word_index)
        return cache[chapter_num]

    return _load


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    overrides_doc = json.loads(args.overrides.read_text())
    chapters_doc = json.loads(args.chapters.read_text())
    perk_directory_doc = json.loads(args.perk_directory.read_text())
    aliases = load_perk_aliases(args.perk_aliases)
    obtained_perks_doc = json.loads(args.obtained_perks.read_text())
    classifications_doc = json.loads(DEFAULT_SECTION_CLASSIFICATIONS.read_text())

    prose_loader = _build_prose_loader(args.epub, chapters_doc, classifications_doc)
    directory_index = build_directory_match_index(perk_directory_doc["perks"], aliases)
    obtained_perks_index = build_obtained_perks_index(obtained_perks_doc)

    chapter_roll_overrides = overrides_doc["chapter_roll_overrides"]
    chapter_results: dict[str, dict] = {}
    totals = {"pass": 0, "fail": 0, "no_evidence": 0}
    for chapter_num, entry in chapter_roll_overrides.items():
        result = verify_chapter(
            chapter_num, entry,
            prose_loader=prose_loader,
            directory_index=directory_index,
            obtained_perks_index=obtained_perks_index,
        )
        chapter_results[chapter_num] = result
        for status, n in result["counts"].items():
            totals[status] += n

    payload = {"chapters": chapter_results, "totals": totals}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    print(f"wrote {args.output}")
    print(f"  pass:        {totals['pass']}")
    print(f"  no_evidence: {totals['no_evidence']}")
    print(f"  fail:        {totals['fail']}")


if __name__ == "__main__":
    main()

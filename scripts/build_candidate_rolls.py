"""Stage 1 (ACUR-01): deterministic, zero-LLM candidate roll assembly.

Binds each of ``data/derived/roll_text_evidence.json``'s 718 predicted-roll
rows against ``data/derived/obtained_perks.json``'s paid-then-free bundle
units (grouped via ``scripts/multi_grab.py:merge_paid_units(overrides=None)``
— reused, never reimplemented) to propose a candidate roll object per row.

This is a proposal surface only (D-04): it writes exclusively to
``data/derived/candidate_rolls.json`` and never opens
``data/manual/chapter_roll_overrides.json`` for writing — not even
read-only, in this script. Candidate objects reuse the existing
``chapter_roll_overrides.json`` roll-object field set verbatim (D-05:
``perks``/``outcome``/``constellation``/``word_position``/``mention_*``/
``display_position_policy``/``evidence_quotes``) plus a ``_derivation``
provenance sub-object, so Phase 4's routing and the Phase 5 TUI review need
no translation layer.

Inputs:
  - data/derived/roll_text_evidence.json (evidence_kind, matching anchors,
    prose windows per predicted roll)
  - data/derived/obtained_perks.json (paid-perk-first acquisition order)
  - data/raw/Brocktons_Celestial_Forge.epub (only for the free-perk forward
    search's prose access, via cp_word_index.py's tokenizer)

Output:
  - data/derived/candidate_rolls.json (validated)

Binding rule (POSITIONAL cursor advance — the primary signal, not gated on
a row's own local anchor evidence — see the plan's revision note for why
an anchor-gated rule was rejected: it only ever bound 36/718 rolls):

For each predicted roll, walked chapter-by-chapter in narrative order
(``predicted_word_in_chapter`` / ``slot_index`` ascending), against a
chapter-local positional cursor over that chapter's default
``merge_paid_units`` bundle units (reset to 0 at the start of each
chapter):

  1. If the row's own ``matching_anchor_kinds`` contains ``"miss"``:
     classify ``outcome: "miss"``, ``perks: []``, and do NOT consume a
     unit (a miss never has a bundle unit — CURATION-CONVENTIONS §4). Bind
     ``constellation`` from a ``constellation_reveal`` event in the row's
     ``matching_events`` if present (strip a leading ``"the "`` and a
     trailing ``"Constellation"``/``"constellation"`` word from that
     event's ``anchor_phrase``, e.g. ``"the Knowledge Constellation"`` ->
     ``"Knowledge"``); otherwise ``constellation: null`` with
     ``"constellation"`` in ``_derivation.unfilled_fields``.
  2. Else, if the chapter's unit cursor still has a unit available:
     consume it as a hit (``perks`` = the unit's paid perk name + free
     ride-along names, ``constellation`` = the paid perk's own
     ``constellation`` field) and advance the cursor by 1 —
     REGARDLESS of whether ``"acquisition"`` is present in the row's own
     ``matching_anchor_kinds``. When ``"acquisition"`` is absent (true for
     the large majority of rolls, since ``matching_anchor_kinds`` is
     scoped to a narrow per-roll window and is empty on most
     ``forward_ref``/``general_only``/``no_evidence`` rows by
     construction), ``"evidence_for:outcome"`` is added to
     ``_derivation.unfilled_fields`` to honestly mark the binding as
     positional-only, not anchor-confirmed.
  3. Else (no unit remains, no ``"miss"`` anchor): the roll is fully
     unfilled — ``outcome: null``, ``constellation: null``,
     ``perks: []`` — never guessed — with ``"outcome"``,
     ``"constellation"``, and ``"perks"`` all listed in
     ``_derivation.unfilled_fields``.

In every branch, ``_derivation.evidence_kind``/``matched_anchor_kinds`` are
copied verbatim from the input row (already computed upstream by
``find_text_backed_rolls.py``, never re-derived), and ``word_position`` is
the row's ``predicted_word_in_chapter`` unchanged (mechanically derived,
ROADMAP success criterion 4). This never joins on ``roll_number``/
``source_ordinal`` identity across the predictor/curator numbering
sequences — those sequences diverge and are never joined (project
convention).

Every bound hit candidate additionally gets a liberal forward search (from
its ``word_position`` onward) for each free perk's name — exact
case-insensitive substring first, then a hyphen/space-tolerant variant
(D-13's Stage-1 search posture: over-produce, match substrings/variants,
the opposite tuning from the exact-or-reject mechanical verifier) —
attaching the first match as an ``evidence_quotes`` entry sliced verbatim
from the located prose match (never composed/paraphrased), or
``"evidence_for:<perk name>"`` in ``_derivation.unfilled_fields`` on no
match.
"""

from __future__ import annotations

import bisect
import json
import re
from pathlib import Path

from _common import write_validated_json
from cp_word_index import _chapter_word_index, load_chapter_html
from data_paths import DERIVED, MANUAL, RAW
from mechanical_verifier import _prose_search_text
from multi_grab import _perk_name, merge_paid_units

ROOT = Path(__file__).resolve().parent.parent
EPUB = RAW / "Brocktons_Celestial_Forge.epub"
ROLL_TEXT_EVIDENCE = DERIVED / "roll_text_evidence.json"
OBTAINED_PERKS = DERIVED / "obtained_perks.json"
CHAPTERS = DERIVED / "chapters.json"
CLASSIFICATIONS = MANUAL / "section_classifications.json"
OUT = DERIVED / "candidate_rolls.json"

# Matches an anchor_phrase of the shape "[the ]<Name> Constellation" /
# "[the ]<Name> constellation" — the two-stage regex catalog's own
# constellation_reveal phrasing (find_roll_locations.py's "the X
# Constellation" pattern). Extracts the bare constellation name; anything
# that doesn't fit this shape (e.g. a bare quoted announcement) is left
# unmatched so the caller can honestly mark it unfilled instead of
# guessing.
_CONSTELLATION_PHRASE_RE = re.compile(
    r"^(?:the\s+)?(?P<name>.+?)\s+constellation$", re.IGNORECASE,
)


def _extract_constellation_from_anchor_phrase(anchor_phrase: str) -> str | None:
    match = _CONSTELLATION_PHRASE_RE.match((anchor_phrase or "").strip())
    if not match:
        return None
    name = match.group("name").strip()
    return name or None


def _find_free_perk_evidence(
    perk_name: str,
    search_text: str,
    word_index: list[int],
    start_word: int,
) -> dict | None:
    """Liberal forward search for ``perk_name``'s first verbatim mention
    at or after ``start_word`` in ``search_text`` (an offset-preserving,
    tag-stripped/entity-decoded prose string — see
    ``mechanical_verifier._prose_search_text``, whose Tier 1 exact-match
    check this deliberately mirrors so any quote emitted here would also
    verify under it).

    Tier 1: exact, case-insensitive substring. Tier 2 (fallback): a
    hyphen/space-tolerant variant match (e.g. obtained-perks name
    "Altmode" against prose "alt-mode") — Stage 1 discovery is
    deliberately liberal (D-13), the opposite tuning from the verifier's
    exact-or-reject bar.

    Returns ``{"text": ..., "mention_word_position": ...}`` (the matched
    span plus a little surrounding context, still a literal substring of
    ``search_text``) or ``None`` if no match is found.
    """
    start_char = (
        word_index[start_word] if 0 <= start_word < len(word_index) else 0
    )

    match = re.compile(re.escape(perk_name), re.IGNORECASE).search(
        search_text, start_char,
    )
    if match is None:
        tokens = [t for t in re.split(r"[\s-]+", perk_name) if t]
        if tokens:
            variant = r"[\s-]*".join(re.escape(t) for t in tokens)
            match = re.compile(variant, re.IGNORECASE).search(
                search_text, start_char,
            )
    if match is None:
        return None

    # Expand the bare match to nearby word boundaries so the quote reads
    # as a real (if short) prose fragment rather than a bare name — still
    # a literal slice of search_text, never composed.
    radius = 40
    lo = max(0, match.start() - radius)
    hi = min(len(search_text), match.end() + radius)
    while lo > 0 and not search_text[lo - 1].isspace():
        lo -= 1
    while hi < len(search_text) and not search_text[hi].isspace():
        hi += 1
    text = search_text[lo:hi].strip()
    if not text:
        text = search_text[match.start():match.end()]

    mention_word_position = max(0, bisect.bisect_right(word_index, match.start()) - 1)
    return {"text": text, "mention_word_position": mention_word_position}


def assemble_candidate(
    roll_evidence_row: dict,
    chapter_units: list[dict],
    unit_cursor: int,
    chapter_html: str | None = None,
    word_index: list[int] | None = None,
) -> tuple[dict, int]:
    """Bind one ``roll_text_evidence.json`` row into a candidate roll
    object. Pure — no file I/O; ``chapter_html``/``word_index`` (when
    supplied) are already-loaded prose for the free-perk forward search
    (see module docstring). Returns ``(candidate, next_unit_cursor)``.
    """
    row = roll_evidence_row
    anchor_kinds = list(row.get("matching_anchor_kinds") or [])
    matching_events = row.get("matching_events") or []
    word_position = row["predicted_word_in_chapter"]

    base = {
        "roll_number": row["roll_number"],
        "chapter_num": row["chapter_num"],
        "slot_index": row["slot_index"],
        "word_position": word_position,
        "mention_chapter_num": row["chapter_num"],
        "mention_word_position": word_position,
        "display_position_policy": "mechanical",
    }
    derivation_common = {
        "evidence_kind": row["evidence_kind"],
        "matched_anchor_kinds": anchor_kinds,
    }

    if "miss" in anchor_kinds:
        constellation = None
        unfilled: list[str] = []
        for event in matching_events:
            if event.get("anchor_kind") == "constellation_reveal":
                constellation = _extract_constellation_from_anchor_phrase(
                    event.get("anchor_phrase", ""),
                )
                break
        if constellation is None:
            unfilled.append("constellation")
        candidate = {
            **base,
            "perks": [],
            "outcome": "miss",
            "constellation": constellation,
            "evidence_quotes": [],
            "_derivation": {
                **derivation_common,
                "bundle_source": None,
                "unfilled_fields": unfilled,
            },
        }
        return candidate, unit_cursor

    if unit_cursor < len(chapter_units):
        unit = chapter_units[unit_cursor]
        unit_cursor += 1
        paid = unit.get("paid") or []
        free = unit.get("free_perks") or []
        paid_names = [n for n in (_perk_name(p) for p in paid) if n]
        free_names = [n for n in (_perk_name(p) for p in free) if n]
        perks = paid_names + free_names
        constellation = paid[0].get("constellation") if paid else None

        unfilled = []
        if constellation is None:
            unfilled.append("constellation")
        if "acquisition" not in anchor_kinds:
            unfilled.append("evidence_for:outcome")

        evidence_quotes: list[dict] = []
        if chapter_html is not None and word_index is not None:
            search_text = _prose_search_text(chapter_html)
            for name in free_names:
                found = _find_free_perk_evidence(
                    name, search_text, word_index, word_position,
                )
                if found is not None:
                    evidence_quotes.append({
                        "text": found["text"],
                        "mention_chapter_num": row["chapter_num"],
                        "mention_word_position": found["mention_word_position"],
                    })
                else:
                    unfilled.append(f"evidence_for:{name}")

        candidate = {
            **base,
            "perks": perks,
            "outcome": "hit",
            "constellation": constellation,
            "evidence_quotes": evidence_quotes,
            "_derivation": {
                **derivation_common,
                "bundle_source": "merge_paid_units:default",
                "unfilled_fields": unfilled,
            },
        }
        return candidate, unit_cursor

    # No unit remains and no "miss" anchor — fully unfilled, never guessed.
    candidate = {
        **base,
        "perks": [],
        "outcome": None,
        "constellation": None,
        "evidence_quotes": [],
        "_derivation": {
            **derivation_common,
            "bundle_source": None,
            "unfilled_fields": ["outcome", "constellation", "perks"],
        },
    }
    return candidate, unit_cursor


if __name__ == "__main__":
    print(
        "build_candidate_rolls.py: assemble_candidate is proven against a "
        "synthetic fixture in this plan's Task 1 <verify> block; full-corpus "
        "wiring lands in Task 2."
    )

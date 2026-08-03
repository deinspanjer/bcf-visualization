"""Assemble the retrieved paragraph set and the shared system prefix.

**Retrieve candidate paragraphs; never send whole chapters or unbounded
spans** (D-01). Measured over all 869 curated evidence quotes and 198
chapters: whole chapters cost ~3,531k tokens, the earlier
windows-plus-forward-spans design ~1,700k, while the union used here —
``evidence_scorer`` at a threshold parameter of 3, unioned with
perk-name-bearing paragraphs — reached 85.5% recall at ~363k tokens.

Two cautions carried from research:

* That 85.5% predates this module's paragraph segmentation, which changes
  what "a paragraph" *is*. Treat it as a prior, not a baseline.
* Do **not** chase the residual by lowering the threshold toward 1: it
  costs ~4x the tokens for 2 points *less* recall than the union. The
  residual is a routing outcome, not a bug (D-04).

Everything here consumes existing, proven modules. Writing a second
paragraph scorer or constellation extractor would be a phase failure
(D-03) — ``evidence_scorer``, ``miss_quote_matcher`` and ``quote_autofill``
already do this work and are proven in the TUI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from forge_curator.evidence_scorer import evidence_candidates
    from forge_curator.miss_quote_matcher import find_miss_quote_candidates
    from forge_curator.quote_autofill import KNOWN_CONSTELLATIONS
    from query_exemplars import retrieve as retrieve_exemplars
    from stage2_prose import paragraphized_prose_text, word_starts_to_spans
except ImportError:  # pragma: no cover - import-path shim
    from scripts.forge_curator.evidence_scorer import (  # type: ignore[no-redef]
        evidence_candidates,
    )
    from scripts.forge_curator.miss_quote_matcher import (  # type: ignore[no-redef]
        find_miss_quote_candidates,
    )
    from scripts.forge_curator.quote_autofill import (  # type: ignore[no-redef]
        KNOWN_CONSTELLATIONS,
    )
    from scripts.query_exemplars import retrieve as retrieve_exemplars  # type: ignore
    from scripts.stage2_prose import (  # type: ignore[no-redef]
        paragraphized_prose_text,
        word_starts_to_spans,
    )


# D-02: pass a threshold PARAMETER. The scorer's shipped default of 4 is
# correctly tuned as a low-noise navigation aid for Dre's n/N jumping;
# degrading interactive navigation to serve a batch job is a bad trade.
STAGE2_RETRIEVAL_THRESHOLD = 3

# Bumped on any prompt edit. Phase 5's fingerprint includes this term.
STAGE2_PROMPT_VERSION = "stage2-prompt-v1"

DEFAULT_EXEMPLAR_K = 3

# Fixed source precedence, used only to break char_start ties so ordering
# is deterministic.
_SOURCE_PRECEDENCE = {"prose_window": 0, "scorer": 1, "perk_name": 2, "miss": 3}


@dataclass(frozen=True)
class Snippet:
    char_start: int
    char_end: int
    word_index: int
    source: str
    text: str


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def perk_name_paragraphs(
    paragraph_spans: list[tuple[int, int, str]], perk_names: list[str]
) -> list[tuple[int, int, str, str]]:
    """Paragraphs containing a known perk name, variant-tolerant.

    Token-subset matching on a punctuation-stripped, lowercased form, so
    ``Altmode`` matches prose "alt-mode" — a separator inserted where the
    perk name has none at all. This is D-01's union component 2; the
    aliases table stays the single source for name variants and no second
    alias table is introduced.
    """
    hits: list[tuple[int, int, str, str]] = []
    for start, end, text in paragraph_spans:
        collapsed = _normalize_token(text)
        for name in perk_names:
            needle = _normalize_token(name)
            if needle and needle in collapsed:
                hits.append((start, end, text, name))
                break
    return hits


def _paragraph_spans(prose_text: str) -> list[tuple[int, int, str]]:
    return [
        (m.start(), m.end(), m.group(0))
        for m in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", prose_text)
    ]


def build_candidate_snippets(
    chapter_num: str,
    *,
    chapter_html: str,
    word_starts: list[int],
    section_classifications: dict[str, dict],
    candidates: list[dict[str, Any]],
    perk_names: list[str],
    evidence_rows: list[dict[str, Any]] | None = None,
    threshold: int = STAGE2_RETRIEVAL_THRESHOLD,
) -> list[Snippet]:
    """The D-01 retrieved paragraph set for one chapter."""
    prose_text = paragraphized_prose_text(
        chapter_html,
        section_classifications=section_classifications,
        chapter_num=chapter_num,
    )
    spans = word_starts_to_spans(word_starts, len(prose_text))
    paragraph_spans = _paragraph_spans(prose_text)

    collected: list[Snippet] = []

    # (1) scorer paragraphs at the Stage-2 threshold
    for cand in evidence_candidates(prose_text, spans, threshold=threshold):
        collected.append(
            Snippet(
                char_start=cand.char_start,
                char_end=cand.char_end,
                word_index=cand.word_index,
                source="scorer",
                text=prose_text[cand.char_start:cand.char_end],
            )
        )

    # (2) paragraphs naming a perk acquired in this chapter
    for start, end, text, _name in perk_name_paragraphs(paragraph_spans, perk_names):
        collected.append(
            Snippet(
                char_start=start,
                char_end=end,
                word_index=_word_index_for(spans, start),
                source="perk_name",
                text=text,
            )
        )

    # (3) each roll's own prose_window as the positional prior
    for row in evidence_rows or []:
        window = row.get("prose_window")
        start = row.get("window_char_start")
        end = row.get("window_char_end")
        if not window or start is None or end is None:
            continue
        collected.append(
            Snippet(
                char_start=int(start),
                char_end=int(end),
                word_index=_word_index_for(spans, int(start)),
                source="prose_window",
                text=str(window),
            )
        )

    # (4) miss-specific candidates. Perk-name matching is structurally
    # inapplicable to a miss (there is no acquired perk), so without this
    # a miss roll is served only by the generic scorer.
    for cand in candidates:
        if (cand.get("outcome") or "") != "miss":
            continue
        anchor = cand.get("word_position")
        if anchor is None:
            continue
        for miss in find_miss_quote_candidates(
            prose_text,
            spans,
            constellation=cand.get("constellation"),
            anchor_word_index=int(anchor),
        ):
            start = getattr(miss, "char_start", None)
            end = getattr(miss, "char_end", None)
            if start is None or end is None:
                continue
            collected.append(
                Snippet(
                    char_start=int(start),
                    char_end=int(end),
                    word_index=_word_index_for(spans, int(start)),
                    source="miss",
                    text=prose_text[int(start):int(end)],
                )
            )

    return _dedupe(collected)


def _word_index_for(spans: list[tuple[int, int]], char_offset: int) -> int:
    import bisect

    starts = [s for s, _ in spans]
    return max(bisect.bisect_right(starts, char_offset) - 1, 0)


def _dedupe(snippets: list[Snippet]) -> list[Snippet]:
    """Drop identical or exactly-adjacent ranges; emit in char order.

    Ties on ``char_start`` break by fixed source precedence so the output
    is deterministic — which matters because the prompt feeds a
    fingerprint.
    """
    ordered = sorted(
        snippets,
        key=lambda s: (
            s.char_start,
            _SOURCE_PRECEDENCE.get(s.source, 99),
            -s.char_end,
        ),
    )
    kept: list[Snippet] = []
    for snip in ordered:
        duplicate = False
        for existing in kept:
            if (
                existing.char_start == snip.char_start
                and existing.char_end == snip.char_end
            ) or existing.char_end == snip.char_start:
                duplicate = True
                break
        if not duplicate:
            kept.append(snip)
    return kept


CONVENTIONS_BRIEF = """\
You are curating Celestial Forge roll evidence from story prose. Reproduce
the practice below exactly.

A ROLL IS A BUNDLE. A hit roll's perks array is ONE PAID PERK followed by
its cost-0 ride-alongs, in that order. A MULTI-GRAB is different: several
PAID motes taken in one roll. Prose wording ("cluster", "several", counts)
corroborates multi-grab grouping.

THE SHAPE OF HIT EVIDENCE, in order:
  1. the mote is reached  -- "I felt the Forge move again"
  2. the constellation is named, usually right there
  3. the paid perk is named, often a little later
  4. free perks are mentioned loosely -- "it also gave me a gun"
The author then dwells on the acquisition, so individual perk names often
appear verbatim several paragraphs later. Attach the FIRST real mention as
an additional quote. A roll's quotes can span most of a chapter (measured
max 7,392 words apart) -- never reject a quote for being far from the roll.

MISSES have no acquired perk to anchor them. Look for the Forge reaching
and FAILING to connect: "failed to latch", "spun away", "constellation
passed", "not enough reach". When the constellation is named, carry it.

PARTIAL EVIDENCE IS AN ACCEPTABLE OUTCOME, AND THIS IS THE KEY RULE.
Capture what is solid and name the remainder in unfilled_fields. Do not
guess, and do not fail a whole roll because one field is unclear. A roll
with zero quotes is a valid submission. An empty rolls array is a valid
submission. Submitting a roll you could not evidence, with its gaps
marked, is MORE useful than omitting it.

Beware a real precision trap: prose often names characters or
consequences around a perk ("Everyone had received their own Entrance
Hall") thousands of words from the roll. Those are consequences being
described, not perk-name evidence. A naive first-mention search attaches
nonsense.

QUOTES MUST BE VERBATIM. Copy the exact characters from the prose you were
shown. Quotes are verified by exact match against the real chapter text --
a paraphrase is rejected outright, and a rejected quote costs the roll its
evidence. Use check_quote to test a quote before submitting it.

You never supply word positions or roll ordinals. They are derived from
your quote text. There is no field for them.
"""


def build_system_prefix(
    *,
    exemplar_index: dict[str, Any] | None = None,
    target_regime: int | None = None,
    target_chapter: str | None = None,
    k: int = DEFAULT_EXEMPLAR_K,
) -> str:
    """Shared conventions + schema + a small k of same-regime exemplars.

    Built once per run and reused across chapters. The target chapter is
    excluded from its own exemplar set — showing a curated chapter its own
    answer would inflate exactly the numbers this pipeline is judged on.
    ``exemplar_index.json`` is 419 KB and is never sent whole.
    """
    parts = [CONVENTIONS_BRIEF, "", "KNOWN CONSTELLATIONS: " + ", ".join(KNOWN_CONSTELLATIONS)]

    if exemplar_index is not None and target_regime is not None:
        filtered = dict(exemplar_index)
        filtered["exemplars"] = [
            entry
            for entry in exemplar_index.get("exemplars", [])
            if str(entry.get("chapter_num")) != str(target_chapter)
        ]
        exemplars = retrieve_exemplars(
            target_regime, filtered, k=k, target_chapter=target_chapter
        )
        if exemplars:
            parts.append("")
            parts.append("WORKED EXAMPLES from comparable chapters:")
            for entry in exemplars:
                parts.append(_format_exemplar(entry))

    parts.append("")
    parts.append(
        "Deliver your result ONLY by calling submit_stage2_rolls. Answering "
        "in prose delivers nothing."
    )
    return "\n".join(parts)


def _format_exemplar(entry: dict[str, Any]) -> str:
    lines = [f"  chapter {entry.get('chapter_num')}:"]
    for roll in (entry.get("rolls") or [])[:2]:
        quotes = [q.get("text", "") for q in (roll.get("evidence_quotes") or [])[:2]]
        lines.append(
            f"    outcome={roll.get('outcome')} "
            f"constellation={roll.get('constellation')} "
            f"perks={(roll.get('perks') or [])[:3]}"
        )
        for quote in quotes:
            lines.append(f"      quote: {quote[:200]}")
    return "\n".join(lines)


def build_user_message(
    chapter_num: str,
    *,
    candidates: list[dict[str, Any]],
    snippets: list[Snippet],
    perk_rows: list[dict[str, Any]],
) -> str:
    """The per-chapter payload: Stage 1 slots, known perks, and prose."""
    lines = [f"CHAPTER {chapter_num}", ""]

    lines.append("STAGE 1 CANDIDATE SLOTS (answer each by slot_index):")
    for cand in candidates:
        derivation = cand.get("_derivation") or {}
        lines.append(
            f"  slot_index={cand.get('slot_index')} "
            f"predicted_word_position={cand.get('word_position')} "
            f"outcome={cand.get('outcome')} "
            f"constellation={cand.get('constellation')} "
            f"evidence_kind={derivation.get('evidence_kind')} "
            f"bundle_source={derivation.get('bundle_source')}"
        )
        if cand.get("perks"):
            lines.append(f"    mechanically-bundled perks: {cand['perks']}")

    if perk_rows:
        lines.append("")
        lines.append("PERKS RECORDED AS ACQUIRED IN THIS CHAPTER:")
        for row in perk_rows:
            kind = "FREE ride-along" if row.get("cost") == 0 else f"PAID {row.get('cost')}"
            lines.append(
                f"  {row.get('perk_name')} [{kind}] "
                f"constellation={row.get('constellation')}"
            )

    lines.append("")
    lines.append(
        f"RETRIEVED PROSE ({len(snippets)} passages, in chapter order). "
        "Quote verbatim from these. If you need prose outside them, call "
        "get_prose_span."
    )
    for snip in snippets:
        lines.append("")
        lines.append(f"  [~word {snip.word_index}, via {snip.source}]")
        lines.append(f"  {snip.text.strip()}")

    lines.append("")
    lines.append(
        f"Now call submit_stage2_rolls for chapter \"{chapter_num}\"."
    )
    return "\n".join(lines)

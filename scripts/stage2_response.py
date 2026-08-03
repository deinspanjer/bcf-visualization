"""Turn a model submission into verified, maximally pre-filled proposals.

This is where the phase's real behaviour lives, and none of it needs
inference to test: ``process_stage2_response`` takes a plain dict and
returns a routing outcome, with no transport, no subprocess, and no MCP.
The MCP tool handler is a thin delegate to it.

The boundary between "model proposes" and "code decides" is explicit here
rather than merely documented:

* The model supplies quote **text** and **structure** only. Every word
  position is derived by *locating* the proposed text in real prose
  (D-10). A quote that cannot be located is recorded as evidence-not-found
  with the model's text preserved for human judgment — never dropped, and
  never given an invented position.
* Rolls map to Stage 1 candidates by an explicit ``slot_index`` carried in
  the payload, never by list position. A duplicate ``slot_index`` rejects
  the whole submission with a correction signal rather than silently
  taking the last one.
* ``self_reported_confidence`` and ``reasoning`` are carried into the
  output and are **never read by any conditional in this module**.

Partial output is correct output (CURATION-CONVENTIONS.md §5). A roll with
zero quotes is valid — WoG-backed rolls legitimately carry none. An empty
``rolls`` array is a valid outcome. Stage 1 slots the model never answered
are still written, marked evidence-not-found, so review is
confirm-or-correct rather than start-from-blank.

**There is no corpus write path in this module.** Everything routes to the
proposals sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from forge_curator.quote_autofill import single_constellation_reference
    from mechanical_verifier import verify_roll
    from stage2_prose import locate_quote, prose_span_text
    from stage2_proposals_io import upsert_chapter_proposal
    from stage2_schema import (
        MAX_PROSE_SPAN_WORDS,
        STAGE2_TOOL_SURFACE_VERSION,
    )
except ImportError:  # pragma: no cover - import-path shim
    from scripts.forge_curator.quote_autofill import (  # type: ignore[no-redef]
        single_constellation_reference,
    )
    from scripts.mechanical_verifier import verify_roll  # type: ignore[no-redef]
    from scripts.stage2_prose import (  # type: ignore[no-redef]
        locate_quote,
        prose_span_text,
    )
    from scripts.stage2_proposals_io import (  # type: ignore[no-redef]
        upsert_chapter_proposal,
    )
    from scripts.stage2_schema import (  # type: ignore[no-redef]
        MAX_PROSE_SPAN_WORDS,
        STAGE2_TOOL_SURFACE_VERSION,
    )


TRACKED_FIELDS = ("perks", "outcome", "constellation", "evidence_quotes")


class DuplicateSlotIndexError(ValueError):
    """Two submitted rolls claimed the same Stage 1 slot.

    Rejecting the whole submission is deliberate. Silently keeping the
    last one would discard a roll the model meant to propose, and the
    model would never learn it happened.
    """


@dataclass
class RoutingOutcome:
    chapter_num: str
    rolls: list[dict[str, Any]]
    per_roll: list[dict[str, Any]]
    stats: dict[str, Any]
    model_facing_summary: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Stage2RunContext:
    """Warm, per-run state shared by every chapter in a batch.

    Holding the prose loader, directory index and perk index here is what
    makes one warm server across a whole run cheaper than one process per
    chapter: these caches get built once, not N times.
    """

    prose_loader: Callable[[str], tuple[str, list[int]]]
    directory_index: Any
    obtained_perks_index: dict[tuple[str, str], dict]
    # chapter_num -> slot_index -> Stage 1 candidate
    candidates_by_chapter: dict[str, dict[int, dict[str, Any]]] = field(
        default_factory=dict
    )
    run_id: str = ""
    model: str = ""
    proposals_path: Path | None = None
    # Handler-side state. This -- never the subprocess exit code -- is the
    # success oracle the transport consults after a run.
    outcomes: dict[str, RoutingOutcome] = field(default_factory=dict)
    submissions: dict[str, dict[str, Any]] = field(default_factory=dict)
    read_set: list[dict[str, Any]] = field(default_factory=list)
    instrumentation: dict[str, int] = field(
        default_factory=lambda: {
            "prose_span_calls": 0,
            "check_quote_calls": 0,
            "prose_span_quotes_verified": 0,
            "check_quote_quotes_verified": 0,
        }
    )
    # Quote text the model saw via each read tool, so Task 3 can report
    # whether a read tool actually contributed a quote that verified.
    _span_texts: list[str] = field(default_factory=list)
    _checked_quotes: set[str] = field(default_factory=set)

    # -- Stage2Context protocol -------------------------------------------

    def submit_rolls(self, chapter_num: str, rolls: list[dict[str, Any]]) -> str:
        self.submissions[str(chapter_num)] = {
            "chapter_num": str(chapter_num),
            "rolls": rolls,
        }
        outcome = process_stage2_response(str(chapter_num), rolls, ctx=self)
        self.outcomes[str(chapter_num)] = outcome
        return outcome.model_facing_summary

    def prose_span(self, chapter_num: str, start_word: int, end_word: int) -> str:
        chapter_html, word_starts = self.prose_loader(str(chapter_num))
        text = prose_span_text(chapter_html, word_starts, start_word, end_word)
        self.instrumentation["prose_span_calls"] += 1
        self._span_texts.append(text)
        self.read_set.append(
            {
                "tool": "get_prose_span",
                "args": {
                    "chapter_num": str(chapter_num),
                    "start_word": start_word,
                    "end_word": end_word,
                },
                "response_sha256": _sha256(text),
            }
        )
        return text

    def check_quote(self, chapter_num: str, quote_text: str) -> dict[str, Any]:
        """Non-authoritative dry run. Records nothing the gate consults.

        The instrumentation below is audit/diagnostic only — it exists so
        the read tools' contribution is *measurable*, and is never an
        input to any routing decision.
        """
        chapter_html, word_starts = self.prose_loader(str(chapter_num))
        located = locate_quote(quote_text, chapter_html, word_starts)
        self.instrumentation["check_quote_calls"] += 1
        self._checked_quotes.add(quote_text)
        result = {
            "found": located["found"],
            "tier": located["tier"],
            "word_position": located["word_position"],
            "occurrence_count": located["occurrence_count"],
        }
        self.read_set.append(
            {
                "tool": "check_quote",
                "args": {"chapter_num": str(chapter_num), "quote_text": quote_text},
                "response_sha256": _sha256(repr(result)),
            }
        )
        return result

    def take_submission(self, chapter_num: str) -> dict[str, Any] | None:
        return self.submissions.get(str(chapter_num))


def _sha256(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _index_submitted_rolls(rolls: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Map submitted rolls by explicit slot_index, never by position."""
    by_slot: dict[int, dict[str, Any]] = {}
    for roll in rolls:
        slot = roll.get("slot_index")
        if slot is None:
            raise DuplicateSlotIndexError(
                "every submitted roll must carry an explicit slot_index"
            )
        slot = int(slot)
        if slot in by_slot:
            raise DuplicateSlotIndexError(
                f"slot_index {slot} was submitted more than once. Each Stage 1 "
                "slot may be answered at most once; resubmit with one roll per "
                "slot."
            )
        by_slot[slot] = roll
    return by_slot


def _assemble_roll(
    chapter_num: str,
    slot_index: int,
    proposed: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    *,
    chapter_html: str,
    word_starts: list[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assemble ONE corpus-shaped roll object plus its sidecar record.

    Assembled exactly once and then routed — never assembled differently
    per destination. A stripped proposal would invert the value function,
    because locating and attaching quotes is precisely the hand-work this
    pipeline exists to remove.
    """
    proposed = proposed or {}
    candidate = candidate or {}

    located_quotes: list[dict[str, Any]] = []
    unlocated_quotes: list[dict[str, Any]] = []
    quote_tiers: list[int | None] = []

    for quote in proposed.get("evidence_quotes") or []:
        text = quote.get("text") or ""
        quote_chapter = quote.get("mention_chapter_num") or chapter_num
        located = locate_quote(text, chapter_html, word_starts)
        if located["found"]:
            located_quotes.append(
                {
                    "text": text,
                    "mention_chapter_num": str(quote_chapter),
                    "mention_word_position": located["word_position"],
                }
            )
            quote_tiers.append(located["tier"])
        else:
            # Preserved verbatim for Dre's judgment. No invented position.
            unlocated_quotes.append(
                {"text": text, "mention_chapter_num": str(quote_chapter)}
            )

    # Mechanical constellation derivation beats the model's proposal: the
    # code-derived value comes from the canonical 14-item list applied to
    # a quote that actually exists in the prose.
    mechanical_constellation = None
    for quote in located_quotes:
        found = single_constellation_reference(quote["text"])
        if found is not None:
            mechanical_constellation = found
            break

    model_constellation = proposed.get("constellation")
    if mechanical_constellation is not None:
        constellation = mechanical_constellation
        if model_constellation and model_constellation != mechanical_constellation:
            constellation_check = "mechanical_overrides"
        else:
            constellation_check = "mechanical_agrees"
    else:
        constellation = model_constellation or candidate.get("constellation")
        constellation_check = "model_only" if constellation else None

    perks = proposed.get("perks")
    if perks is None:
        perks = list(candidate.get("perks") or [])

    outcome = proposed.get("outcome")
    if outcome is None:
        outcome = candidate.get("outcome")

    roll = {
        "perks": list(perks),
        "outcome": outcome,
        "constellation": constellation,
        # Mechanically predicted by Stage 1; the model never supplies it.
        "word_position": candidate.get("word_position"),
        "mention_chapter_num": candidate.get("mention_chapter_num"),
        "mention_word_position": candidate.get("mention_word_position"),
        "display_position_policy": candidate.get("display_position_policy"),
        "skipped": False,
        "source_ordinal": None,
        "evidence_quotes": located_quotes,
        "curator_note": proposed.get("curator_note"),
    }

    unfilled = _unfilled_fields(roll, proposed, unlocated_quotes)

    sidecar = {
        "slot_index": slot_index,
        "answered_by_model": bool(proposed),
        "quote_tiers": quote_tiers,
        "unlocated_quotes": unlocated_quotes,
        "unfilled_fields": unfilled,
        "constellation_check": constellation_check,
        "evidence_kind": (candidate.get("_derivation") or {}).get("evidence_kind"),
        # Explanatory metadata only. Never read by a conditional here.
        "self_reported_confidence": proposed.get("self_reported_confidence"),
        "reasoning": proposed.get("reasoning"),
    }
    return roll, sidecar


def _unfilled_fields(
    roll: dict[str, Any],
    proposed: dict[str, Any],
    unlocated_quotes: list[dict[str, Any]],
) -> list[str]:
    """Per-field record of what is evidenced vs evidence-not-found.

    Marking a field here is a success, not a failure (§5). It is what
    turns review into confirm-or-correct.
    """
    unfilled: list[str] = []
    for name in TRACKED_FIELDS:
        value = roll.get(name)
        if value in (None, [], ""):
            unfilled.append(name)
    if unlocated_quotes and "evidence_quotes" not in unfilled:
        unfilled.append("evidence_quotes:partial")
    for name in proposed.get("unfilled_fields") or []:
        if name not in unfilled:
            unfilled.append(str(name))
    return unfilled


def process_stage2_response(
    chapter_num: str,
    rolls: list[dict[str, Any]],
    *,
    ctx: Stage2RunContext,
) -> RoutingOutcome:
    """Verify, pre-fill, and route one chapter's submission to proposals.

    Raises :class:`DuplicateSlotIndexError` on a duplicate ``slot_index``;
    the MCP layer turns that into an ``isError`` correction signal.
    """
    chapter_num = str(chapter_num)
    by_slot = _index_submitted_rolls(rolls)

    chapter_html, word_starts = ctx.prose_loader(chapter_num)
    candidates = ctx.candidates_by_chapter.get(chapter_num, {})

    # Every Stage 1 slot appears in the output, whether or not the model
    # answered it. A blank chapter captures none of the value; an
    # unanswered slot marked evidence-not-found still tells Dre where to
    # look.
    all_slots = sorted(set(by_slot) | set(candidates))

    assembled: list[dict[str, Any]] = []
    per_roll: list[dict[str, Any]] = []

    for roll_index, slot in enumerate(all_slots):
        roll, sidecar = _assemble_roll(
            chapter_num,
            slot,
            by_slot.get(slot),
            candidates.get(slot),
            chapter_html=chapter_html,
            word_starts=word_starts,
        )
        verification = verify_roll(
            chapter_num,
            roll_index,
            roll,
            prose_loader=ctx.prose_loader,
            directory_index=ctx.directory_index,
            obtained_perks_index=ctx.obtained_perks_index,
        )
        sidecar["verify_status"] = verification["status"]
        sidecar["verify_issues"] = verification["issues"]
        assembled.append(roll)
        per_roll.append(sidecar)

    stats = _summarize(assembled, per_roll)
    _credit_read_tools(ctx, assembled)

    entry = {
        "curated_by": "agent",
        "rolls": assembled,
        "_stage2": {
            "run_id": ctx.run_id,
            "model": ctx.model,
            "tool_surface_version": STAGE2_TOOL_SURFACE_VERSION,
            "generated_at": _utc_now(),
            "per_roll": per_roll,
        },
    }
    upsert_chapter_proposal(entry, chapter_num, ctx.proposals_path)

    return RoutingOutcome(
        chapter_num=chapter_num,
        rolls=assembled,
        per_roll=per_roll,
        stats=stats,
        # States what was accepted, never where it went. If the model
        # learned the destination, the next turn's proposals would be
        # steered by it.
        model_facing_summary=(
            f"Recorded {stats['rolls']} roll(s) for chapter {chapter_num}: "
            f"{stats['quotes_located']} quote(s) located in the prose, "
            f"{stats['quotes_unlocated']} could not be found. "
            "Quotes that could not be found are kept as-is for human review."
        ),
    )


def _summarize(
    rolls: list[dict[str, Any]], per_roll: list[dict[str, Any]]
) -> dict[str, Any]:
    tiers = [tier for entry in per_roll for tier in entry["quote_tiers"]]
    return {
        "rolls": len(rolls),
        "answered_by_model": sum(1 for e in per_roll if e["answered_by_model"]),
        "quotes_located": sum(len(r["evidence_quotes"]) for r in rolls),
        "quotes_unlocated": sum(len(e["unlocated_quotes"]) for e in per_roll),
        "tier1": sum(1 for t in tiers if t == 1),
        "tier2": sum(1 for t in tiers if t == 2),
        "verify_pass": sum(1 for e in per_roll if e["verify_status"] == "pass"),
        "verify_fail": sum(1 for e in per_roll if e["verify_status"] == "fail"),
        "verify_no_evidence": sum(
            1 for e in per_roll if e["verify_status"] == "no_evidence"
        ),
        "fields_prefilled": sum(
            sum(1 for f in TRACKED_FIELDS if r.get(f) not in (None, [], ""))
            for r in rolls
        ),
        "rolls_evidence_not_found": sum(
            1 for r in rolls if not r["evidence_quotes"]
        ),
    }


def _credit_read_tools(ctx: Stage2RunContext, rolls: list[dict[str, Any]]) -> None:
    """Attribute verified quotes back to the read tool that surfaced them.

    Instrumentation for the explicit keep-or-drop decision on
    ``get_prose_span``: if it recovers nothing that verifies, it should be
    deleted rather than have its caps tuned upward.
    """
    for roll in rolls:
        for quote in roll["evidence_quotes"]:
            text = quote["text"]
            if text in ctx._checked_quotes:
                ctx.instrumentation["check_quote_quotes_verified"] += 1
            if any(text and text in span for span in ctx._span_texts):
                ctx.instrumentation["prose_span_quotes_verified"] += 1

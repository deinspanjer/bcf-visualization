"""Explicit JSON Schemas for the Stage 2 propose-only MCP tool surface.

These schemas are written by hand and are **never** derived from function
signatures. Research (04-RESEARCH.md Q1) measured ``FastMCP``'s
signature-derived schema silently coercing the integer ``104`` into the
string ``"104"`` via pydantic leniency. A coerced ``chapter_num`` feeds
mechanical position derivation, so that coercion is a live corruption
path, not a cosmetic difference. The low-level ``Server`` with an explicit
``inputSchema`` rejects it instead.

Every schema sets ``additionalProperties: false``. That is load-bearing in
two directions:

1. It stops the model inventing fields the pipeline would silently drop.
2. It is how D-10 is *enforced* rather than merely requested — the model
   proposes quote text and structure only, so there is deliberately no
   ``word_position``/``mention_word_position``/``source_ordinal`` property
   anywhere in the submission schema. A model that tries to supply a
   position gets an ``isError`` correction signal at the tool boundary.

The guarantee these schemas carry is real only because
``Server.call_tool(validate_input=True)`` runs ``jsonschema.validate`` and
returns ``_make_error_result`` on failure. The MCP specification places
the input-validation MUST on *servers*, not on the wire — there is no
client-side MUST. Do not describe this as "the protocol validates it"
without that flag being set (D-32).

No tool in this surface writes a curation edit, accepts a destination
argument, or returns a destination (D-26/D-30).
"""

from __future__ import annotations

# Bumped whenever any tool's schema or observable behaviour changes.
# Phase 5's D-20 fingerprint includes this term: changing what
# ``get_prose_span`` returns changes achievable output exactly as much as
# a prompt edit does.
STAGE2_TOOL_SURFACE_VERSION = "stage2-tools-v1"

# Read-tool caps (D-30). Enforced as inclusive integer comparisons in the
# handler — the 5th and 20th calls succeed, the 6th and 21st are refused.
# No floating-point arithmetic anywhere in the cap path.
MAX_PROSE_SPAN_WORDS = 400
MAX_PROSE_SPAN_CALLS = 5
MAX_CHECK_QUOTE_CALLS = 20

# The exact tool set. Asserted by set equality in
# tests/test_stage2_mcp_server.py::test_tool_surface_is_propose_only so a
# fourth tool cannot be added without a test failing.
STAGE2_TOOL_NAMES = frozenset(
    {"submit_stage2_rolls", "get_prose_span", "check_quote"}
)


# ---------------------------------------------------------------------------
# submit_stage2_rolls — the only delivery channel
# ---------------------------------------------------------------------------

_EVIDENCE_QUOTE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text"],
    "properties": {
        "text": {
            "type": "string",
            "minLength": 1,
            "description": (
                "Verbatim prose, copied exactly from the chapter. Not "
                "paraphrased, not trimmed mid-word. This text is located "
                "in the real prose mechanically; a quote that cannot be "
                "located is recorded as evidence-not-found and is never "
                "given an invented position."
            ),
        },
        # A quote may legitimately live in a different chapter than its
        # roll (8% of corpus quotes do). That is a chapter identity, not a
        # position, so the model may propose it.
        "mention_chapter_num": {
            "type": ["string", "null"],
            "description": (
                "Only set this when the quote genuinely appears in a "
                "different chapter than the roll. Otherwise omit it."
            ),
        },
    },
}

_ROLL_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["slot_index"],
    "properties": {
        # Explicit slot mapping. process_stage2_response maps submitted
        # rolls to Stage 1 candidates by THIS field, never by list
        # position, and rejects the whole submission on a duplicate rather
        # than silently taking the last one.
        "slot_index": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Which Stage 1 candidate slot this roll answers. Required. "
                "Must be unique within the submission."
            ),
        },
        "perks": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "One paid perk followed by its cost-0 ride-alongs, in that "
                "order (a bundle). For a multi-grab, several paid perks "
                "taken in one roll. Empty for a miss."
            ),
        },
        "outcome": {
            "enum": ["hit", "miss", None],
            "description": "hit, miss, or null when genuinely undetermined.",
        },
        "constellation": {
            "type": ["string", "null"],
            "description": (
                "Named constellation, when the prose names it. A verified "
                "quote's mechanically-derived constellation beats this."
            ),
        },
        "grouping": {
            "enum": ["bundle", "multi_grab", None],
            "description": (
                "bundle = one paid perk plus cost-0 ride-alongs. "
                "multi_grab = several paid motes in one roll (the Personal "
                "Reality / Additional Space mechanic)."
            ),
        },
        "evidence_quotes": {
            "type": "array",
            "items": _EVIDENCE_QUOTE_SCHEMA,
            "description": (
                "May be empty. A roll with zero quotes is a valid outcome "
                "-- WoG-backed rolls and evidence-not-found rolls are both "
                "legitimate. Do not invent a quote to avoid an empty array."
            ),
        },
        "unfilled_fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "Fields you could not evidence. Naming a field here is a "
                "success, not a failure (CURATION-CONVENTIONS.md 5). "
                "Partial output is correct output."
            ),
        },
        "curator_note": {
            "type": ["string", "null"],
            "description": "Short free-text note for the human reviewer.",
        },
        # Explanatory metadata ONLY. D-13 TIGHTENED: self-report is never a
        # routing input and is never read by any conditional in the gate.
        "self_reported_confidence": {
            "enum": ["high", "low", None],
            "description": (
                "Recorded for human review and post-hoc calibration. It "
                "does not influence routing."
            ),
        },
        "reasoning": {
            "type": ["string", "null"],
            "description": "One line. Explanatory metadata only.",
        },
    },
}

SUBMIT_STAGE2_ROLLS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chapter_num", "rolls"],
    "properties": {
        "chapter_num": {
            "type": "string",
            "description": (
                "Chapter identifier as a string, exactly as given to you "
                "(e.g. \"92\", \"121.1\"). Not a number."
            ),
        },
        "rolls": {
            "type": "array",
            "items": _ROLL_PROPOSAL_SCHEMA,
            "description": (
                "May be empty. An empty array is a valid partial outcome, "
                "not an error."
            ),
        },
    },
}


# ---------------------------------------------------------------------------
# get_prose_span — bounded read (D-30)
# ---------------------------------------------------------------------------

GET_PROSE_SPAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chapter_num", "start_word", "end_word"],
    "properties": {
        "chapter_num": {"type": "string"},
        "start_word": {
            "type": "integer",
            "minimum": 0,
            "description": "Inclusive CP-earning word index to start at.",
        },
        "end_word": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Exclusive CP-earning word index to stop at. The span may "
                f"cover at most {MAX_PROSE_SPAN_WORDS} CP words, and at "
                f"most {MAX_PROSE_SPAN_CALLS} spans may be read per chapter."
            ),
        },
    },
}


# ---------------------------------------------------------------------------
# check_quote — non-authoritative dry run (D-30)
# ---------------------------------------------------------------------------

CHECK_QUOTE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chapter_num", "quote_text"],
    "properties": {
        "chapter_num": {"type": "string"},
        "quote_text": {
            "type": "string",
            "minLength": 1,
            "description": (
                "Candidate quote to dry-run against the real prose. This "
                "is NOT authoritative -- the submission re-runs the real "
                "verifier regardless. It records nothing. At most "
                f"{MAX_CHECK_QUOTE_CALLS} checks per chapter."
            ),
        },
    },
}


TOOL_INPUT_SCHEMAS = {
    "submit_stage2_rolls": SUBMIT_STAGE2_ROLLS_SCHEMA,
    "get_prose_span": GET_PROSE_SPAN_SCHEMA,
    "check_quote": CHECK_QUOTE_SCHEMA,
}

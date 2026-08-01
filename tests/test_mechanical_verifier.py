from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import EPUB, _chapter_word_index, load_chapter_html  # noqa: E402
from scripts.data_paths import DERIVED, MANUAL  # noqa: E402
from scripts.mechanical_verifier import (  # noqa: E402
    POSITION_TOLERANCE_WORDS,
    build_obtained_perks_index,
    verify_roll,
)
from scripts.perk_name_resolver import build_directory_match_index  # noqa: E402


# ---------------------------------------------------------------------------
# Real-data fixtures shared by the two tracer-style tests (Task 1). These are
# the ONLY tests in this file that touch the real (gitignored, locally
# present) epub or the real corpus — every unit test added by Task 2 uses
# synthetic fixtures instead.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_overrides() -> dict:
    doc = json.loads((MANUAL / "chapter_roll_overrides.json").read_text())
    return doc["chapter_roll_overrides"]


@pytest.fixture(scope="module")
def real_prose_loader():
    chapters = json.loads((DERIVED / "chapters.json").read_text())["chapters"]
    href_by_chapter = {c["chapter_num"]: c["epub_href"] for c in chapters}
    classifications = json.loads(
        (MANUAL / "section_classifications.json").read_text()
    )["classifications"]

    cache: dict[str, tuple[str, list[int]]] = {}

    def _load(chapter_num: str) -> tuple[str, list[int]]:
        if chapter_num not in cache:
            href = href_by_chapter[chapter_num]
            html = load_chapter_html(EPUB, href)
            word_index = _chapter_word_index(html, classifications, chapter_num)
            cache[chapter_num] = (html, word_index)
        return cache[chapter_num]

    return _load


@pytest.fixture(scope="module")
def real_directory_index():
    directory_rows = json.loads((DERIVED / "perk_directory.json").read_text())["perks"]
    aliases = json.loads((MANUAL / "perk_aliases.json").read_text())
    return build_directory_match_index(directory_rows, aliases)


@pytest.fixture(scope="module")
def real_obtained_perks_index():
    obtained_perks_doc = json.loads((DERIVED / "obtained_perks.json").read_text())
    return build_obtained_perks_index(obtained_perks_doc)


def test_tracer_ch67_roll1_personal_reality_multigrab_passes_end_to_end(
    real_overrides, real_prose_loader, real_directory_index, real_obtained_perks_index,
) -> None:
    """The plan's tracer bullet: chapter 67's five-perk Personal Reality
    multi-grab hit — four paid perks resolving via the directory ladder,
    one cost-0 free ride-along ("Neutral Lighting") resolving via
    obtained_perks_index alone. Exercises the tokenizer, both quote tiers,
    the D-04 position check, both perk-resolution branches, and the
    null-tolerant enum check together, end-to-end, against real data.
    """
    roll = real_overrides["67"]["rolls"][1]
    assert roll["perks"] == [
        "The Pond", "The Meaning of Life", "The Pond-Expansion",
        "Neutral Lighting", "Natural Lighting",
    ]
    result = verify_roll(
        "67", 1, roll,
        prose_loader=real_prose_loader,
        directory_index=real_directory_index,
        obtained_perks_index=real_obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_ch92_roll1_transformers_bundle_free_ride_alongs_resolve(
    real_overrides, real_prose_loader, real_directory_index, real_obtained_perks_index,
) -> None:
    """D-06(c) CORRECTION's canonical example: chapter 92's seven-perk
    Transformers bundle — one paid "Cybertronian Forge" plus six cost-0
    ride-alongs, none of which resolve via directory_index.lookup. This
    is the harder free-path case: every one of the six free names would
    report perk_unresolved under the pre-correction all-through-the-ladder
    design.
    """
    roll = real_overrides["92"]["rolls"][1]
    assert roll["perks"] == [
        "Cybertronian Forge", "Altmode", "Decepticon Terrorize!", "Energon",
        "Energon Battle Pistol", "Energon Melee Weapon",
        "ROBOTS IN DISGUISE! - Medium Chassis",
    ]
    result = verify_roll(
        "92", 1, roll,
        prose_loader=real_prose_loader,
        directory_index=real_directory_index,
        obtained_perks_index=real_obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


# ===========================================================================
# Task 2: unit tests against synthetic fixtures. None of these reference
# data/raw/Brocktons_Celestial_Forge.epub or set BCF_DATA_DIR directly —
# they build tiny, hand-crafted (chapter_html, word_index) pairs and
# directory/obtained-perks indexes instead.
# ===========================================================================

def _word_index_for(html: str) -> list[int]:
    """Simple `\\S+`-token char-offset index for a plain-text synthetic
    fixture — the same word-boundary definition cp_word_index.py's real
    tokenizer uses, without going through the full section-classification
    machinery (that machinery is covered separately by test_cp_word_index.py).
    """
    return [m.start() for m in re.finditer(r"\S+", html)]


class _ProseDB:
    """A tiny synthetic prose_loader: chapter_num -> (html, word_index)."""

    def __init__(self) -> None:
        self._chapters: dict[str, tuple[str, list[int]]] = {}

    def add(self, chapter_num: str, html: str) -> "_ProseDB":
        self._chapters[chapter_num] = (html, _word_index_for(html))
        return self

    def __call__(self, chapter_num: str) -> tuple[str, list[int]]:
        return self._chapters[chapter_num]


class _SpyDirectoryIndex:
    """Records every `.lookup()` call; returns None unless a canned
    resolution is supplied — used both as a plain no-op stub (for tests
    with no perks to resolve) and as the free-path spy (asserting the
    directory is never consulted for a cost-0 ride-along).
    """

    def __init__(self, resolves: dict[str, dict] | None = None) -> None:
        self.calls: list[tuple[str, object, object]] = []
        self._resolves = resolves or {}

    def lookup(self, raw_name, jump=None, constellation=None):
        self.calls.append((raw_name, jump, constellation))
        return self._resolves.get(raw_name)


def _quote(text: str, mention_chapter_num: str, mention_word_position: int | None) -> dict:
    return {
        "text": text,
        "mention_chapter_num": mention_chapter_num,
        "mention_word_position": mention_word_position,
    }


def _roll(
    *,
    perks: list[str] | None = None,
    outcome: str | None = None,
    constellation: str | None = None,
    word_position: int | None = None,
    display_position_policy: str | None = None,
    evidence_quotes: list[dict] | None = None,
    mention_chapter_num: str | None = None,
) -> dict:
    roll: dict = {
        "perks": perks or [],
        "outcome": outcome,
        "constellation": constellation,
        "word_position": word_position,
        "display_position_policy": display_position_policy,
        "evidence_quotes": evidence_quotes or [],
    }
    if mention_chapter_num is not None:
        roll["mention_chapter_num"] = mention_chapter_num
    return roll


_NO_DIRECTORY = _SpyDirectoryIndex()


# ---------------------------------------------------------------------------
# Quote verification: Tier 1, Tier 2 (whitespace + each confusable class),
# reject-on-word-edit, nearest-occurrence disambiguation, cross-chapter
# resolution, and the "different chapter always fails" invariant.
# ---------------------------------------------------------------------------

def test_tier1_exact_quote_match_passes() -> None:
    prose = _ProseDB().add("1", "Alpha bravo charlie delta echo foxtrot golf.")
    roll = _roll(evidence_quotes=[_quote("charlie delta echo", "1", 2)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_tier2_whitespace_run_difference_passes() -> None:
    # Prose carries an internal paragraph-break-sized whitespace run where
    # the curated quote text only has a single space.
    prose = _ProseDB().add("1", "Alpha bravo\n\ncharlie delta echo.")
    roll = _roll(evidence_quotes=[_quote("bravo charlie", "1", 1)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_tier2_dash_confusable_passes() -> None:
    prose = _ProseDB().add("1", "The pre–installed system failed unexpectedly.")
    roll = _roll(evidence_quotes=[_quote("pre-installed system failed", "1", 1)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_tier2_quote_confusable_passes() -> None:
    prose = _ProseDB().add("1", "She said, “that won’t work” to the group.")
    roll = _roll(evidence_quotes=[_quote("that won't work", "1", 2)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_tier2_ellipsis_confusable_passes() -> None:
    prose = _ProseDB().add("1", "He paused… then continued speaking.")
    roll = _roll(evidence_quotes=[_quote("paused... then", "1", 1)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_reject_word_level_edit_fails_quote_not_found() -> None:
    prose = _ProseDB().add("1", "Alpha bravo charlie delta echo foxtrot golf.")
    # "charlie" substituted for "chXrlie" — a word-level edit, never
    # fuzzy-accepted under either tier.
    roll = _roll(evidence_quotes=[_quote("bravo chXrlie delta", "1", 1)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["quote_not_found"]


def test_duplicate_quote_nearest_occurrence_disambiguation() -> None:
    prefix = " ".join(f"w{i}" for i in range(5))            # word indices 0-4
    phrase = "the target phrase"                              # word indices 5-7 (first) / 98-100 (second)
    middle = " ".join(f"m{i}" for i in range(90))             # word indices 8-97
    html = f"{prefix} {phrase} {middle} {phrase} tail"
    prose = _ProseDB().add("1", html)
    # Claim a position near the SECOND occurrence (98) — nearest-occurrence
    # disambiguation must not naively pick the first match at index 5
    # (distance 92, would false-fail) over the second (distance 1).
    roll = _roll(evidence_quotes=[_quote(phrase, "1", 97)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_quote_position_out_of_tolerance_fails() -> None:
    html = "gamma delta " + " ".join(f"w{i}" for i in range(100))
    prose = _ProseDB().add("1", html)
    claimed = POSITION_TOLERANCE_WORDS + 10  # comfortably past the tolerance
    roll = _roll(evidence_quotes=[_quote("gamma delta", "1", claimed)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["position_out_of_tolerance"]


def test_cross_chapter_quote_resolves_via_mention_chapter_num() -> None:
    prose = (
        _ProseDB()
        .add("A", "Nothing relevant happens in this chapter at all.")
        .add("B", "The real evidence phrase appears right here in chapter B.")
    )
    roll = _roll(evidence_quotes=[_quote("real evidence phrase", "B", 2)])
    result = verify_roll(
        "A", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_quote_found_only_in_different_chapter_always_fails() -> None:
    prose = (
        _ProseDB()
        .add("X", "Chapter X prose does not contain the phrase at all.")
        .add("Y", "The elusive phrase only lives in chapter Y, never chapter X.")
    )
    # Claims chapter X, but the exact text only exists in chapter Y — the
    # verifier must never fall back to searching other chapters.
    roll = _roll(evidence_quotes=[_quote("elusive phrase", "X", 1)])
    result = verify_roll(
        "X", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["quote_not_found"]


def test_quote_text_empty_fails() -> None:
    prose = _ProseDB().add("1", "Some prose here.")
    roll = _roll(evidence_quotes=[_quote("   ", "1", 0)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["quote_text_empty"]


def test_quote_missing_position_fails() -> None:
    prose = _ProseDB().add("1", "Some prose here today.")
    roll = _roll(evidence_quotes=[_quote("prose here", "1", None)])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["position_missing"]


# ---------------------------------------------------------------------------
# Enum sanity (null-tolerant) and roll-level word_position range.
# ---------------------------------------------------------------------------

def test_null_outcome_and_display_position_policy_pass() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    roll = _roll(outcome=None, display_position_policy=None)
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"


def test_invalid_outcome_and_display_position_policy_fail() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    roll = _roll(outcome="win", display_position_policy="floating")
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    codes = {i["code"] for i in result["issues"]}
    assert codes == {"bad_outcome_enum", "bad_display_position_policy"}


def test_word_position_in_range_passes() -> None:
    html = " ".join(f"w{i}" for i in range(10))
    prose = _ProseDB().add("1", html)
    roll = _roll(word_position=5)
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"


def test_word_position_out_of_range_fails() -> None:
    html = " ".join(f"w{i}" for i in range(10))
    prose = _ProseDB().add("1", html)
    roll = _roll(word_position=999)
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["word_position_out_of_range"]


# ---------------------------------------------------------------------------
# Perk resolution: paid-path (ladder, jump=None), free-path (obtained_perks
# alone, directory never consulted), adjacent-chapter fallback, and
# absent-from-index falling through to the paid ladder.
# ---------------------------------------------------------------------------

def _synthetic_directory_index():
    directory_rows = [
        {"name": "Test Perk", "jump": "Test Jump", "constellation": "Quality"},
    ]
    return build_directory_match_index(directory_rows, aliases={})


def test_paid_perk_with_cost_row_resolves_via_ladder_jump_none() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    directory_index = _synthetic_directory_index()
    obtained_perks_index = {("1", "Test Perk"): {"cost": 200}}
    roll = _roll(perks=["Test Perk"], constellation="Quality")
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=directory_index,
        obtained_perks_index=obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"


def test_paid_perk_unresolved_fails() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    directory_index = _synthetic_directory_index()
    roll = _roll(perks=["Totally Unknown Perk"], constellation="Quality")
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=directory_index, obtained_perks_index={},
    )
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["perk_unresolved"]


def test_free_perk_resolves_without_touching_directory() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    spy = _SpyDirectoryIndex()
    obtained_perks_index = {("1", "Free Ride-Along"): {"cost": 0}}
    roll = _roll(perks=["Free Ride-Along"], constellation="Quality")
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=spy,
        obtained_perks_index=obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"
    assert spy.calls == []


def test_adjacent_chapter_free_perk_fallback_resolves() -> None:
    # The ARM SLAVE M6 Bushnell case: roll lives in chapter 81's override,
    # obtained_perks.json rows the grant under chapter 82, and chapter 81's
    # roll object itself carries mention_chapter_num: "82" at the roll level.
    prose = _ProseDB().add("81", "irrelevant")
    spy = _SpyDirectoryIndex()
    obtained_perks_index = {("82", "ARM SLAVE M6 Bushnell"): {"cost": 0}}
    roll = _roll(
        perks=["ARM SLAVE M6 Bushnell"], constellation="Knowledge",
        mention_chapter_num="82",
    )
    result = verify_roll(
        "81", 0, roll,
        prose_loader=prose, directory_index=spy,
        obtained_perks_index=obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"
    assert spy.calls == []


def test_absent_from_index_perk_falls_through_to_paid_ladder() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    directory_index = _synthetic_directory_index()
    # No row anywhere (neither containing nor fallback chapter) for this
    # name — genuinely paid, untracked name, resolved via the ladder.
    roll = _roll(perks=["Test Perk"], constellation="Quality")
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=directory_index, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"


# ---------------------------------------------------------------------------
# no_evidence vs fail aggregation.
# ---------------------------------------------------------------------------

def test_no_evidence_status_when_quotes_empty_and_all_else_clean() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    roll = _roll(evidence_quotes=[])
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=_NO_DIRECTORY, obtained_perks_index={},
    )
    assert result["issues"] == []
    assert result["status"] == "no_evidence"


def test_fail_status_when_quotes_empty_but_perk_unresolved() -> None:
    prose = _ProseDB().add("1", "irrelevant")
    directory_index = _synthetic_directory_index()
    roll = _roll(
        perks=["Totally Unknown Perk"], constellation="Quality",
        evidence_quotes=[],
    )
    result = verify_roll(
        "1", 0, roll,
        prose_loader=prose, directory_index=directory_index, obtained_perks_index={},
    )
    # Absence of quotes never masks an independent perk/enum/position failure.
    assert result["status"] == "fail"
    assert [i["code"] for i in result["issues"]] == ["perk_unresolved"]

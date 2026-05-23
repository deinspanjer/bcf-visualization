from __future__ import annotations

import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_grab import (  # noqa: E402
    load_overrides as load_multi_grab_overrides,
    merge_paid_units,
)
from _common import _load_schema  # noqa: E402
from chapter_alignment import model_issues_by_chapter  # noqa: E402
from data_paths import DERIVED  # noqa: E402


CHAPTERS_JSON = DERIVED / "chapters.json"
OBTAINED_JSON = DERIVED / "obtained_perks.json"
PREDICTED_JSON = DERIVED / "predicted_rolls.json"
ROLL_FACTS_JSON = DERIVED / "roll_facts.json"
ROLL_VALIDATION_JSON = DERIVED / "roll_validation.json"
CHAPTER_FACTS_JSON = DERIVED / "chapter_facts.json"


def _chapter_nums() -> list[str]:
    chapters = json.loads(CHAPTERS_JSON.read_text())["chapters"]
    return [
        str(chapter["chapter_num"])
        for chapter in sorted(chapters, key=lambda c: tuple(c["sort_key"]))
    ]


def _predicted_roll_counts() -> Counter[str]:
    predicted = json.loads(PREDICTED_JSON.read_text())["predicted"]
    return Counter(str(roll["chapter_num"]) for roll in predicted)


def _required_paid_roll_counts() -> Counter[str]:
    obtained = sorted(
        json.loads(OBTAINED_JSON.read_text())["perks"],
        key=lambda p: p.get("epub_sequence", 0),
    )
    with contextlib.redirect_stdout(io.StringIO()):
        units, _stats = merge_paid_units(obtained, load_multi_grab_overrides())
    return Counter(str(unit["chapter_num"]) for unit in units)


def _known_attempt_counts() -> Counter[str]:
    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    return Counter(
        str(roll.get("mechanical_chapter_num") or roll["chapter_num"])
        for roll in roll_facts
        if roll.get("source_kind") != "trigger"
    )


def test_roll_validation_reports_global_roll_capacity_checks() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    checks = {
        str(check["chapter_num"]): check
        for check in validation["chapter_checks"]
    }
    predicted_counts = _predicted_roll_counts()
    paid_counts = _required_paid_roll_counts()
    attempt_counts = _known_attempt_counts()

    for chapter_num in _chapter_nums():
        check = checks[chapter_num]
        predicted = predicted_counts[chapter_num]
        paid = paid_counts[chapter_num]
        attempts = attempt_counts[chapter_num]
        issue_codes = {issue["code"] for issue in check["issues"]}

        assert check["predicted_roll_count"] == predicted
        assert check["required_paid_roll_count"] == paid
        assert check["known_attempt_count"] == attempts

        assert check["paid_roll_capacity_ok"] is (paid <= predicted)
        assert check["known_attempt_capacity_ok"] is (attempts <= predicted)
        assert (
            "paid_rolls_exceed_predicted_slots" in issue_codes
        ) is (paid > predicted)
        assert (
            "known_attempts_exceed_predicted_slots" in issue_codes
        ) is (attempts > predicted)


def test_roll_facts_use_evidence_quotes_contract() -> None:
    validator = Draft202012Validator(_load_schema("roll_facts"))
    valid_quote = {
        "text": "synthetic quote",
        "mention_chapter_num": "1",
        "mention_word_position": 10,
    }
    minimal_roll = {
        "roll_key": "fixture:0001",
        "roll_number": 1,
        "chapter_num": "1",
        "predicted_chapter_num": "1",
        "mechanical_chapter_num": "1",
        "mechanical_word_position": 100,
        "mechanical_cumulative_word_offset": 100,
        "mention_chapter_num": "1",
        "mention_word_position": 10,
        "display_position_policy": "source_marker",
        "display_chapter_num": "1",
        "display_word_position": 10,
        "display_cumulative_word_offset": 10,
        "source_chapter_num": "1",
        "source_roll_index": 1,
        "source_word_position": 10,
        "source_cumulative_word_offset": 10,
        "visible_chapter_nums": ["1"],
        "chapter_attribution_disagreement": False,
        "source": "curator_rolls",
        "source_kind": "miss",
        "outcome": "miss",
        "constellation": None,
        "constellation_revealed": False,
        "available_cp": 100,
        "banked_cp_after_roll": 100,
        "purchased_perks": [],
        "purchased_perk_cost_total": None,
        "purchased_perk_id": None,
        "purchased_perk_jump": None,
        "free_perks": [],
        "rolled_perk_name": None,
        "rolled_perk_instance": None,
        "rolled_perk_cost": 200,
        "miss_cost_estimate": 200,
        "predicted_word_position_epub": 100,
        "epub_word_offset_predicted": 130,
        "epub_word_offset_curated": 130,
        "predicted_char_offset_in_chapter": None,
        "anchor_char_offset_in_chapter": None,
        "evidence_kind": "curator_log",
        "evidence_quotes": [valid_quote],
        "raw": "Roll 1 miss",
        "source_row_index": 0,
        "roll_sequence_in_chapter": 1,
        "rolls_in_chapter": 1,
        "slot_source": "curator",
        "word_position": 10,
        "cumulative_word_offset": 10,
    }
    valid_doc = {
        "schema_version": 1,
        "_source": "test",
        "_method": "test",
        "_caveat": "test",
        "_counts": {
            "rolls_emitted": 1,
            "curator_rows": 1,
            "interpolated_rows": 0,
            "hits": 0,
            "misses": 1,
            "triggers": 0,
            "free_perks": 0,
        },
        "rolls": [minimal_roll],
    }

    assert list(validator.iter_errors(valid_doc)) == []

    invalid_doc = valid_doc | {
        "rolls": [minimal_roll | {"narrative_evidence": "legacy scalar"}],
    }
    errors = list(validator.iter_errors(invalid_doc))

    assert any("Additional properties" in error.message for error in errors)


def test_roll_validation_status_matches_blocking_model_issues() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    blocking = {
        "paid_rolls_exceed_predicted_slots",
        "known_attempts_exceed_predicted_slots",
        "cost_schedule_infeasible",
        "curated_hit_missing_perks",
    }

    for check in validation["chapter_checks"]:
        issue_codes = {
            issue["code"]
            for issue in check["issues"]
            if not issue.get("resolved")
        }
        raw_issue_codes = {issue["code"] for issue in check["issues"]}
        has_discrepancy = bool(issue_codes & blocking)
        assert check["has_discrepancy"] is has_discrepancy
        assert check["raw_has_discrepancy"] is bool(raw_issue_codes & blocking)
        assert check["status"] == ("discrepancy" if has_discrepancy else "ok")


def test_chapter_facts_embed_current_and_prior_model_discrepancy_flags() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    checks = {
        str(check["chapter_num"]): check
        for check in validation["chapter_checks"]
    }
    chapters = json.loads(CHAPTER_FACTS_JSON.read_text())["chapters"]
    alignment_issues = model_issues_by_chapter()

    first_discrepancy: str | None = None
    prior_discrepancy = False
    for chapter in chapters:
        chapter_num = str(chapter["chapter_num"])
        model = chapter["model_validation"]
        check = checks[chapter_num]
        has_alignment_issue = bool(alignment_issues.get(chapter_num))
        expected_current = bool(check["has_discrepancy"] or has_alignment_issue)
        expected_status = "discrepancy" if expected_current else check["status"]

        assert model["status"] == expected_status
        assert model["current_discrepancy"] is expected_current
        assert model["prior_discrepancy"] is prior_discrepancy
        assert model["first_discrepancy_chapter_num"] == first_discrepancy

        if expected_current:
            if first_discrepancy is None:
                first_discrepancy = chapter_num
            prior_discrepancy = True

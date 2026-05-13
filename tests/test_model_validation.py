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
from data_paths import DERIVED  # noqa: E402


CHAPTERS_JSON = DERIVED / "chapters.json"
OBTAINED_JSON = DERIVED / "obtained_perks.json"
PREDICTED_JSON = DERIVED / "predicted_rolls.json"
ROLL_FACTS_JSON = DERIVED / "roll_facts.json"
ROLL_VALIDATION_JSON = DERIVED / "roll_validation.json"
CHAPTER_FACTS_JSON = DERIVED / "chapter_facts.json"
ROLL_FACTS_SCHEMA_JSON = DERIVED / "_schemas" / "roll_facts.schema.json"


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
    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    schema = json.loads(ROLL_FACTS_SCHEMA_JSON.read_text())
    validator = Draft202012Validator(schema)
    quoted_roll = next(roll for roll in roll_facts if roll.get("evidence_quotes"))

    assert "narrative_evidence" not in quoted_roll
    assert quoted_roll["evidence_quotes"][0]["text"]

    invalid_doc = {
        "schema_version": 1,
        "_source": "test",
        "_method": "test",
        "_caveat": "test",
        "_counts": {
            "rolls_emitted": 1,
            "curator_rows": 1,
            "interpolated_rows": 0,
            "hits": 1,
            "misses": 0,
            "triggers": 0,
            "free_perks": 0,
        },
        "rolls": [dict(quoted_roll, narrative_evidence="legacy scalar")],
    }
    errors = list(validator.iter_errors(invalid_doc))

    assert any("Additional properties" in error.message for error in errors)


def test_roll_validation_status_matches_blocking_model_issues() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    blocking = {
        "paid_rolls_exceed_predicted_slots",
        "known_attempts_exceed_predicted_slots",
        "cost_schedule_infeasible",
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


def test_chapter_4_extra_attempt_discrepancy_is_curator_resolved() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    check = next(
        row for row in validation["chapter_checks"]
        if str(row["chapter_num"]) == "4"
    )
    resolved = [
        issue for issue in check["issues"]
        if issue["code"] == "known_attempts_exceed_predicted_slots"
    ]

    assert check["predicted_roll_count"] == 4
    assert check["known_attempt_count"] == 5
    assert check["known_attempt_capacity_ok"] is False
    assert check["raw_has_discrepancy"] is True
    assert check["has_discrepancy"] is False
    assert check["status"] == "ok"
    assert check["resolved_issue_codes"] == ["known_attempts_exceed_predicted_slots"]
    assert resolved and resolved[0]["severity"] == "info"
    assert resolved[0]["resolved"] is True
    assert resolved[0]["resolution_reason_code"] == "post_publication_edit_extra_roll"


def test_chapter_facts_embed_current_and_prior_model_discrepancy_flags() -> None:
    validation = json.loads(ROLL_VALIDATION_JSON.read_text())
    checks = {
        str(check["chapter_num"]): check
        for check in validation["chapter_checks"]
    }
    chapters = json.loads(CHAPTER_FACTS_JSON.read_text())["chapters"]

    first_discrepancy: str | None = None
    prior_discrepancy = False
    for chapter in chapters:
        chapter_num = str(chapter["chapter_num"])
        model = chapter["model_validation"]
        check = checks[chapter_num]

        assert model["status"] == check["status"]
        assert model["current_discrepancy"] is check["has_discrepancy"]
        assert model["prior_discrepancy"] is prior_discrepancy
        assert model["first_discrepancy_chapter_num"] == first_discrepancy

        if check["has_discrepancy"]:
            if first_discrepancy is None:
                first_discrepancy = chapter_num
            prior_discrepancy = True


def test_chapter_4_resolution_does_not_pollute_chapter_5_model_status() -> None:
    chapters = {
        str(chapter["chapter_num"]): chapter
        for chapter in json.loads(CHAPTER_FACTS_JSON.read_text())["chapters"]
    }

    assert chapters["4"]["model_validation"]["current_discrepancy"] is False
    assert chapters["4"]["model_validation"]["raw_current_discrepancy"] is True
    assert chapters["5"]["model_validation"]["prior_discrepancy"] is False
    assert chapters["5"]["model_validation"]["first_discrepancy_chapter_num"] is None

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from derive_roll_facts import _apply_issue_resolutions, _validation_status  # noqa: E402


def test_validation_status_treats_unresolved_blocking_issue_as_discrepancy() -> None:
    issues = [
        {
            "code": "known_attempts_exceed_predicted_slots",
            "severity": "error",
            "message": "fixture known attempts exceed predictions",
        },
        {
            "code": "ambiguous_schedule",
            "severity": "info",
            "message": "multiple feasible assignments",
        },
    ]

    assert _validation_status(issues) == ("discrepancy", True, True)


def test_validation_status_keeps_raw_discrepancy_after_resolution() -> None:
    issues, resolved_codes = _apply_issue_resolutions(
        [
            {
                "code": "known_attempts_exceed_predicted_slots",
                "severity": "error",
                "message": "fixture known attempts exceed predictions",
            }
        ],
        {
            "model_validation_resolution": {
                "status": "resolved",
                "resolved_issue_codes": ["known_attempts_exceed_predicted_slots"],
                "reason_code": "curator_confirmed",
                "note": "Fixture curator accepted the extra source attempt.",
            }
        },
    )

    assert resolved_codes == ["known_attempts_exceed_predicted_slots"]
    assert issues == [
        {
            "code": "known_attempts_exceed_predicted_slots",
            "severity": "info",
            "message": "fixture known attempts exceed predictions",
            "resolved": True,
            "resolution_reason_code": "curator_confirmed",
            "resolution_note": "Fixture curator accepted the extra source attempt.",
        }
    ]
    assert _validation_status(issues) == ("ok", False, True)


def test_validation_status_ignores_info_only_ambiguity() -> None:
    issues = [
        {
            "code": "ambiguous_schedule",
            "severity": "info",
            "message": "multiple feasible assignments",
        }
    ]

    assert _validation_status(issues) == ("ok", False, False)

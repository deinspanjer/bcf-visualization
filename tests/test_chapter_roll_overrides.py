from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.multi_grab import load_overrides
from scripts.derive_roll_facts import (
    _has_structural_roll_override,
    _restructure_curator_rows,
)


def test_roll_entries_must_use_dict_shape(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "1": {
                "rolls": [
                    ["Old Bare List"],
                ],
            },
        },
    }))

    with pytest.raises(ValueError, match="must be dict"):
        load_overrides(path)


def test_missing_override_file_has_no_legacy_fallback(tmp_path: Path) -> None:
    result = load_overrides(tmp_path / "chapter_roll_overrides.json")

    assert result == {"chapter_roll_overrides": {}}


def test_quote_only_override_preserves_existing_roll_shape() -> None:
    curator_rows = [
        (1, {"kind": "miss", "perks": [], "roll_number": 3}),
        (
            2,
            {
                "kind": "roll",
                "perks": [
                    {
                        "name": "Bling of War",
                        "source": "Macross",
                        "cost": 100,
                        "free": False,
                        "constellation": "Quality",
                    },
                ],
                "banked_before": 200,
                "banked_after": 100,
                "constellation": "Quality",
                "roll_number": 4,
            },
        ),
    ]
    override = {
        "rolls": [
            {"narrative_evidence": None},
            {"narrative_evidence": "That could be me someday."},
        ],
    }

    rows = _restructure_curator_rows("2", curator_rows, override)

    assert rows[0]["kind"] == "miss"
    assert rows[0].get("_narrative_evidence") is None
    assert rows[1]["kind"] == "roll"
    assert [p["name"] for p in rows[1]["perks"]] == ["Bling of War"]
    assert rows[1]["banked_after"] == 100
    assert rows[1]["_narrative_evidence"] == "That could be me someday."


def test_quote_only_override_is_not_structural() -> None:
    assert not _has_structural_roll_override({
        "rolls": [
            {"narrative_evidence": None},
            {"narrative_evidence": "That could be me someday."},
        ],
    })
    assert _has_structural_roll_override({
        "rolls": [
            {"narrative_evidence": None},
            {"outcome": "miss"},
        ],
    })

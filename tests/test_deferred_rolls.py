from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_grab import load_overrides, merge_paid_units  # noqa: E402
from derive_roll_facts import (  # noqa: E402
    _direct_override_rows,
    _override_needs_direct_rows,
    _restructure_curator_rows,
)
from build_chapter_facts import _skipped_predicted_roll_markers  # noqa: E402


def _perk(
    chapter_num: str,
    name: str,
    *,
    cost: int = 100,
    free: bool = False,
    seq: int = 1,
) -> dict:
    return {
        "epub_sequence": seq,
        "chapter_num": chapter_num,
        "chapter_full_title": f"{chapter_num} Test",
        "perk_name": name,
        "classification": None,
        "jump": "Test Jump",
        "cost": cost,
        "cost_text": "Free" if free else str(cost),
        "free": free,
        "perk_text": "",
        "constellation": "Toolkits",
    }


def test_override_loader_defaults_deferred_roll_fields(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "5": {
                "rolls": [
                    {"perks": ["Same Chapter"], "outcome": "hit"},
                    {
                        "perks": ["Later Chapter"],
                        "outcome": "hit",
                        "mention_chapter_num": "6",
                        "mention_word_position": 123,
                    },
                ],
            },
        },
    }))

    rolls = load_overrides(path)["chapter_roll_overrides"]["5"]["rolls"]

    assert rolls[0]["mention_chapter_num"] == "5"
    assert rolls[0]["mention_word_position"] is None
    assert rolls[0]["display_position_policy"] == "mechanical"
    assert rolls[1]["mention_chapter_num"] == "6"
    assert rolls[1]["mention_word_position"] == 123
    assert rolls[1]["display_position_policy"] == "mechanical"


def test_override_loader_preserves_skipped_roll_slots(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "8.1": {
                "rolls": [
                    {"skipped": True},
                ],
            },
        },
    }))

    roll = load_overrides(path)["chapter_roll_overrides"]["8.1"]["rolls"][0]

    assert roll["skipped"] is True


def test_skipped_roll_override_exports_predicted_slot_marker() -> None:
    markers = _skipped_predicted_roll_markers(
        "9",
        [
            {"roll_number": 34, "word_position": 102000, "chapter_num": "9"},
            {"roll_number": 35, "word_position": 104000, "chapter_num": "9"},
        ],
        {
            "rolls": [
                {"skipped": False},
                {"skipped": True},
            ],
        },
        chapter_cp_start=100000,
    )

    assert markers == [
        {
            "slot_index": 2,
            "roll_number": 35,
            "mechanical_chapter_num": "9",
            "mechanical_word_position": 4000,
            "mechanical_cumulative_word_offset": 104000,
            "predicted_word_position_epub": 104000,
            "reason": "skipped_to_align_narrative",
        },
    ]


def test_merge_paid_units_moves_deferred_hit_to_mechanical_chapter() -> None:
    obtained = [
        _perk("1", "Trigger Perk", cost=100, seq=1),
        _perk("2", "Fashion", cost=200, seq=2),
        _perk("2", "Free Tie", cost=0, free=True, seq=2),
    ]
    overrides = {
        "chapter_roll_overrides": {
            "1": {
                "rolls": [
                    {
                        "perks": [],
                        "outcome": "miss",
                    },
                    {
                        "perks": ["Fashion", "Free Tie"],
                        "outcome": "hit",
                        "mention_chapter_num": "2",
                        "display_position_policy": "mechanical",
                    },
                ],
            },
        },
    }

    with contextlib.redirect_stdout(io.StringIO()):
        units, _stats = merge_paid_units(obtained, overrides)

    assert len(units) == 1
    unit = units[0]
    assert unit["chapter_num"] == "1"
    assert unit["mention_chapter_num"] == "2"
    assert unit["display_position_policy"] == "mechanical"
    assert [p["perk_name"] for p in unit["paid"]] == ["Fashion"]
    assert [p["perk_name"] for p in unit["free_perks"]] == ["Free Tie"]


def test_direct_deferred_metadata_preserves_unmentioned_source_rows() -> None:
    curator_rows = [
        (
            10,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 200,
                "banked_after": 200,
                "roll_number": 27,
                "raw": "Roll 27",
            },
        ),
        (
            11,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 300,
                "banked_after": 400,
                "roll_number": 28,
                "raw": "Roll 28",
            },
        ),
        (
            12,
            {
                "kind": "roll",
                "perks": [{"name": "Life Fiber Spool"}],
                "banked_before": 400,
                "banked_after": 0,
                "roll_number": 29,
                "raw": "Roll 29",
            },
        ),
    ]
    override = {
        "rolls": [
            {
                "mention_chapter_num": "9",
                "display_position_policy": "mechanical",
            },
        ],
    }

    rows = _direct_override_rows("8.1", curator_rows, override, {})

    assert [row["roll_number"] for row in rows] == [27, 28, 29]
    assert rows[0]["_mention_chapter_num"] == "9"
    assert rows[0]["_display_position_policy"] == "mechanical"
    assert "_mention_chapter_num" not in rows[1]
    assert "_mention_chapter_num" not in rows[2]


def test_direct_deferred_rows_can_use_cross_chapter_source_template() -> None:
    quote = {
        "text": "The Size constellation passed by without any successful connections.",
        "mention_chapter_num": "10",
        "mention_word_position": 294,
    }

    rows = _direct_override_rows(
        "9",
        [],
        {
            "rolls": [
                {
                    "outcome": "miss",
                    "source_roll_number": 33,
                    "mention_chapter_num": "10",
                    "mention_word_position": 294,
                    "display_position_policy": "mention",
                    "evidence_quotes": [quote],
                }
            ]
        },
        {},
        {
            33: (
                34,
                {
                    "kind": "miss",
                    "roll_number": 33,
                    "banked_before": 100,
                    "banked_after": 100,
                    "constellation": "Size",
                    "raw": "Roll 33 (100): Size -> Miss -> (100)",
                },
            )
        },
    )

    assert rows == [
        {
            "_source_idx": 34,
            "_override_origin": 0,
            "_override_direct": True,
            "_curator_added": False,
            "_mention_chapter_num": "10",
            "_mention_word_position": 294,
            "_display_position_policy": "mention",
            "_evidence_quotes": [quote],
            "kind": "miss",
            "perks": [],
            "banked_before": 100,
            "banked_after": 100,
            "constellation": "Size",
            "constellation_revealed": False,
            "roll_number": 33,
            "raw": "Roll 33 (100): Size -> Miss -> (100)",
            "_source_roll_number": 33,
        }
    ]


def test_source_roll_assignment_uses_direct_rows_even_in_same_chapter() -> None:
    override = {
        "rolls": [
            {
                "source_roll_number": 38,
                "mention_chapter_num": "10",
                "mention_word_position": 6755,
                "display_position_policy": "mention",
                "evidence_quotes": [
                    {
                        "text": "quoted evidence",
                        "mention_chapter_num": "10",
                        "mention_word_position": 6755,
                    }
                ],
            }
        ]
    }
    curator_rows = [
        (
            39,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 300,
                "banked_after": 300,
                "roll_number": 38,
                "constellation": "Alchemy",
                "raw": "Roll 38",
            },
        )
    ]

    assert _override_needs_direct_rows("10", override, curator_rows)

    rows = _direct_override_rows("10", curator_rows, override, {})

    assert rows[0]["roll_number"] == 38
    assert rows[0]["constellation"] == "Alchemy"
    assert rows[0]["_mention_word_position"] == 6755
    assert rows[0]["_display_position_policy"] == "mention"


def test_source_roll_assignment_inherits_source_hit_without_redeclared_perks() -> None:
    override = {
        "rolls": [
            {
                "source_roll_number": 37,
                "mention_chapter_num": "10",
                "mention_word_position": 6755,
                "display_position_policy": "mention",
                "evidence_quotes": [
                    {
                        "text": "Stylish Mechanic quote",
                        "mention_chapter_num": "10",
                        "mention_word_position": 6755,
                    }
                ],
            }
        ]
    }
    curator_rows = [
        (
            38,
            {
                "kind": "roll",
                "perks": [
                    {
                        "name": "Stylish Mechanic",
                        "cost": 100,
                        "constellation": "Quality",
                    }
                ],
                "banked_before": 300,
                "banked_after": 200,
                "roll_number": 37,
                "constellation": "Quality",
                "raw": "Roll 37",
            },
        )
    ]

    rows = _direct_override_rows("10", curator_rows, override, {})

    assert rows[0]["kind"] == "roll"
    assert rows[0]["roll_number"] == 37
    assert rows[0]["perks"][0]["name"] == "Stylish Mechanic"
    assert rows[0]["constellation"] == "Quality"


def test_extra_miss_override_preserves_existing_source_rows() -> None:
    curator_rows = [
        (
            31,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 100,
                "banked_after": 100,
                "roll_number": 30,
                "raw": "Roll 30",
            },
        ),
    ]
    override = {
        "rolls": [
            {
                "perks": [],
                "outcome": None,
                "word_position": None,
                "evidence_quotes": [],
            },
            {
                "perks": [],
                "outcome": "miss",
                "word_position": None,
                "evidence_quotes": [],
            },
        ],
    }

    rows = _restructure_curator_rows("9", curator_rows, override)

    assert [row["kind"] for row in rows] == ["miss", "miss"]
    assert rows[0]["roll_number"] == 30
    assert rows[0]["_override_origin"] is None
    assert rows[1]["roll_number"] is None
    assert rows[1]["_override_origin"] == 1


def test_same_chapter_override_with_unhosted_perks_uses_direct_rows() -> None:
    curator_rows = [
        (
            31,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 100,
                "banked_after": 100,
                "roll_number": 30,
                "raw": "Roll 30",
            },
        ),
    ]
    override = {
        "rolls": [
            {"outcome": "miss", "perks": []},
            {"outcome": "hit", "perks": ["Garment Gloves"]},
        ],
    }

    assert _override_needs_direct_rows("9", override, curator_rows)


def test_mixed_explicit_miss_and_hit_override_uses_direct_rows() -> None:
    curator_rows = [
        (31, {"kind": "miss", "perks": [], "roll_number": 30}),
        (
            32,
            {
                "kind": "roll",
                "perks": [{"name": "Garment Gloves"}],
                "roll_number": 31,
            },
        ),
        (
            33,
            {
                "kind": "roll",
                "perks": [{"name": "Alchemy"}],
                "roll_number": 32,
            },
        ),
    ]
    override = {
        "rolls": [
            {"outcome": None, "perks": []},
            {"outcome": "miss", "perks": []},
            {"outcome": "miss", "perks": []},
            {"outcome": "hit", "perks": ["Garment Gloves"]},
            {"outcome": "hit", "perks": ["Alchemy"]},
        ],
    }

    assert _override_needs_direct_rows("9", override, curator_rows)


def test_skipped_override_consumes_predicted_slot_without_roll_fact() -> None:
    curator_rows = [
        (
            31,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 100,
                "banked_after": 100,
                "roll_number": 30,
                "raw": "Roll 30",
            },
        ),
    ]
    override = {
        "rolls": [
            {"outcome": None, "perks": [], "skipped": True},
        ],
    }

    rows = _direct_override_rows("9", curator_rows, override, {})

    assert [row["kind"] for row in rows] == ["skipped", "miss"]
    assert rows[0]["_override_origin"] == 0
    assert rows[1]["roll_number"] == 30


def test_skipped_slot_quote_metadata_does_not_attach_to_source_roll() -> None:
    curator_rows = [
        (
            31,
            {
                "kind": "miss",
                "perks": [],
                "banked_before": 100,
                "banked_after": 100,
                "roll_number": 30,
                "raw": "Roll 30",
            },
        ),
        (
            32,
            {
                "kind": "roll",
                "perks": [{"name": "Life Fiber Spool"}],
                "banked_before": 400,
                "banked_after": 0,
                "roll_number": 31,
                "raw": "Roll 31",
            },
        ),
    ]
    override = {
        "rolls": [
            {"skipped": True},
            {},
            {
                "skipped": True,
                "evidence_quotes": [
                    {
                        "text": "Life Fibers",
                        "mention_chapter_num": "9",
                        "mention_word_position": 1728,
                    }
                ],
            },
        ],
    }

    rows = _direct_override_rows("8.1", curator_rows, override, {})

    emitted = [row for row in rows if row["kind"] != "skipped"]
    assert emitted[0]["roll_number"] == 30
    assert emitted[0].get("_evidence_quotes") in (None, [])
    assert emitted[1]["roll_number"] == 31
    assert emitted[1].get("_evidence_quotes") in (None, [])


def test_merge_paid_units_ignores_unassigned_zero_cost_paid_perks() -> None:
    obtained = [
        _perk("1", "Discounted Trigger", cost=0, seq=1),
        _perk("1", "Narrative Hit", cost=100, seq=2),
    ]
    overrides = {
        "chapter_roll_overrides": {
            "1": {
                "rolls": [
                    {
                        "perks": ["Narrative Hit"],
                        "outcome": "hit",
                    },
                ],
            },
        },
    }

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        units, _stats = merge_paid_units(obtained, overrides)

    assert stdout.getvalue() == ""
    assert len(units) == 1
    assert [p["perk_name"] for p in units[0]["paid"]] == ["Narrative Hit"]

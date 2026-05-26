from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.multi_grab import load_overrides, merge_paid_units  # noqa: E402
from scripts.derive_roll_facts import (  # noqa: E402
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
            {"evidence_quotes": []},
            {
                "evidence_quotes": [
                    {
                        "text": "That could be me someday.",
                        "mention_chapter_num": "2",
                        "mention_word_position": 123,
                    },
                    {
                        "text": "A second proof passage.",
                        "mention_chapter_num": "2",
                        "mention_word_position": 456,
                    },
                ],
            },
        ],
    }

    rows = _restructure_curator_rows("2", curator_rows, override)

    assert rows[0]["kind"] == "miss"
    assert rows[0].get("_evidence_quotes") == []
    assert rows[1]["kind"] == "roll"
    assert [p["name"] for p in rows[1]["perks"]] == ["Bling of War"]
    assert rows[1]["banked_after"] == 100
    assert rows[1]["_evidence_quotes"] == [
        {
            "text": "That could be me someday.",
            "mention_chapter_num": "2",
            "mention_word_position": 123,
        },
        {
            "text": "A second proof passage.",
            "mention_chapter_num": "2",
            "mention_word_position": 456,
        },
    ]


def test_constellation_only_override_patches_matching_roll_slot() -> None:
    curator_rows = [
        (1, {"kind": "miss", "perks": [], "constellation": "Time", "roll_number": 3}),
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
        (3, {"kind": "miss", "perks": [], "constellation": None, "roll_number": 5}),
    ]
    override = {
        "rolls": [
            {},
            {},
            {
                "constellation": "Capstone",
                "evidence_quotes": [
                    {
                        "text": "The Forge missed a connection to that new constellation.",
                        "mention_chapter_num": "2",
                        "mention_word_position": 300,
                    },
                ],
            },
        ],
    }

    rows = _restructure_curator_rows("2", curator_rows, override)

    assert rows[1]["kind"] == "roll"
    assert rows[1]["constellation"] == "Quality"
    assert "_evidence_quotes" not in rows[1]
    assert rows[2]["kind"] == "miss"
    assert rows[2]["roll_number"] == 5
    assert rows[2]["constellation"] == "Capstone"
    assert rows[2]["constellation_revealed"]
    assert rows[2]["_evidence_quotes"] == [
        {
            "text": "The Forge missed a connection to that new constellation.",
            "mention_chapter_num": "2",
            "mention_word_position": 300,
        },
    ]


def test_quote_only_override_is_not_structural() -> None:
    assert not _has_structural_roll_override({
        "rolls": [
            {"evidence_quotes": []},
            {
                "evidence_quotes": [
                    {
                        "text": "That could be me someday.",
                        "mention_chapter_num": "2",
                        "mention_word_position": 123,
                    },
                ],
            },
        ],
    })
    assert _has_structural_roll_override({
        "rolls": [
            {"evidence_quotes": []},
            {"outcome": "miss"},
        ],
    })
    assert not _has_structural_roll_override({
        "rolls": [
            {
                "mention_chapter_num": "2",
                "display_position_policy": "mechanical",
                "evidence_quotes": [
                    {
                        "text": "same-chapter quote",
                        "mention_chapter_num": "2",
                        "mention_word_position": 123,
                    },
                ],
            },
        ],
    }, "2")


def test_quote_only_override_does_not_replace_multi_grab_units() -> None:
    obtained = [
        {
            "chapter_num": "2",
            "perk_name": "Bling of War",
            "cost": 100,
            "free": False,
            "epub_sequence": 1,
            "jump": "Macross",
        },
        {
            "chapter_num": "2",
            "perk_name": "Alchemist",
            "cost": 200,
            "free": False,
            "epub_sequence": 2,
            "jump": "Secrets of Evermore",
        },
    ]
    overrides = {
        "chapter_roll_overrides": {
            "2": {
                "rolls": [
                    {
                        "evidence_quotes": [
                            {
                                "text": (
                                    "I felt my power try and fail to latch onto a mote "
                                    "from a new constellation."
                                ),
                                "mention_chapter_num": "2",
                                "mention_word_position": 10,
                            },
                        ],
                    },
                ],
            },
        },
    }

    units, stats = merge_paid_units(obtained, overrides)

    assert stats["curated_chapters"] == 0
    assert [u["paid"][0]["perk_name"] for u in units] == [
        "Bling of War",
        "Alchemist",
    ]


def test_source_miss_metadata_does_not_replace_paid_units(capsys: pytest.CaptureFixture[str]) -> None:
    obtained = [
        {
            "chapter_num": "2",
            "perk_name": "Bling of War",
            "cost": 100,
            "free": False,
            "epub_sequence": 1,
            "jump": "Macross",
        },
        {
            "chapter_num": "2",
            "perk_name": "Storage Chest",
            "cost": 0,
            "free": True,
            "epub_sequence": 1,
            "jump": "Macross",
        },
        {
            "chapter_num": "2",
            "perk_name": "Alchemist",
            "cost": 200,
            "free": False,
            "epub_sequence": 2,
            "jump": "Secrets of Evermore",
        },
    ]
    overrides = {
        "chapter_roll_overrides": {
            "2": {
                "rolls": [
                    {
                        "evidence_quotes": [
                            {
                                "text": "The first connection landed.",
                                "mention_chapter_num": "2",
                                "mention_word_position": 10,
                            },
                        ],
                    },
                    {
                        "outcome": "miss",
                        "source_roll_number": 3,
                        "evidence_quotes": [
                            {
                                "text": "The later source roll missed.",
                                "mention_chapter_num": "3",
                                "mention_word_position": 20,
                            },
                        ],
                    },
                ],
            },
        },
    }

    units, stats = merge_paid_units(obtained, overrides)

    assert "override drops paid perk" not in capsys.readouterr().out
    assert stats["curated_chapters"] == 0
    assert [p["perk_name"] for unit in units for p in unit["paid"]] == [
        "Bling of War",
        "Alchemist",
    ]
    assert [p["perk_name"] for p in units[0]["free_perks"]] == ["Storage Chest"]

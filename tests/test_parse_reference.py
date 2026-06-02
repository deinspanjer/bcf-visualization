from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from parse_reference import parse_obtained_perks  # noqa: E402


def _reference_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Obtained Perks"
    ws.append([
        "EPUB Sequence",
        "Chapter",
        "Perk",
        "Classification",
        "Jump",
        "Cost",
        "Text",
    ])
    return wb


def test_obtained_perks_corrects_interlude_gregor_shawn_chapter_number() -> None:
    wb = _reference_workbook()
    ws = wb["Obtained Perks"]
    ws.append([
        138,
        "95 Interlude Gregor - Shawn",
        "Minor Blessing Zeus - Lightning",
        "Perk",
        "Percy Jackson",
        "100",
        "fixture text",
    ])
    ws.append([
        139,
        "95 Instant Replay",
        "Unrelated Fixture",
        "Perk",
        "Fixture Jump",
        "100",
        "fixture text",
    ])

    constellation_idx = {
        "exact": {},
        "norm": {},
        "name_only": {},
    }
    perks = parse_obtained_perks(wb, constellation_idx, {})

    assert [perk.chapter_num for perk in perks] == ["95.5", "95"]

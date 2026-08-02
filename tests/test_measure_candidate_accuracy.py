from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from measure_candidate_accuracy import derive_stub_chapters  # noqa: E402


def _overrides_doc(chapters: dict) -> dict:
    return {"chapter_roll_overrides": chapters}


def _curated_roll(evidence_quotes=None) -> dict:
    return {
        "perks": [], "outcome": "miss", "constellation": None,
        "word_position": None, "evidence_quotes": evidence_quotes or [],
    }


def test_stub_chapter_with_all_empty_evidence_quotes_is_derived() -> None:
    doc = _overrides_doc({
        "1": {"rolls": [_curated_roll(evidence_quotes=[])]},
        "2": {"rolls": [_curated_roll(evidence_quotes=[
            {"text": "sample", "mention_chapter_num": "2", "mention_word_position": 10},
        ])]},
    })
    assert derive_stub_chapters(doc) == {"1"}

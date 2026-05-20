"""Stability and sensitivity tests for per-chapter alignment fingerprints."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from predict_rolls import (  # noqa: E402
    chapter_alignment_fingerprint,
    compute_alignment_fingerprints,
)


ALIGNMENT_JSON = ROOT / "data" / "derived" / "chapter_alignment_fingerprints.json"


def test_fingerprint_format_and_population():
    doc = json.loads(ALIGNMENT_JSON.read_text())
    fps = doc["chapter_alignment_fingerprints"]
    assert doc["_count"] == len(fps)
    assert fps, "expected at least one chapter with predicted rolls"
    for cn, h in fps.items():
        assert h.startswith("sha256:")
        assert len(h) == len("sha256:") + 16
        assert cn.replace(".", "").isdigit()


def test_fingerprint_deterministic_for_same_inputs():
    # Two passes over the same input must produce identical hashes.
    rolls = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
        {"roll_number": 2, "cp_offset": 4000, "epub_offset": 4253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(rolls) == chapter_alignment_fingerprint(rolls)


def test_fingerprint_changes_when_cp_offset_shifts():
    a = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    b = [
        {"roll_number": 1, "cp_offset": 2001, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(a) != chapter_alignment_fingerprint(b)


def test_fingerprint_changes_when_epub_offset_shifts():
    a = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    b = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2254,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(a) != chapter_alignment_fingerprint(b)


def test_fingerprint_changes_when_regime_shifts():
    a = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    b = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 2, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(a) != chapter_alignment_fingerprint(b)


def test_fingerprint_changes_when_threshold_shifts():
    a = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    b = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 200,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(a) != chapter_alignment_fingerprint(b)


def test_fingerprint_changes_when_roll_added():
    a = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    b = a + [
        {"roll_number": 2, "cp_offset": 4000, "epub_offset": 4253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
    ]
    assert chapter_alignment_fingerprint(a) != chapter_alignment_fingerprint(b)


def test_compute_alignment_fingerprints_groups_by_chapter():
    rolls = [
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "1"},
        {"roll_number": 2, "cp_offset": 4000, "epub_offset": 4253,
         "cp_rule_regime": 1, "roll_trigger_cp_threshold": 100,
         "chapter_num": "2"},
    ]
    fps = compute_alignment_fingerprints(rolls)
    assert set(fps.keys()) == {"1", "2"}
    # Different chapters → different per-chapter sequences → different hashes.
    assert fps["1"] != fps["2"]


def test_disk_fingerprints_match_recomputation():
    # The on-disk file must equal a fresh recomputation from
    # predicted_rolls.json — the contract that lets the realignment
    # guard trust the file.
    disk = json.loads(ALIGNMENT_JSON.read_text())["chapter_alignment_fingerprints"]
    predicted = json.loads(
        (ROOT / "data" / "derived" / "predicted_rolls.json").read_text()
    )["predicted"]
    recomputed = compute_alignment_fingerprints(predicted)
    assert disk == recomputed

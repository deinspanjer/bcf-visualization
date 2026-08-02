from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.chapter_roll_overrides_io import (  # noqa: E402
    DEFAULT_DOC,
    load_chapter_roll_overrides_doc,
)


def test_missing_curated_by_raises(tmp_path: Path) -> None:
    """D-01/D-12: an existing chapter entry missing curated_by is a hard
    validation error at load time, never a silent default."""
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "1": {"rolls": []},
        },
    }))

    with pytest.raises(ValueError, match="curated_by"):
        load_chapter_roll_overrides_doc(path)


def test_invalid_curated_by_enum_raises(tmp_path: Path) -> None:
    """D-01: curated_by is enum ["human", "agent"] — anything else is a
    validation error, not a value the loader passes through."""
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "1": {"curated_by": "robot", "rolls": []},
        },
    }))

    with pytest.raises(ValueError, match="curated_by"):
        load_chapter_roll_overrides_doc(path)


def test_live_corpus_loads_and_all_118_entries_are_human() -> None:
    """D-12: loading the live 118-chapter corpus must succeed, and every
    existing entry must carry curated_by == "human" after the bulk stamp.

    Loads the real committed data/manual/chapter_roll_overrides.json
    directly (it is git-tracked, not gitignored) rather than a synthetic
    fixture, formalizing this phase's manual verify step as a test.
    """
    live_path = ROOT / "data" / "manual" / "chapter_roll_overrides.json"

    doc = load_chapter_roll_overrides_doc(live_path)

    entries = doc["chapter_roll_overrides"]
    assert len(entries) == 118
    assert all(entry.get("curated_by") == "human" for entry in entries.values())


def test_missing_file_returns_default_without_validation(tmp_path: Path) -> None:
    """Mirrors test_missing_override_file_has_no_legacy_fallback against
    the new module directly: a genuinely absent file defaults cleanly
    without any schema validation running (nothing on disk to validate)."""
    result = load_chapter_roll_overrides_doc(tmp_path / "chapter_roll_overrides.json")

    assert result == DEFAULT_DOC

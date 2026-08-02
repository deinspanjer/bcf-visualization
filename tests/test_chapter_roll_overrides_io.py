from __future__ import annotations

import json
import re
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
    write_chapter_roll_overrides_doc,
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


# ---------------------------------------------------------------------------
# Gap-closure follow-up (CINF-01): a validated writer, and a regression
# guard proving every write path to chapter_roll_overrides.json is now
# routed through it.
# ---------------------------------------------------------------------------

def test_writer_rejects_missing_curated_by(tmp_path: Path) -> None:
    """The writer validates before touching disk -- an entry missing
    curated_by must raise and must NOT leave a partially-written file."""
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {"chapter_roll_overrides": {"1": {"rolls": []}}}

    with pytest.raises(ValueError, match="curated_by"):
        write_chapter_roll_overrides_doc(doc, path)

    assert not path.exists()


def test_writer_round_trip_matches_load(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {
        "chapter_roll_overrides": {
            "1": {"curated_by": "human", "rolls": [{"perks": ["A"]}]},
        }
    }

    write_chapter_roll_overrides_doc(doc, path)
    reloaded = load_chapter_roll_overrides_doc(path)

    assert reloaded == doc


def test_writer_preserves_non_ascii_characters_verbatim(tmp_path: Path) -> None:
    """D-13 (deferred-items.md, phase 01): the writer must use
    ensure_ascii=False -- a bare json.dumps() default would escape every
    literal unicode character (en-dash, ellipsis, curly quotes) in
    evidence_quotes into \\uXXXX sequences, producing spurious whole-file
    diffs across hand-curated data on every re-stamp."""
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {
        "chapter_roll_overrides": {
            "1": {
                "curated_by": "human",
                "rolls": [{
                    "evidence_quotes": [
                        {"text": "The pre–installed system… “worked”."}
                    ],
                }],
            },
        }
    }

    write_chapter_roll_overrides_doc(doc, path)
    raw = path.read_text(encoding="utf-8")

    assert "–" in raw  # en-dash, literal
    assert "…" in raw  # ellipsis, literal
    assert "“" in raw  # left curly quote, literal
    assert "\\u" not in raw  # never escaped


def test_writer_round_trip_on_live_corpus_is_byte_identical(tmp_path: Path) -> None:
    """The single most important check in this task (per the gap-closure
    objective): loading the real 118-chapter hand-curated corpus through
    the loader and writing it straight back through the new writer must
    reproduce the file byte-for-byte. This is what proves the
    formatting/escaping convention matches exactly -- a regression here
    would silently damage hand-curated data on the next re-stamp run."""
    live_path = ROOT / "data" / "manual" / "chapter_roll_overrides.json"
    original = live_path.read_bytes()

    doc = load_chapter_roll_overrides_doc(live_path)
    scratch_path = tmp_path / "chapter_roll_overrides.json"
    write_chapter_roll_overrides_doc(doc, scratch_path)

    assert scratch_path.read_bytes() == original


def test_no_bare_write_path_to_overrides_file() -> None:
    """Regression guard: the only sanctioned way to write
    data/manual/chapter_roll_overrides.json is
    chapter_roll_overrides_io.write_chapter_roll_overrides_doc (which
    delegates to _common.write_validated_json). This closes a gap where
    five scripts/*.py modules read/wrote the file directly with bare
    json.loads/json.dumps/write_text, bypassing schema validation
    entirely -- two of them wrote the corpus back unvalidated and with
    ensure_ascii defaulting to True, corrupting unicode in hand-curated
    evidence quotes on every run (deferred-items.md, phase 01).

    This is a durable, grep-style source assertion (not an exhaustive
    behavioral test) precisely because the failure mode it guards
    against is a *future* contributor adding a sixth bare write path --
    it should fail loudly and immediately, without needing a fixture
    that exercises the new code.
    """
    scripts_dir = SCRIPTS
    # Every module-level Path constant across scripts/ that is bound to
    # the overrides file's path, keyed by the constant's name.
    path_var_pattern = re.compile(
        r'^(\w+)\s*=\s*.*["\']chapter_roll_overrides\.json["\']',
        re.MULTILINE,
    )
    overrides_path_vars: set[str] = set()
    for py_file in scripts_dir.glob("*.py"):
        overrides_path_vars.update(path_var_pattern.findall(py_file.read_text()))

    assert overrides_path_vars, (
        "expected to find at least one *_PATH constant pointing at "
        "chapter_roll_overrides.json in scripts/ -- did path constants "
        "move or get renamed?"
    )

    write_call_pattern = re.compile(r"(\w+)\.write_text\(")
    offenders: list[str] = []
    for py_file in scripts_dir.glob("*.py"):
        if py_file.name == "_common.py":
            continue  # the one sanctioned writer implementation lives here
        text = py_file.read_text()
        for match in write_call_pattern.finditer(text):
            if match.group(1) in overrides_path_vars:
                offenders.append(f"{py_file.name}: {match.group(0)}")

    assert not offenders, (
        "found a bare .write_text() call writing directly to a path bound "
        "to chapter_roll_overrides.json -- route through "
        "chapter_roll_overrides_io.write_chapter_roll_overrides_doc "
        f"instead: {offenders}"
    )

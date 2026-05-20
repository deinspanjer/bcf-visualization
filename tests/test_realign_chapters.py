"""Smoke tests for the realign CLI tool's accept-all path."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def test_yes_flag_restamps_every_mismatched_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    # Build a tmp world with one mismatched chapter.
    overrides = tmp_path / "chapter_roll_overrides.json"
    fingerprints = tmp_path / "chapter_alignment_fingerprints.json"
    predicted = tmp_path / "predicted_rolls.json"
    _write(overrides, {
        "chapter_roll_overrides": {
            "65": {
                "_fingerprint": "sha256:old0000000000000",
                "rolls": [{"perks": [], "outcome": "miss"}],
            },
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "65": "sha256:new0000000000000",
        }
    })
    _write(predicted, {
        "predicted": [
            {"roll_number": 100, "cp_offset": 130000, "epub_offset": 200000,
             "chapter_num": "65", "cp_rule_regime": 1,
             "roll_trigger_cp_threshold": 100},
        ]
    })

    # Redirect the modules' path constants.
    import chapter_alignment
    importlib.reload(chapter_alignment)
    monkeypatch.setattr(chapter_alignment, "OVERRIDES_PATH", overrides)
    monkeypatch.setattr(chapter_alignment, "FINGERPRINTS_PATH", fingerprints)

    import realign_chapters
    importlib.reload(realign_chapters)
    monkeypatch.setattr(realign_chapters, "OVERRIDES_PATH", overrides)
    monkeypatch.setattr(realign_chapters, "FINGERPRINTS_PATH", fingerprints)
    monkeypatch.setattr(realign_chapters, "ANCHOR_FIELD", "_fingerprint")

    import predict_rolls
    monkeypatch.setattr(predict_rolls, "OUT", predicted)

    monkeypatch.setattr(sys, "argv", ["realign_chapters.py", "--yes"])
    realign_chapters.main()

    out = capsys.readouterr().out
    assert "chapter 65" in out
    assert "re-stamped chapter 65" in out
    assert "1 re-stamped" in out

    saved = json.loads(overrides.read_text())
    assert (
        saved["chapter_roll_overrides"]["65"]["_fingerprint"]
        == "sha256:new0000000000000"
    )


def test_yes_flag_is_noop_when_no_mismatches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    overrides = tmp_path / "chapter_roll_overrides.json"
    fingerprints = tmp_path / "chapter_alignment_fingerprints.json"
    _write(overrides, {
        "chapter_roll_overrides": {
            "65": {"_fingerprint": "sha256:abc0000000000000", "rolls": []},
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "65": "sha256:abc0000000000000",
        }
    })

    import chapter_alignment
    importlib.reload(chapter_alignment)
    monkeypatch.setattr(chapter_alignment, "OVERRIDES_PATH", overrides)
    monkeypatch.setattr(chapter_alignment, "FINGERPRINTS_PATH", fingerprints)

    import realign_chapters
    importlib.reload(realign_chapters)
    monkeypatch.setattr(realign_chapters, "OVERRIDES_PATH", overrides)
    monkeypatch.setattr(realign_chapters, "FINGERPRINTS_PATH", fingerprints)

    monkeypatch.setattr(sys, "argv", ["realign_chapters.py", "--yes"])
    realign_chapters.main()
    assert "no chapters need re-stamping" in capsys.readouterr().out

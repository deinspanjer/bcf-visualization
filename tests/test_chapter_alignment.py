"""Tests for the re-alignment guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _write(p: Path, doc: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n")


def _patched_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Redirect chapter_alignment's path constants to a tmp area."""
    import chapter_alignment
    overrides = tmp_path / "chapter_roll_overrides.json"
    fingerprints = tmp_path / "chapter_alignment_fingerprints.json"
    monkeypatch.setattr(chapter_alignment, "OVERRIDES_PATH", overrides)
    monkeypatch.setattr(chapter_alignment, "FINGERPRINTS_PATH", fingerprints)
    return overrides, fingerprints


def test_check_passes_when_all_stamps_match(tmp_path, monkeypatch):
    import chapter_alignment
    overrides, fingerprints = _patched_paths(tmp_path, monkeypatch)
    _write(overrides, {
        "chapter_roll_overrides": {
            "1": {"_fingerprint": "sha256:aaaa000000000000", "rolls": []},
            "65": {"_fingerprint": "sha256:bbbb000000000000", "rolls": []},
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "1": "sha256:aaaa000000000000",
            "65": "sha256:bbbb000000000000",
        }
    })
    assert chapter_alignment.check() == []
    chapter_alignment.fail_if_misaligned()  # should not raise


def test_check_reports_a_mismatch(tmp_path, monkeypatch):
    import chapter_alignment
    overrides, fingerprints = _patched_paths(tmp_path, monkeypatch)
    _write(overrides, {
        "chapter_roll_overrides": {
            "65": {"_fingerprint": "sha256:old0000000000000", "rolls": []},
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "65": "sha256:new0000000000000",
        }
    })
    mismatches = chapter_alignment.check()
    assert len(mismatches) == 1
    assert mismatches[0].chapter_num == "65"
    assert mismatches[0].stored == "sha256:old0000000000000"
    assert mismatches[0].current == "sha256:new0000000000000"


def test_fail_if_misaligned_raises_with_chapter_in_message(tmp_path, monkeypatch):
    import chapter_alignment
    overrides, fingerprints = _patched_paths(tmp_path, monkeypatch)
    _write(overrides, {
        "chapter_roll_overrides": {
            "65": {"_fingerprint": "sha256:old0000000000000", "rolls": []},
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "65": "sha256:new0000000000000",
        }
    })
    with pytest.raises(SystemExit) as exc:
        chapter_alignment.fail_if_misaligned()
    assert "65" in str(exc.value)
    assert "stale" in str(exc.value)


def test_fail_if_misaligned_errors_on_unstamped_override(tmp_path, monkeypatch):
    import chapter_alignment
    overrides, fingerprints = _patched_paths(tmp_path, monkeypatch)
    _write(overrides, {
        "chapter_roll_overrides": {
            "65": {"rolls": []},  # no _fingerprint
        }
    })
    _write(fingerprints, {
        "chapter_alignment_fingerprints": {
            "65": "sha256:new0000000000000",
        }
    })
    with pytest.raises(SystemExit) as exc:
        chapter_alignment.fail_if_misaligned()
    assert "65" in str(exc.value)
    assert "bootstrap_chapter_alignment_anchors" in str(exc.value)


def test_live_data_passes_after_bootstrap():
    """The live committed data must always satisfy the guard.

    If this fails after a real edit, run
    scripts/bootstrap_chapter_alignment_anchors.py to re-stamp."""
    import chapter_alignment
    # Force reload of module-level paths in case a prior test monkeypatched.
    import importlib
    importlib.reload(chapter_alignment)
    chapter_alignment.fail_if_misaligned()

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.multi_grab import load_overrides


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

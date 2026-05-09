from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.multi_grab import load_overrides


class ChapterRollOverridesTest(unittest.TestCase):
    def test_roll_entries_must_use_dict_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapter_roll_overrides.json"
            path.write_text(json.dumps({
                "chapter_roll_overrides": {
                    "1": {
                        "rolls": [
                            ["Old Bare List"],
                        ],
                    },
                },
            }))

            with self.assertRaisesRegex(ValueError, "must be dict"):
                load_overrides(path)

    def test_missing_override_file_has_no_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_overrides(Path(tmp) / "chapter_roll_overrides.json")

        self.assertEqual(result, {"chapter_roll_overrides": {}})


if __name__ == "__main__":
    unittest.main()

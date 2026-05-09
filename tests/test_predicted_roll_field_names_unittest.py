from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class PredictedRollFieldNamesTest(unittest.TestCase):
    def test_predicted_rolls_use_explicit_cp_field_names(self) -> None:
        data = json.loads((ROOT / "data" / "derived" / "predicted_rolls.json").read_text())
        self.assertGreater(data["_count"], 0)
        first = data["predicted"][0]

        self.assertIn("cp_rule_regime", first)
        self.assertIn("roll_trigger_cp_threshold", first)
        self.assertNotIn("regime", first)
        self.assertNotIn("cp_threshold", first)

    def test_schema_requires_explicit_cp_field_names(self) -> None:
        schema = json.loads(
            (ROOT / "data" / "derived" / "_schemas" / "predicted_rolls.schema.json").read_text()
        )
        item_schema = schema["properties"]["predicted"]["items"]

        self.assertIn("cp_rule_regime", item_schema["required"])
        self.assertIn("roll_trigger_cp_threshold", item_schema["required"])
        self.assertNotIn("regime", item_schema["required"])
        self.assertNotIn("cp_threshold", item_schema["required"])
        self.assertIn("cp_rule_regime", item_schema["properties"])
        self.assertIn("roll_trigger_cp_threshold", item_schema["properties"])
        self.assertNotIn("regime", item_schema["properties"])
        self.assertNotIn("cp_threshold", item_schema["properties"])


if __name__ == "__main__":
    unittest.main()

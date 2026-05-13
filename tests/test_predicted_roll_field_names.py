from __future__ import annotations

import json

from scripts.data_paths import DERIVED


def test_predicted_rolls_use_explicit_cp_field_names() -> None:
    data = json.loads((DERIVED / "predicted_rolls.json").read_text())
    assert data["_count"] > 0
    first = data["predicted"][0]

    assert "cp_rule_regime" in first
    assert "roll_trigger_cp_threshold" in first
    assert "regime" not in first
    assert "cp_threshold" not in first


def test_schema_requires_explicit_cp_field_names() -> None:
    schema = json.loads(
        (DERIVED / "_schemas" / "predicted_rolls.schema.json").read_text()
    )
    item_schema = schema["properties"]["predicted"]["items"]

    assert "cp_rule_regime" in item_schema["required"]
    assert "roll_trigger_cp_threshold" in item_schema["required"]
    assert "regime" not in item_schema["required"]
    assert "cp_threshold" not in item_schema["required"]
    assert "cp_rule_regime" in item_schema["properties"]
    assert "roll_trigger_cp_threshold" in item_schema["properties"]
    assert "regime" not in item_schema["properties"]
    assert "cp_threshold" not in item_schema["properties"]

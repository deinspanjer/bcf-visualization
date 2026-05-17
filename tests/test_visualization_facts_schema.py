from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "data" / "derived" / "_schemas" / "visualization_facts.schema.json"


def test_schema_exists_and_is_valid_json():
    assert SCHEMA.exists(), f"missing schema file: {SCHEMA}"
    doc = json.loads(SCHEMA.read_text())
    assert doc["$id"].endswith("/visualization_facts.schema.json")
    assert doc["title"] == "Visualization Facts"


def test_schema_requires_all_bundle_keys():
    doc = json.loads(SCHEMA.read_text())
    required = set(doc["required"])
    assert required == {
        "schema_version", "_source", "_method", "version",
        "shadow_periods", "in_world_timeline", "chapters",
        "constellation_wireframes", "predicted_rolls", "predicted_rolls_meta",
    }


def test_schema_version_is_pinned_to_1():
    doc = json.loads(SCHEMA.read_text())
    assert doc["properties"]["schema_version"] == {"const": 1}


def test_predicted_rolls_item_shape_uses_regime_not_cp_rule_regime():
    """Bundle's predicted_rolls items use `regime` (matches render-code reader); pipeline file's
    cp_rule_regime is the upstream name and gets renamed by the bundler."""
    doc = json.loads(SCHEMA.read_text())
    item = doc["properties"]["predicted_rolls"]["items"]
    assert set(item["required"]) == {
        "roll_number", "word_position", "chapter_num",
        "regime", "roll_trigger_cp_threshold",
    }
    assert item["properties"]["regime"]["enum"] == [1, 2, 3]
    assert "cp_rule_regime" not in item["properties"], (
        "bundle schema must use the render-side name `regime`, not the pipeline name `cp_rule_regime`"
    )


def test_constellation_wireframes_keys_minimal():
    doc = json.loads(SCHEMA.read_text())
    wf = doc["properties"]["constellation_wireframes"]
    assert set(wf["required"]) == {"cluster_constellations", "jump_constellations"}
    assert wf["additionalProperties"] is False

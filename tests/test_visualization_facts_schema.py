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
        "schema_version", "_source", "_method",
        "shadow_periods", "in_world_timeline", "chapters",
        "constellation_wireframes", "predicted_rolls", "predicted_rolls_meta",
    }
    assert "version" not in doc["properties"]


def test_schema_version_field_is_const_pinned():
    """The bundle's `schema_version` property must be const-pinned (not
    free-form). This is the gate that lets the data-package manifest's
    per-file `schema_version` actually enforce a contract on consumers —
    if it weren't pinned, manifests could load older or newer documents
    silently. The specific integer is a moving target; the pin pattern
    itself is the invariant."""
    doc = json.loads(SCHEMA.read_text())
    prop = doc["properties"]["schema_version"]
    assert "const" in prop, "schema_version must be const-pinned, not free-form"
    assert isinstance(prop["const"], int) and prop["const"] >= 1


def test_predicted_rolls_item_shape_uses_explicit_predicted_identity_and_regime():
    """Bundle predicted_rolls use explicit predicted identity and render-side regime."""
    doc = json.loads(SCHEMA.read_text())
    item = doc["properties"]["predicted_rolls"]["items"]
    assert set(item["required"]) == {
        "predicted_ordinal", "predicted_label", "cp_offset", "epub_offset",
        "chapter_num", "slot_index", "regime", "roll_trigger_cp_threshold",
    }
    assert item["properties"]["regime"]["enum"] == [1, 2, 3]
    assert "roll_number" not in item["properties"]
    assert "cp_rule_regime" not in item["properties"], (
        "bundle schema must use the render-side name `regime`, not the pipeline name `cp_rule_regime`"
    )


def test_constellation_wireframes_keys_minimal():
    doc = json.loads(SCHEMA.read_text())
    wf = doc["properties"]["constellation_wireframes"]
    assert set(wf["required"]) == {"cluster_constellations", "jump_constellations"}
    assert wf["additionalProperties"] is False

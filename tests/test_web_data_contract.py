from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _node_eval(source: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def test_web_contract_helpers_accept_supported_manifest() -> None:
    source = """
      import { validateDataPackageManifest } from './web/data-contract.js';
      const manifest = {
        schema_version: 1,
        contract: 'bcf-visualization-data',
        contract_version: 1,
        files: { visualization_facts: { path: 'visualization_facts.json', schema_version: 2 } },
        entrypoints: { web: { required: ['visualization_facts'], optional: [] } },
      };
      const result = validateDataPackageManifest(manifest);
      console.log(JSON.stringify(result.required));
    """
    assert json.loads(_node_eval(source)) == ["visualization_facts"]


def test_web_contract_helpers_reject_unsupported_manifest() -> None:
    source = """
      import { validateDataPackageManifest } from './web/data-contract.js';
      try {
        validateDataPackageManifest({
          schema_version: 1,
          contract: 'bcf-visualization-data',
          contract_version: 99,
          files: {},
          entrypoints: { web: { required: ['chapter_facts'], optional: [] } },
        });
      } catch (err) {
        console.log(err.message);
      }
    """
    assert "Unsupported data package contract" in _node_eval(source)


def test_web_contract_helpers_reject_bad_required_document_version() -> None:
    source = """
      import { validateDataDocument } from './web/data-contract.js';
      try {
        validateDataDocument(
          'visualization_facts',
          { schema_version: 2 },
          { schema_version: 1 },
          { optional: false },
        );
      } catch (err) {
        console.log(err.message);
      }
    """
    assert "Unsupported visualization_facts schema_version" in _node_eval(source)


def test_web_contract_helpers_allow_bad_optional_document_to_disable_feature() -> None:
    source = """
      import { validateDataDocument } from './web/data-contract.js';
      const result = validateDataDocument(
        'demo_optional',
        { schema_version: 2 },
        { schema_version: 1 },
        { optional: true },
      );
      console.log(JSON.stringify(result));
    """
    assert json.loads(_node_eval(source)) == {
        "ok": False,
        "reason": "Unsupported demo_optional schema_version: expected 1, found 2",
    }


def test_web_contract_helper_formats_data_version_label() -> None:
    source = """
      import { dataVersionLabel } from './web/data-contract.js';
      console.log(dataVersionLabel({
        version_label: 'BCF data 20260509.7, story ch 194 / 120.1',
        package_id: 'bcf-visualization-runtime-v20260509.7-ch194-120.1',
      }));
    """
    assert _node_eval(source) == "BCF data 20260509.7, story ch 194 / 120.1"


def test_web_contract_helper_falls_back_to_story_metadata_label() -> None:
    source = """
      import { dataVersionLabel } from './web/data-contract.js';
      console.log(dataVersionLabel({
        package_date: '20260509',
        build_number: 7,
        story_chapter_ordinal: 194,
        story_chapter_num: '120.1',
      }));
    """
    assert _node_eval(source) == "BCF data 20260509.7, story ch 194 / 120.1"


def test_web_contract_helper_marks_smoke_failed_data_label() -> None:
    source = """
      import { dataVersionOptionLabel } from './web/data-contract.js';
      console.log(dataVersionOptionLabel({
        version_label: 'BCF data 20260509.7, story ch 194 / 120.1',
        smoke_status: 'failed',
      }, false));
    """
    assert _node_eval(source) == (
        "BCF data 20260509.7, story ch 194 / 120.1 (smoke failed)"
    )


def test_web_contract_helper_marks_default_after_smoke_status() -> None:
    source = """
      import { dataVersionOptionLabel } from './web/data-contract.js';
      console.log(dataVersionOptionLabel({
        version_label: 'BCF data 20260509.7, story ch 194 / 120.1',
        smoke_status: 'passed',
      }, true));
    """
    assert _node_eval(source) == (
        "BCF data 20260509.7, story ch 194 / 120.1 (smoke passed, default)"
    )


def test_visualization_facts_bundle_has_keys_loader_reads() -> None:
    """The real bundle at data/derived/visualization_facts.json must carry every
    top-level key the web loader reads. If a future bundler change drops a key,
    this test fails before we ship a broken visualization."""
    bundle_path = ROOT / "data" / "derived" / "visualization_facts.json"
    assert bundle_path.exists(), (
        "Run scripts/build_visualization_facts.py first (Task 2 Step 5)."
    )
    bundle = json.loads(bundle_path.read_text())
    required_keys = {
        "schema_version", "version",
        "shadow_periods", "in_world_timeline", "chapters",
        "constellation_wireframes", "predicted_rolls", "predicted_rolls_meta",
    }
    missing = required_keys - set(bundle.keys())
    assert not missing, f"bundle missing keys the loader reads: {sorted(missing)}"


def test_visualization_facts_predicted_rolls_use_renamed_regime_field() -> None:
    """The bundler renames cp_rule_regime → regime so render code at web/app.js
    consumes a single canonical field name. If a row carries cp_rule_regime instead
    of regime, the scrubber axis hairlines will silently render as regime-1."""
    bundle_path = ROOT / "data" / "derived" / "visualization_facts.json"
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text())
    rolls = bundle.get("predicted_rolls") or []
    assert rolls, "expected at least one predicted roll in the real bundle"
    for row in rolls[:5]:
        assert "regime" in row, f"row missing renamed field: {row}"
        assert "cp_rule_regime" not in row, f"row still carries upstream field: {row}"

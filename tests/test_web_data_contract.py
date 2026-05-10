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
        files: { chapter_facts: { path: 'chapter_facts.json', schema_version: 1 } },
        entrypoints: { web: { required: ['chapter_facts'], optional: [] } },
      };
      const result = validateDataPackageManifest(manifest);
      console.log(JSON.stringify(result.required));
    """
    assert json.loads(_node_eval(source)) == ["chapter_facts"]


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
          'chapter_facts',
          { schema_version: 2 },
          { schema_version: 1 },
          { optional: false },
        );
      } catch (err) {
        console.log(err.message);
      }
    """
    assert "Unsupported chapter_facts schema_version" in _node_eval(source)


def test_web_contract_helpers_allow_bad_optional_document_to_disable_feature() -> None:
    source = """
      import { validateDataDocument } from './web/data-contract.js';
      const result = validateDataDocument(
        'roll_resolutions',
        { schema_version: 2 },
        { schema_version: 1 },
        { optional: true },
      );
      console.log(JSON.stringify(result));
    """
    assert json.loads(_node_eval(source)) == {
        "ok": False,
        "reason": "Unsupported roll_resolutions schema_version: expected 1, found 2",
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

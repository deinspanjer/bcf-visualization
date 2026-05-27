from __future__ import annotations

import json
from pathlib import Path

from scripts.build_visualization_facts import build

ROOT = Path(__file__).resolve().parent.parent


def _seed_inputs(tmp_path: Path) -> Path:
    """Write the four input files build() expects into tmp_path and return tmp_path."""
    chapter_facts = {
        "schema_version": 1,
        "_source": "fixture",
        "_method": "fixture",
        "_count": 1,
        "_grain": "chapter",
        "_deferred": [],
        "shadow_periods": [],
        "in_world_timeline": {
            "_sources_used": ["manual"],
            "_count": 0,
            "_first_in_world_date": None,
            "_last_in_world_date": None,
            "entries": [],
        },
        "chapters": [
            {"chapter_num": "1", "full_title": "1 Fixture"},
        ],
    }
    wireframes = {
        "schema_version": 2,
        "_source": "fixture",
        "_count": 14,
        "_jumps_count": 0,
        "_note": "fixture",
        "cluster_constellations": [],
        "jump_constellations": [],
    }
    predicted = {
        "_source": "fixture",
        "_count": 1,
        "_total_cp_words": 2000,
        "_total_epub_words": 2253,
        "_regime_summary": {"1": "a", "2": "b", "3": "c"},
        "_validation_chapters_1_75": {
            "actual_total_attempts": 0,
            "predicted_total_in_same_chapters": 0,
        },
        "predicted": [
            {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
             "chapter_num": "1", "slot_index": 1, "cp_rule_regime": 1,
             "roll_trigger_cp_threshold": 100},
        ],
        "comparison_per_chapter": [],
    }
    manifest = {
        "schema_version": 1,
        "package_id": "fixture-pkg",
        "version_label": "fixture label",
        "package_date": "20260101",
        "build_number": 1,
        "source_commit": "deadbeef",
        "story_chapter_ordinal": 1,
        "story_chapter_num": "1",
        "story_chapter_title": "1 Fixture",
    }
    (tmp_path / "chapter_facts.json").write_text(json.dumps(chapter_facts))
    (tmp_path / "constellation_wireframes.json").write_text(json.dumps(wireframes))
    (tmp_path / "predicted_rolls.json").write_text(json.dumps(predicted))
    (tmp_path / "data_package.json").write_text(json.dumps(manifest))
    return tmp_path


def test_bundle_has_required_top_level_keys(tmp_path: Path):
    bundle = build(_seed_inputs(tmp_path))
    assert set(bundle.keys()) >= {
        "schema_version", "_source", "_method", "version",
        "shadow_periods", "in_world_timeline", "chapters",
        "constellation_wireframes", "predicted_rolls", "predicted_rolls_meta",
    }


def test_bundle_version_matches_manifest(tmp_path: Path):
    bundle = build(_seed_inputs(tmp_path))
    assert bundle["version"]["package_id"] == "fixture-pkg"
    assert bundle["version"]["version_label"] == "fixture label"
    assert bundle["version"]["build_number"] == 1


def test_bundle_chapters_projected_with_rolls_list(tmp_path: Path):
    # Bundle projects each chapter through _project_bundle_chapter, which
    # strips the cascade positional fields from rolls and ensures a `rolls`
    # array exists. Fixtures with no rolls round-trip with an empty list.
    bundle = build(_seed_inputs(tmp_path))
    assert bundle["chapters"] == [
        {"chapter_num": "1", "full_title": "1 Fixture", "rolls": []},
    ]


def test_bundle_source_method_describe_bundler(tmp_path: Path):
    bundle = build(_seed_inputs(tmp_path))
    assert bundle["_source"] == "scripts/build_visualization_facts.py"
    assert "Bundles" in bundle["_method"]


def test_bundle_strips_pipeline_metadata_from_wireframes(tmp_path: Path):
    bundle = build(_seed_inputs(tmp_path))
    wf = bundle["constellation_wireframes"]
    assert set(wf.keys()) == {"cluster_constellations", "jump_constellations"}


def test_bundle_predicted_rolls_renames_cp_rule_regime_to_regime(tmp_path: Path):
    """Bundler renames the source field cp_rule_regime → regime so the bundle's items match
    the render-side reader at web/app.js:1021 (`tick.regime`). Synthetic ticks already use `regime`."""
    bundle = build(_seed_inputs(tmp_path))
    assert bundle["predicted_rolls"] == [
        {"predicted_ordinal": 1, "predicted_label": "P1", "cp_offset": 2000,
         "epub_offset": 2253, "chapter_num": "1", "slot_index": 1,
         "regime": 1, "roll_trigger_cp_threshold": 100},
    ]
    for row in bundle["predicted_rolls"]:
        assert "roll_number" not in row
        assert "cp_rule_regime" not in row, (
            "bundler must drop the upstream cp_rule_regime field after renaming"
        )
    assert bundle["predicted_rolls_meta"]["_count"] == 1
    assert bundle["predicted_rolls_meta"]["_regime_summary"] == {"1": "a", "2": "b", "3": "c"}

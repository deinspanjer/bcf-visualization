"""Bundle chapter_facts, constellation_wireframes, predicted_rolls, and version metadata into the single visualization_facts.json file consumed by the web visualization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from _common import write_validated_json
    from data_paths import DERIVED
    from data_release import refresh_current_runtime_manifest
except ModuleNotFoundError:
    from scripts._common import write_validated_json
    from scripts.data_paths import DERIVED
    from scripts.data_release import refresh_current_runtime_manifest


SOURCE = "scripts/build_visualization_facts.py"
METHOD = ("Bundles chapter_facts + constellation_wireframes + "
          "predicted_rolls into the single web-facing visualization data file.")

VERSION_FIELDS = (
    "package_id", "version_label", "package_date", "build_number",
    "source_commit", "story_chapter_ordinal", "story_chapter_num",
    "story_chapter_title",
)

CHAPTER_FACTS_PAYLOAD_KEYS = ("shadow_periods", "in_world_timeline")
WIREFRAME_PAYLOAD_KEYS = ("cluster_constellations", "jump_constellations")
PREDICTED_META_KEYS = ("_count", "_total_cp_words", "_total_epub_words", "_regime_summary")

# Cascade positional fields kept on chapter_facts (still consumed by the
# TUI) but stripped from the bundle. The UI reads only the canonical
# epub_word_offset_{predicted,curated} now.
BUNDLE_DROPPED_ROLL_FIELDS = (
    "display_cumulative_word_offset",
    "cumulative_word_offset",
    "source_cumulative_word_offset",
    "display_word_position_epub",
    "predicted_word_position_epub",
)


def _project_bundle_roll(roll: dict) -> dict:
    return {k: v for k, v in roll.items() if k not in BUNDLE_DROPPED_ROLL_FIELDS}


def _project_bundle_chapter(chapter: dict) -> dict:
    return {
        **chapter,
        "rolls": [_project_bundle_roll(r) for r in chapter.get("rolls", [])],
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def build(input_dir: Path) -> dict:
    chapter_facts = _read_json(input_dir / "chapter_facts.json")
    wireframes = _read_json(input_dir / "constellation_wireframes.json")
    predicted = _read_json(input_dir / "predicted_rolls.json")
    manifest = _read_json(input_dir / "data_package.json")

    version = {key: manifest[key] for key in VERSION_FIELDS}

    # Rename cp_rule_regime → regime on the way through. Keeps a single canonical name
    # at the render-side consumer (`web/app.js:1021` reads `tick.regime`); the pipeline
    # file's `cp_rule_regime` stays unchanged for internal use.
    predicted_rolls = [
        {
            **{
                k: v for k, v in row.items()
                if k not in {"cp_rule_regime", "roll_number"}
            },
            "predicted_ordinal": int(row["roll_number"]),
            "predicted_label": f"P{int(row['roll_number'])}",
            "regime": row["cp_rule_regime"],
        }
        for row in predicted["predicted"]
    ]

    bundle = {
        "schema_version": 2,
        "_source": SOURCE,
        "_method": METHOD,
        "version": version,
        **{key: chapter_facts[key] for key in CHAPTER_FACTS_PAYLOAD_KEYS},
        "chapters": [_project_bundle_chapter(c) for c in chapter_facts["chapters"]],
        "constellation_wireframes": {
            key: wireframes[key] for key in WIREFRAME_PAYLOAD_KEYS
        },
        "predicted_rolls": predicted_rolls,
        "predicted_rolls_meta": {
            key: predicted[key] for key in PREDICTED_META_KEYS
        },
    }
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path, default=DERIVED,
        help="Directory containing chapter_facts.json, constellation_wireframes.json, predicted_rolls.json, data_package.json. Defaults to data/derived/.",
    )
    parser.add_argument(
        "--output", type=Path, default=DERIVED / "visualization_facts.json",
        help="Output path. Defaults to data/derived/visualization_facts.json.",
    )
    args = parser.parse_args()

    bundle = build(args.input_dir)
    write_validated_json(args.output, bundle, schema_name="visualization_facts")
    if args.input_dir.resolve() == DERIVED.resolve():
        refresh_current_runtime_manifest(source_dir=DERIVED)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

from openpyxl import Workbook


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _roll_fact(
    *,
    chapter_num: str,
    sequence: int,
    roll_number: int,
    outcome: str,
    display_position_policy: str,
    display_word_position: int,
    mechanical_word_position: int,
) -> dict:
    return {
        "chapter_num": chapter_num,
        "roll_sequence_in_chapter": sequence,
        "source_row_index": sequence,
        "predicted_ordinal": roll_number,
        "predicted_label": f"P{roll_number}",
        "source_ordinal": roll_number,
        "source_label": f"S{roll_number}",
        "roll_ordinal": roll_number,
        "roll_label": f"R{roll_number}",
        "chapter_ordinal": sequence,
        "chapter_label": f"C{sequence}",
        "association_source": "auto",
        "outcome": outcome,
        "constellation": "Magic",
        "mechanical_chapter_num": chapter_num,
        "mechanical_word_position": mechanical_word_position,
        "mechanical_cumulative_word_offset": mechanical_word_position,
        "mention_chapter_num": chapter_num,
        "mention_word_position": display_word_position,
        "display_position_policy": display_position_policy,
        "display_chapter_num": chapter_num,
        "display_word_position": display_word_position,
        "source_chapter_num": chapter_num,
        "source_chapter_ordinal": sequence,
        "source_roll_label": f"Roll {roll_number}",
        "source_word_position": display_word_position,
        "source_cumulative_word_offset": display_word_position,
        "visible_chapter_nums": [chapter_num],
        "purchased_perk_id": None,
        "purchased_perks": [],
        "purchased_perk_cost_total": None,
        "purchased_perk_jump": None,
        "free_perks": [],
        "word_position": mechanical_word_position,
        "cumulative_word_offset": display_word_position,
        "predicted_word_position_epub": mechanical_word_position,
        "display_word_position_epub": display_word_position,
        "epub_word_offset_predicted": mechanical_word_position,
        "epub_word_offset_curated": display_word_position,
        "predicted_char_offset_in_chapter": None,
        "anchor_char_offset_in_chapter": None,
        "evidence_kind": "direct",
        "evidence_quotes": [
            {
                "text": f"quote for roll {roll_number}",
                "mention_chapter_num": chapter_num,
                "mention_word_position": display_word_position,
            }
        ],
        "available_cp": 100,
        "banked_cp_after_roll": 0,
        "rolled_perk_name": None,
        "rolled_perk_instance": None,
        "rolled_perk_cost": None,
        "miss_cost_estimate": 100 if outcome == "miss" else None,
        "rolls_in_chapter": 1,
        "source": "curator_rolls",
        "source_kind": "roll",
    }


def _model_check(chapter_num: str, *, discrepancy: bool) -> dict:
    return {
        "chapter_num": chapter_num,
        "status": "discrepancy" if discrepancy else "ok",
        "has_discrepancy": discrepancy,
        "raw_has_discrepancy": discrepancy,
        "source_priority": "vetted_curated",
        "predicted_roll_count": 1,
        "required_paid_roll_count": 0,
        "known_attempt_count": 1,
        "paid_roll_capacity_ok": True,
        "known_attempt_capacity_ok": True,
        "cost_schedule_ok": True,
        "synthetic_slot_count": 0,
        "resolved_issue_codes": [],
        "issues": (
            [
                {
                    "code": "fixture_discrepancy",
                    "severity": "error",
                    "message": "Fixture discrepancy.",
                }
            ]
            if discrepancy
            else []
        ),
    }


def _fixture_chapter(
    chapter_num: str,
    title: str,
    *,
    sort_key: list[int],
    word_count: int = 1000,
) -> dict:
    return {
        "chapter_num": chapter_num,
        "full_title": title,
        "sort_key": sort_key,
        "ordinal": sort_key[0],
        "epub_href": f"chap_{sort_key[0]}.xhtml",
        "total_word_count": word_count,
    }


def _fixture_section(chapter_num: str, title: str, *, word_count: int = 1000) -> dict:
    return {
        "chapter_num": chapter_num,
        "full_title": title,
        "total_word_count": word_count,
        "sections": [
            {
                "header": None,
                "word_count": word_count,
                "classification": "mc_pov",
                "confidence": "fixture",
                "structural_markers": [],
            }
        ],
    }


def _fixture_perk(
    *,
    sequence: int,
    chapter_num: str,
    name: str,
    jump: str,
    constellation: str,
    cost: int,
) -> dict:
    return {
        "epub_sequence": sequence,
        "chapter_num": chapter_num,
        "chapter_full_title": f"{chapter_num} Fixture",
        "perk_name": name,
        "classification": "Perk",
        "jump": jump,
        "cost": cost,
        "cost_text": str(cost),
        "free": False,
        "perk_text": f"{name} fixture text.",
        "constellation": constellation,
    }


def _fixture_directory_perk(
    *,
    name: str,
    jump: str,
    constellation: str,
    cost: int,
) -> dict:
    return {
        "id": f"{constellation}__{jump}__{name}".replace(" ", "_"),
        "constellation": constellation,
        "name": name,
        "jump": jump,
        "status": "Obtained",
        "cost": cost,
        "cost_text": f"{cost} CP",
        "free": False,
        "repeatable": False,
        "description": f"{name} fixture description.",
        "acquired_chapter_num": None,
        "acquired_epub_sequence": None,
        "first_acquired_at_word_offset": None,
        "matched_to_obtained": True,
        "source": "fixture",
        "acquired_instances": [],
    }


def _patch_pipeline_paths(monkeypatch, project: Path, epub: Path) -> None:
    from scripts import build_chapter_facts, derive_roll_facts

    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"

    monkeypatch.setattr(derive_roll_facts, "ROOT", project)
    monkeypatch.setattr(derive_roll_facts, "CURATOR_ROLLS", derived / "rolls.json")
    monkeypatch.setattr(derive_roll_facts, "ROLL_OUTCOMES", derived / "roll_outcomes.json")
    monkeypatch.setattr(derive_roll_facts, "PREDICTED_ROLLS", derived / "predicted_rolls.json")
    monkeypatch.setattr(derive_roll_facts, "OBTAINED_PERKS", derived / "obtained_perks.json")
    monkeypatch.setattr(derive_roll_facts, "CHAPTERS_JSON", derived / "chapters.json")
    monkeypatch.setattr(derive_roll_facts, "EVIDENCE", derived / "roll_text_evidence.json")
    monkeypatch.setattr(derive_roll_facts, "DIRECTORY", derived / "perk_directory.json")
    monkeypatch.setattr(derive_roll_facts, "OUTSTANDING", derived / "outstanding_perks_by_chapter.json")
    monkeypatch.setattr(derive_roll_facts, "ROLL_OVERRIDES", manual / "roll_overrides.json")
    monkeypatch.setattr(derive_roll_facts, "OUT", derived / "roll_facts.json")
    monkeypatch.setattr(derive_roll_facts, "VALIDATION_OUT", derived / "roll_validation.json")
    monkeypatch.setattr(
        derive_roll_facts,
        "_load_cp_words_per_chapter",
        lambda: {
            "1 Fixture": 1000,
            "2 Fixture": 1000,
            "3 Fixture": 1000,
        },
    )
    monkeypatch.setattr(derive_roll_facts, "load_regime_transitions", lambda: [])
    monkeypatch.setattr(
        derive_roll_facts,
        "load_multi_grab_overrides",
        lambda: json.loads((manual / "chapter_roll_overrides.json").read_text()),
    )

    monkeypatch.setattr(build_chapter_facts, "ROOT", project)
    monkeypatch.setattr(build_chapter_facts, "EPUB", epub)
    monkeypatch.setattr(build_chapter_facts, "CHAPTERS", derived / "chapters.json")
    monkeypatch.setattr(build_chapter_facts, "SECTIONS", derived / "chapter_sections.json")
    monkeypatch.setattr(build_chapter_facts, "CLASSIFICATIONS", manual / "section_classifications.json")
    monkeypatch.setattr(build_chapter_facts, "ROLL_FACTS", derived / "roll_facts.json")
    monkeypatch.setattr(build_chapter_facts, "ROLL_VALIDATION", derived / "roll_validation.json")
    monkeypatch.setattr(build_chapter_facts, "PREDICTED_ROLLS", derived / "predicted_rolls.json")
    monkeypatch.setattr(build_chapter_facts, "CHAPTER_ROLL_OVERRIDES", manual / "chapter_roll_overrides.json")
    monkeypatch.setattr(build_chapter_facts, "OBTAINED_PERKS", derived / "obtained_perks.json")
    monkeypatch.setattr(build_chapter_facts, "PERK_DIRECTORY", derived / "perk_directory.json")
    monkeypatch.setattr(build_chapter_facts, "PUBLICATION_DATES", manual / "chapter_publication_dates.json")
    monkeypatch.setattr(build_chapter_facts, "TIMELINE", derived / "timeline.json")
    monkeypatch.setattr(build_chapter_facts, "OUT", derived / "chapter_facts.json")
    monkeypatch.setattr(
        build_chapter_facts,
        "refresh_current_runtime_manifest",
        lambda *, source_dir, **_: None,
    )
    monkeypatch.setattr(
        build_chapter_facts,
        "model_issues_by_chapter",
        lambda: {
            "2": [
                {
                    "code": "chapter_alignment_stale",
                    "severity": "error",
                    "message": "Chapter roll overrides are stale.",
                }
            ]
        },
    )


def test_chapter_facts_projects_roll_facts_onto_story_axis(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_chapter_facts

    project = tmp_path / "project"
    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = raw / "fixture.epub"

    raw.mkdir(parents=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr(
            "EPUB/nav.xhtml",
            (
                '<nav><a href="chap_1.xhtml">1 Fixture</a>'
                '<a href="chap_2.xhtml">2 Fixture</a></nav>'
            ),
        )
        zf.writestr("EPUB/chap_1.xhtml", "<p>Fixture chapter one body.</p>")
        zf.writestr("EPUB/chap_2.xhtml", "<p>Fixture chapter two body.</p>")

    chapters = [
        {
            "chapter_num": "1",
            "full_title": "1 Fixture",
            "sort_key": [1, 0],
            "ordinal": 1,
            "epub_href": "chap_1.xhtml",
            "total_word_count": 1000,
        },
        {
            "chapter_num": "2",
            "full_title": "2 Fixture",
            "sort_key": [2, 0],
            "ordinal": 2,
            "epub_href": "chap_2.xhtml",
            "total_word_count": 1000,
        },
    ]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {
            "chapters": [
                {
                    "chapter_num": "1",
                    "full_title": "1 Fixture",
                    "total_word_count": 1000,
                    "sections": [
                        {
                            "header": None,
                            "word_count": 1000,
                            "classification": "mc_pov",
                            "confidence": "fixture",
                            "structural_markers": [],
                        }
                    ],
                },
                {
                    "chapter_num": "2",
                    "full_title": "2 Fixture",
                    "total_word_count": 1000,
                    "sections": [
                        {
                            "header": None,
                            "word_count": 1000,
                            "classification": "mc_pov",
                            "confidence": "fixture",
                            "structural_markers": [],
                        }
                    ],
                },
            ]
        },
    )
    _write_json(
        manual / "section_classifications.json",
        {
            "classifications": {
                "1@0": {"counts_for_cp": True},
                "2@0": {"counts_for_cp": True},
            }
        },
    )
    _write_json(
        derived / "roll_facts.json",
        {
            "rolls": [
                _roll_fact(
                    chapter_num="1",
                    sequence=1,
                    roll_number=1,
                    outcome="miss",
                    display_position_policy="source_marker",
                    display_word_position=250,
                    mechanical_word_position=400,
                ),
                _roll_fact(
                    chapter_num="2",
                    sequence=1,
                    roll_number=2,
                    outcome="miss",
                    display_position_policy="mechanical",
                    display_word_position=500,
                    mechanical_word_position=500,
                ),
            ]
        },
    )
    _write_json(
        derived / "roll_validation.json",
        {"chapter_checks": [_model_check("1", discrepancy=True), _model_check("2", discrepancy=False)]},
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {"chapter_num": "1", "slot_index": 1, "cp_offset": 400,
                 "epub_offset": 400, "roll_number": 1},
                {"chapter_num": "2", "slot_index": 1, "cp_offset": 1500,
                 "epub_offset": 1500, "roll_number": 2},
            ]
        },
    )
    _write_json(
        manual / "chapter_roll_overrides.json",
        {"chapter_roll_overrides": {"2": {"rolls": [{"skipped": True}]}}},
    )
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(
        manual / "chapter_publication_dates.json",
        {
            "_source": "test fixture",
            "_count": 2,
            "chapters": [
                {
                    "chapter_num": "1",
                    "published_at": "2024-01-01",
                    "published_source": "ao3",
                    "last_edited_at": None,
                    "last_edited_source": None,
                },
                {
                    "chapter_num": "2",
                    "published_at": "2024-01-02",
                    "published_source": "ao3",
                    "last_edited_at": None,
                    "last_edited_source": None,
                },
            ],
        },
    )
    _write_json(
        derived / "timeline.json",
        {
            "_sources_used": [],
            "_count": 0,
            "_first_in_world_date": None,
            "_last_in_world_date": None,
            "entries": [],
        },
    )

    monkeypatch.setattr(build_chapter_facts, "ROOT", project)
    monkeypatch.setattr(build_chapter_facts, "EPUB", epub)
    monkeypatch.setattr(build_chapter_facts, "CHAPTERS", derived / "chapters.json")
    monkeypatch.setattr(build_chapter_facts, "SECTIONS", derived / "chapter_sections.json")
    monkeypatch.setattr(build_chapter_facts, "CLASSIFICATIONS", manual / "section_classifications.json")
    monkeypatch.setattr(build_chapter_facts, "ROLL_FACTS", derived / "roll_facts.json")
    monkeypatch.setattr(build_chapter_facts, "ROLL_VALIDATION", derived / "roll_validation.json")
    monkeypatch.setattr(build_chapter_facts, "PREDICTED_ROLLS", derived / "predicted_rolls.json")
    monkeypatch.setattr(build_chapter_facts, "CHAPTER_ROLL_OVERRIDES", manual / "chapter_roll_overrides.json")
    monkeypatch.setattr(build_chapter_facts, "OBTAINED_PERKS", derived / "obtained_perks.json")
    monkeypatch.setattr(build_chapter_facts, "PERK_DIRECTORY", derived / "perk_directory.json")
    monkeypatch.setattr(build_chapter_facts, "PUBLICATION_DATES", manual / "chapter_publication_dates.json")
    monkeypatch.setattr(build_chapter_facts, "TIMELINE", derived / "timeline.json")
    monkeypatch.setattr(build_chapter_facts, "OUT", derived / "chapter_facts.json")
    monkeypatch.setattr(
        build_chapter_facts,
        "refresh_current_runtime_manifest",
        lambda *, source_dir, **_: None,
    )
    monkeypatch.setattr(
        build_chapter_facts,
        "model_issues_by_chapter",
        lambda: {
            "2": [
                {
                    "code": "chapter_alignment_stale",
                    "severity": "error",
                    "message": "Chapter roll overrides are stale.",
                }
            ]
        },
    )

    build_chapter_facts.main()

    output = json.loads((derived / "chapter_facts.json").read_text())
    by_chapter = {chapter["chapter_num"]: chapter for chapter in output["chapters"]}

    assert by_chapter["1"]["rolls"][0]["display_cumulative_word_offset"] == 250
    assert by_chapter["1"]["rolls"][0]["cumulative_word_offset"] == 250
    assert by_chapter["2"]["rolls"][0]["display_cumulative_word_offset"] == 1500
    assert by_chapter["2"]["skipped_predicted_rolls"] == [
        {
            "slot_index": 1,
            "predicted_ordinal": 2,
            "predicted_label": "P2",
            "source_ordinal": None,
            "source_label": None,
            "roll_ordinal": None,
            "roll_label": None,
            "skipped_ordinal": 1,
            "skipped_label": "X1",
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 500,
            "mechanical_cumulative_word_offset": 1500,
            "predicted_word_position_epub": 1500,
            "reason": "skipped_to_align_narrative",
        }
    ]
    assert by_chapter["1"]["model_validation"]["current_discrepancy"] is True
    assert by_chapter["2"]["model_validation"]["current_discrepancy"] is True
    assert by_chapter["2"]["model_validation"]["prior_discrepancy"] is True
    assert by_chapter["2"]["model_validation"]["first_discrepancy_chapter_num"] == "1"
    assert by_chapter["2"]["model_validation"]["issues"][-1]["code"] == (
        "chapter_alignment_stale"
    )

    # Date fields pass through verbatim from chapter_publication_dates.json,
    # and edited_lag_days is computed as last_edited_at - published_at.
    assert by_chapter["1"]["published_at"] == "2024-01-01"
    assert by_chapter["1"]["published_source"] == "ao3"
    assert by_chapter["1"]["last_edited_at"] is None
    assert by_chapter["1"]["last_edited_source"] is None
    assert by_chapter["1"]["edited_lag_days"] is None


def test_chapter_facts_emits_edited_lag_days_from_publication_dates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """When chapter_publication_dates.json carries a last_edited_at,
    build_chapter_facts derives edited_lag_days inline rather than
    pulling it from a separate file."""
    from scripts import build_chapter_facts

    project = tmp_path / "project"
    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = raw / "fixture.epub"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr(
            "EPUB/nav.xhtml",
            '<nav><a href="chap_1.xhtml">1 Fixture</a></nav>',
        )
        zf.writestr("EPUB/chap_1.xhtml", "<p>body</p>")

    _write_json(derived / "chapters.json", {"chapters": [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0]),
    ]})
    _write_json(derived / "chapter_sections.json", {"chapters": [
        _fixture_section("1", "1 Fixture"),
    ]})
    _write_json(manual / "section_classifications.json",
                {"classifications": {"1@0": {"counts_for_cp": True}}})
    _write_json(derived / "predicted_rolls.json", {"predicted": []})
    _write_json(derived / "roll_facts.json",
                {"_method": "test", "rolls": []})
    _write_json(derived / "roll_validation.json", {"chapter_checks": []})
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(manual / "chapter_roll_overrides.json",
                {"chapter_roll_overrides": {}})
    _write_json(derived / "timeline.json", {
        "_sources_used": [], "_count": 0,
        "_first_in_world_date": None, "_last_in_world_date": None,
        "entries": [],
    })
    _write_json(manual / "chapter_publication_dates.json", {
        "_source": "test fixture",
        "_count": 1,
        "chapters": [{
            "chapter_num": "1",
            "published_at": "2020-05-01",
            "published_source": "ao3",
            "last_edited_at": "2020-12-10",
            "last_edited_source": "epub",
        }],
    })

    _patch_pipeline_paths(monkeypatch, project, epub)
    build_chapter_facts.main()

    out = json.loads((derived / "chapter_facts.json").read_text())
    row = out["chapters"][0]
    assert row["published_at"] == "2020-05-01"
    assert row["published_source"] == "ao3"
    assert row["last_edited_at"] == "2020-12-10"
    assert row["last_edited_source"] == "epub"
    assert row["edited_lag_days"] == 223  # 2020-12-10 minus 2020-05-01


def test_chapter_facts_passes_through_manual_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """If the manual file records a non-ao3 published_source (e.g. a row
    a maintainer hand-edited), that provenance flows through unchanged."""
    from scripts import build_chapter_facts

    project = tmp_path / "project"
    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = raw / "fixture.epub"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr("EPUB/nav.xhtml",
                    '<nav><a href="chap_1.xhtml">1 Fixture</a></nav>')
        zf.writestr("EPUB/chap_1.xhtml", "<p>body</p>")

    _write_json(derived / "chapters.json", {"chapters": [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0]),
    ]})
    _write_json(derived / "chapter_sections.json", {"chapters": [
        _fixture_section("1", "1 Fixture"),
    ]})
    _write_json(manual / "section_classifications.json",
                {"classifications": {"1@0": {"counts_for_cp": True}}})
    _write_json(derived / "predicted_rolls.json", {"predicted": []})
    _write_json(derived / "roll_facts.json",
                {"_method": "test", "rolls": []})
    _write_json(derived / "roll_validation.json", {"chapter_checks": []})
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(manual / "chapter_roll_overrides.json",
                {"chapter_roll_overrides": {}})
    _write_json(derived / "timeline.json", {
        "_sources_used": [], "_count": 0,
        "_first_in_world_date": None, "_last_in_world_date": None,
        "entries": [],
    })
    _write_json(manual / "chapter_publication_dates.json", {
        "_source": "test fixture",
        "_count": 1,
        "chapters": [{
            "chapter_num": "1",
            "published_at": "2020-07-19",
            "published_source": "manual",
            "last_edited_at": None,
            "last_edited_source": None,
        }],
    })

    _patch_pipeline_paths(monkeypatch, project, epub)
    build_chapter_facts.main()

    row = json.loads((derived / "chapter_facts.json").read_text())["chapters"][0]
    assert row["published_at"] == "2020-07-19"
    assert row["published_source"] == "manual"
    assert row["last_edited_at"] is None
    assert row["last_edited_source"] is None
    assert row["edited_lag_days"] is None


def test_roll_facts_derivation_feeds_chapter_facts_cross_chapter_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_chapter_facts, derive_roll_facts

    project = tmp_path / "project"
    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = raw / "fixture.epub"

    raw.mkdir(parents=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr(
            "EPUB/nav.xhtml",
            (
                '<nav><a href="chap_1.xhtml">1 Fixture</a>'
                '<a href="chap_2.xhtml">2 Fixture</a>'
                '<a href="chap_3.xhtml">3 Fixture</a></nav>'
            ),
        )
        zf.writestr("EPUB/chap_1.xhtml", "<p>Fixture chapter one body.</p>")
        zf.writestr("EPUB/chap_2.xhtml", "<p>Fixture chapter two body.</p>")
        zf.writestr("EPUB/chap_3.xhtml", "<p>Fixture chapter three body.</p>")

    chapters = [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0]),
        _fixture_chapter("2", "2 Fixture", sort_key=[2, 0]),
        _fixture_chapter("3", "3 Fixture", sort_key=[3, 0]),
    ]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {"chapters": [_fixture_section(c["chapter_num"], c["full_title"]) for c in chapters]},
    )
    _write_json(
        manual / "section_classifications.json",
        {
            "classifications": {
                "1@0": {"counts_for_cp": True},
                "2@0": {"counts_for_cp": True},
                "3@0": {"counts_for_cp": True},
            }
        },
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "1",
                    "slot_index": 1,
                    "cp_offset": 200,
                    "epub_offset": 200,
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                },
                {
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 1200,
                    "epub_offset": 1200,
                    "roll_number": 2,
                    "roll_trigger_cp_threshold": 100,
                },
                {
                    "chapter_num": "2",
                    "slot_index": 2,
                    "cp_offset": 1800,
                    "epub_offset": 1800,
                    "roll_number": 3,
                    "roll_trigger_cp_threshold": 100,
                },
                {
                    "chapter_num": "3",
                    "slot_index": 1,
                    "cp_offset": 2300,
                    "epub_offset": 2300,
                    "roll_number": 3,
                    "roll_trigger_cp_threshold": 100,
                },
                {
                    "chapter_num": "3",
                    "slot_index": 2,
                    "cp_offset": 2700,
                    "epub_offset": 2700,
                    "roll_number": 4,
                    "roll_trigger_cp_threshold": 100,
                },
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {"roll_number": 1, "chapter_num": "1", "slot_index": 1,
                 "cp_offset": 200, "epub_offset": 200},
                {"roll_number": 2, "chapter_num": "2", "slot_index": 1,
                 "cp_offset": 1200, "epub_offset": 1200},
                {"roll_number": 3, "chapter_num": "3", "slot_index": 1,
                 "cp_offset": 2300, "epub_offset": 2300},
                {"roll_number": 4, "chapter_num": "3", "slot_index": 2,
                 "cp_offset": 2700, "epub_offset": 2700},
            ]
        },
    )
    _write_json(
        derived / "rolls.json",
        {
            "rolls": [
                {
                    "roll_number": 1,
                    "chapter_num": "1",
                    "kind": "miss",
                    "banked_before": 100,
                    "banked_after": 100,
                    "constellation": None,
                    "constellation_revealed": False,
                    "perks": [],
                    "raw": "Roll 1 miss",
                },
                {
                    "roll_number": 2,
                    "chapter_num": "2",
                    "kind": "roll",
                    "banked_before": 100,
                    "banked_after": 0,
                    "constellation": "Magic",
                    "constellation_revealed": True,
                    "perks": [
                        {
                            "name": "Deferred Spark",
                            "source": "Fixture Jump",
                            "cost": 100,
                            "free": False,
                        }
                    ],
                    "raw": "Roll 2 hit",
                },
                {
                    "roll_number": 3,
                    "chapter_num": "2",
                    "kind": "miss",
                    "banked_before": 100,
                    "banked_after": 100,
                    "constellation": None,
                    "constellation_revealed": False,
                    "perks": [],
                    "raw": "Roll 3 source miss",
                },
            ]
        },
    )
    _write_json(
        derived / "roll_outcomes.json",
        {
            "rolls": [
                {
                    "chapter_num": "3",
                    "word_position": 300,
                    "source": "predicted",
                    "outcome": "miss",
                    "perk": None,
                    "paid_perks": [],
                    "free_perks": [],
                    "roll_number": 3,
                    "roll_trigger_cp_threshold": 100,
                    "sequence_in_chapter": 1,
                    "rolls_in_chapter": 1,
                    "available_cp": 100,
                    "banked_cp_after_roll": 100,
                }
            ]
        },
    )
    obtained_perks = [
        _fixture_perk(
            sequence=1,
            chapter_num="3",
            name="Deferred Spark",
            jump="Fixture Jump",
            constellation="Magic",
            cost=100,
        )
    ]
    _write_json(derived / "obtained_perks.json", {"perks": obtained_perks})
    _write_json(
        derived / "perk_directory.json",
        {
            "perks": [
                _fixture_directory_perk(
                    name="Deferred Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=100,
                )
            ]
        },
    )
    _write_json(
        derived / "outstanding_perks_by_chapter.json",
        {
            "chapters": [
                {
                    "chapter_num": str(i),
                    "before_chapter": {
                        "total_count": 1,
                        "by_constellation": {
                            "Magic": [{"name": "Expensive Fixture", "cost": 200}]
                        },
                    },
                }
                for i in (1, 2, 3)
            ]
        },
    )
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "1": {
                    "rolls": [
                        {
                            "display_position_policy": "mention",
                            "mention_word_position": 250,
                            "evidence_quotes": [
                                {
                                    "text": "quote-only metadata anchors roll one",
                                    "mention_chapter_num": "1",
                                    "mention_word_position": 250,
                                }
                            ],
                        }
                    ]
                },
                "2": {
                    "rolls": [
                        {
                            "perks": ["Deferred Spark"],
                            "outcome": "hit",
                            "constellation": "Magic",
                            "mention_chapter_num": "3",
                            "mention_word_position": 100,
                            "display_position_policy": "mechanical",
                            "evidence_quotes": [
                                {
                                    "text": "chapter three names the deferred perk",
                                    "mention_chapter_num": "3",
                                    "mention_word_position": 100,
                                }
                            ],
                        },
                        {
                            "display_position_policy": "source_marker",
                            "mention_word_position": 850,
                            "evidence_quotes": [
                                {
                                    "text": "chapter two source evidence for later miss",
                                    "mention_chapter_num": "2",
                                    "mention_word_position": 850,
                                }
                            ],
                        },
                    ]
                },
                    "3": {
                        "rolls": [
                            {"outcome": "miss", "source_ordinal": 3},
                            {"skipped": True},
                        ]
                    },
            }
        },
    )
    _write_json(
        manual / "chapter_publication_dates.json",
        {
            "_source": "test fixture",
            "_count": 3,
            "chapters": [
                {
                    "chapter_num": str(i),
                    "published_at": f"2024-01-{i:02d}",
                    "published_source": "ao3",
                    "last_edited_at": None,
                    "last_edited_source": None,
                }
                for i in (1, 2, 3)
            ],
        },
    )
    _write_json(
        derived / "timeline.json",
        {
            "_sources_used": [],
            "_count": 0,
            "_first_in_world_date": None,
            "_last_in_world_date": None,
            "entries": [],
        },
    )

    _patch_pipeline_paths(monkeypatch, project, epub)

    derive_roll_facts.main()
    build_chapter_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    rolls_by_source = {
        roll["source_ordinal"]: roll
        for roll in roll_facts["rolls"]
        if roll["source_ordinal"] is not None
    }
    assert rolls_by_source[1]["evidence_quotes"] == [
        {
            "text": "quote-only metadata anchors roll one",
            "mention_chapter_num": "1",
            "mention_word_position": 250,
        }
    ]
    assert rolls_by_source[1]["mechanical_word_position"] == 200
    assert rolls_by_source[1]["mention_word_position"] == 250
    assert rolls_by_source[1]["display_position_policy"] == "mention"
    assert rolls_by_source[1]["display_word_position"] == 250
    assert rolls_by_source[1]["word_position"] == 250

    cross_chapter_hit = rolls_by_source[2]
    assert cross_chapter_hit["mechanical_chapter_num"] == "2"
    assert cross_chapter_hit["mechanical_word_position"] == 200
    assert cross_chapter_hit["mention_chapter_num"] == "3"
    assert cross_chapter_hit["mention_word_position"] == 100
    assert cross_chapter_hit["display_position_policy"] == "mechanical"
    assert cross_chapter_hit["display_chapter_num"] == "2"
    assert cross_chapter_hit["visible_chapter_nums"] == ["2", "3"]
    assert cross_chapter_hit["rolled_perk_name"] == "Deferred Spark"
    assert cross_chapter_hit["evidence_quotes"][0]["mention_chapter_num"] == "3"

    cross_chapter_source = rolls_by_source[3]
    assert cross_chapter_source["mechanical_chapter_num"] == "3"
    assert cross_chapter_source["source_chapter_num"] == "2"
    assert cross_chapter_source["source_chapter_ordinal"] == 2
    assert cross_chapter_source["source_word_position"] == 850
    assert cross_chapter_source["visible_chapter_nums"] == ["2", "3"]
    assert [
        roll["source_ordinal"] for roll in roll_facts["rolls"]
        if roll["source_ordinal"] == 3
    ] == [3]

    chapter_facts = json.loads((derived / "chapter_facts.json").read_text())
    chapters_by_num = {chapter["chapter_num"]: chapter for chapter in chapter_facts["chapters"]}
    chapter_three_source_ordinals = [roll["source_ordinal"] for roll in chapters_by_num["3"]["rolls"]]
    assert {2, 3}.issubset(set(chapter_three_source_ordinals))
    assert chapters_by_num["3"]["skipped_predicted_rolls"] == [
        {
            "slot_index": 2,
            "predicted_ordinal": 4,
            "predicted_label": "P4",
            "source_ordinal": None,
            "source_label": None,
            "roll_ordinal": None,
            "roll_label": None,
            "skipped_ordinal": 1,
            "skipped_label": "X1",
            "mechanical_chapter_num": "3",
            "mechanical_word_position": 700,
            "mechanical_cumulative_word_offset": 2700,
            "predicted_word_position_epub": 2700,
            "reason": "skipped_to_align_narrative",
        }
    ]


def test_fallback_roll_facts_apply_index_aligned_manual_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    chapters = [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0]),
        _fixture_chapter("2", "2 Fixture", sort_key=[2, 0]),
    ]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {
            "chapters": [
                _fixture_section("1", "1 Fixture"),
                _fixture_section("2", "2 Fixture"),
            ]
        },
    )
    _write_json(
        manual / "section_classifications.json",
        {
            "classifications": {
                "1@0": {"counts_for_cp": True},
                "2@0": {"counts_for_cp": True},
            }
        },
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 1200,
                    "epub_offset": 1200,
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                }
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": 1,
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 1200,
                    "epub_offset": 1200,
                }
            ]
        },
    )
    _write_json(derived / "rolls.json", {"rolls": []})
    _write_json(
        derived / "roll_outcomes.json",
        {
            "rolls": [
                {
                    "chapter_num": "2",
                    "word_position": 200,
                    "source": "predicted",
                    "outcome": "miss",
                    "perk": None,
                    "paid_perks": [],
                    "free_perks": [],
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                    "sequence_in_chapter": 1,
                    "rolls_in_chapter": 1,
                    "available_cp": 100,
                    "banked_cp_after_roll": 100,
                }
            ]
        },
    )
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(
        derived / "outstanding_perks_by_chapter.json",
        {
            "chapters": [
                {
                    "chapter_num": "2",
                    "before_chapter": {
                        "total_count": 1,
                        "by_constellation": {
                            "Capstone": [{"name": "Too Costly", "cost": 200}]
                        },
                    },
                }
            ]
        },
    )
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "2": {
                    "rolls": [
                        {
                            "outcome": "miss",
                            "constellation": "Capstone",
                            "mention_chapter_num": "2",
                            "mention_word_position": 123,
                            "display_position_policy": "mention",
                            "evidence_quotes": [
                                {
                                    "text": "the Capstone constellation passed by",
                                    "mention_chapter_num": "2",
                                    "mention_word_position": 123,
                                }
                            ],
                        }
                    ]
                }
            }
        },
    )
    _write_json(manual / "roll_overrides.json", {"roll_overrides": []})
    _patch_pipeline_paths(monkeypatch, project, epub)

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    [roll] = roll_facts["rolls"]
    assert roll["source"] == "roll_outcomes"
    assert roll["source_kind"] == "interpolated"
    assert roll["roll_sequence_in_chapter"] == 1
    assert roll["predicted_ordinal"] == 1
    assert roll["source_ordinal"] is None
    assert roll["outcome"] == "miss"
    assert roll["constellation"] == "Capstone"
    assert roll["constellation_revealed"] is True
    assert roll["mechanical_word_position"] == 200
    assert roll["mention_word_position"] == 123
    assert roll["display_position_policy"] == "mention"
    assert roll["display_word_position"] == 123
    assert roll["evidence_quotes"] == [
        {
            "text": "the Capstone constellation passed by",
            "mention_chapter_num": "2",
            "mention_word_position": 123,
        }
    ]


def test_hit_accounting_normalizes_stale_overrides_after_normalized_cost_units(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    chapters = [_fixture_chapter("2", "2 Fixture", sort_key=[2, 0])]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {"chapters": [_fixture_section("2", "2 Fixture")]},
    )
    _write_json(
        manual / "section_classifications.json",
        {"classifications": {"2@0": {"counts_for_cp": True}}},
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 200,
                    "epub_offset": 200,
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                }
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": 1,
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 200,
                    "epub_offset": 200,
                }
            ]
        },
    )
    _write_json(
        derived / "rolls.json",
        {
            "rolls": [
                {
                    "roll_number": 1,
                    "chapter_num": "2",
                    "kind": "roll",
                    "banked_before": 600,
                    "banked_after": 600,
                    "constellation": "Magic",
                    "constellation_revealed": True,
                    "perks": [
                        {
                            "name": "Forge Spark",
                            "source": "Fixture Jump",
                            "cost": 400,
                            "free": False,
                        },
                        {
                            "name": "Side Equipment",
                            "source": "Fixture Jump",
                            "cost": 300,
                            "cost_unit": "Customization Points",
                            "free": False,
                        },
                    ],
                    "raw": "Roll 1 hit",
                }
            ]
        },
    )
    _write_json(derived / "roll_outcomes.json", {"rolls": []})
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(
        derived / "perk_directory.json",
        {
            "perks": [
                _fixture_directory_perk(
                    name="Forge Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=400,
                ),
                _fixture_directory_perk(
                    name="Side Equipment",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=300,
                ),
            ]
        },
    )
    _write_json(
        derived / "outstanding_perks_by_chapter.json",
        {
            "chapters": [
                {
                    "chapter_num": "2",
                    "before_chapter": {
                        "total_count": 0,
                        "by_constellation": {},
                    },
                }
            ]
        },
    )
    _write_json(manual / "chapter_roll_overrides.json", {"chapter_roll_overrides": {}})
    _write_json(
        manual / "roll_overrides.json",
        {
            "roll_overrides": {
                "curator:0000": {
                    "available_cp": 600,
                    "banked_cp_after_roll": 600,
                    "slot_source": "override",
                }
            }
        },
    )
    _patch_pipeline_paths(monkeypatch, project, epub)

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    [roll] = roll_facts["rolls"]
    assert roll["available_cp"] == 600
    assert roll["banked_cp_after_roll"] == 0
    assert roll["slot_source"] == "override"
    assert roll["purchased_perk_cost_total"] == 700
    assert [
        (perk["name"], perk["cost"], perk.get("cost_unit"))
        for perk in roll["purchased_perks"]
    ] == [
        ("Forge Spark", 400, None),
        ("Side Equipment", 300, "Customization Points"),
    ]

    validation = json.loads((derived / "roll_validation.json").read_text())
    [correction] = validation["hit_accounting_corrections"]
    assert correction["roll_ordinal"] == 1
    assert correction["roll_label"] == "R1"
    assert correction["row_index"] == 0
    assert roll_facts["rolls"][correction["row_index"]]["roll_key"] == "curator:0000"
    assert correction["roll_key"] == "curator:0000"
    assert correction["mechanical_chapter_num"] == "2"
    assert correction["predicted_label"] == "P1"
    assert correction["source_label"] == "S1"
    assert correction["available_cp"] == 600
    assert correction["debit"] == 700
    assert correction["old_banked_cp_after_roll"] == 600
    assert correction["new_banked_cp_after_roll"] == 0


def test_quote_carried_cp_checkpoint_resets_downstream_roll_ledger(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    chapters = [_fixture_chapter("2", "2 Fixture", sort_key=[2, 0])]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {"chapters": [_fixture_section("2", "2 Fixture")]},
    )
    _write_json(
        manual / "section_classifications.json",
        {"classifications": {"2@0": {"counts_for_cp": True}}},
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": slot,
                    "cp_offset": slot * 100,
                    "epub_offset": slot * 100,
                    "roll_number": slot,
                    "roll_trigger_cp_threshold": 100,
                }
                for slot in (1, 2, 3)
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": slot,
                    "chapter_num": "2",
                    "slot_index": slot,
                    "cp_offset": slot * 100,
                    "epub_offset": slot * 100,
                }
                for slot in (1, 2, 3)
            ]
        },
    )
    _write_json(
        derived / "rolls.json",
        {
            "rolls": [
                {
                    "roll_number": slot,
                    "chapter_num": "2",
                    "kind": "miss",
                    "banked_before": slot * 100,
                    "banked_after": slot * 100,
                    "constellation": "Magic",
                    "constellation_revealed": True,
                    "perks": [],
                    "raw": f"Roll {slot} miss",
                }
                for slot in (1, 2, 3)
            ]
        },
    )
    _write_json(derived / "roll_outcomes.json", {"rolls": []})
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(
        derived / "outstanding_perks_by_chapter.json",
        {
            "chapters": [
                {
                    "chapter_num": "2",
                    "before_chapter": {
                        "total_count": 0,
                        "by_constellation": {},
                    },
                }
            ]
        },
    )
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "2": {
                    "rolls": [
                        {
                            "evidence_quotes": [
                                {
                                    "text": "There are currently 25 points banked.",
                                    "mention_chapter_num": "2",
                                    "mention_word_position": 900,
                                    "cp_ledger_checkpoint": {
                                        "kind": "post_roll_banked_cp_reset",
                                        "banked_cp_after_roll": 25,
                                    },
                                }
                            ]
                        },
                        {},
                        {},
                    ]
                }
            }
        },
    )
    _write_json(manual / "roll_overrides.json", {"roll_overrides": {}})
    _patch_pipeline_paths(monkeypatch, project, epub)

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    rolls = roll_facts["rolls"]
    assert [
        (roll["roll_label"], roll["available_cp"], roll["banked_cp_after_roll"])
        for roll in rolls
    ] == [
        ("R1", 25, 25),
        ("R2", 30, 30),
        ("R3", 35, 35),
    ]
    assert rolls[0]["evidence_quotes"][0]["cp_ledger_checkpoint"] == {
        "kind": "post_roll_banked_cp_reset",
        "banked_cp_after_roll": 25,
    }

    validation = json.loads((derived / "roll_validation.json").read_text())
    assert validation["cp_ledger_checkpoint_applications"] == [
        {
            "row_index": 0,
            "roll_ordinal": 1,
            "roll_label": "R1",
            "predicted_ordinal": 1,
            "roll_key": "curator:0000",
            "mechanical_chapter_num": "2",
            "predicted_label": "P1",
            "source_ordinal": 1,
            "source_label": "S1",
            "old_available_cp": 100,
            "old_banked_cp_after_roll": 100,
            "new_available_cp": 25,
            "new_banked_cp_after_roll": 25,
            "checkpoint": {
                "kind": "post_roll_banked_cp_reset",
                "banked_cp_after_roll": 25,
            },
        }
    ]


def test_manual_obtained_perk_assignment_pins_hit_to_override_slot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    chapters = [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0], word_count=10000),
        _fixture_chapter("2", "2 Fixture", sort_key=[2, 0]),
    ]
    _write_json(derived / "chapters.json", {"chapters": chapters})
    _write_json(
        derived / "chapter_sections.json",
        {
            "chapters": [
                _fixture_section("1", "1 Fixture", word_count=10000),
                _fixture_section("2", "2 Fixture"),
            ]
        },
    )
    _write_json(
        manual / "section_classifications.json",
        {
            "classifications": {
                "1@0": {"counts_for_cp": True},
                "2@0": {"counts_for_cp": True},
            }
        },
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": idx,
                    "cp_offset": 10000 + idx * 200,
                    "epub_offset": 10000 + idx * 200,
                    "roll_number": idx,
                    "roll_trigger_cp_threshold": 100,
                }
                for idx in range(1, 5)
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": idx,
                    "chapter_num": "2",
                    "slot_index": idx,
                    "cp_offset": 10000 + idx * 200,
                    "epub_offset": 10000 + idx * 200,
                }
                for idx in range(1, 5)
            ]
        },
    )
    _write_json(derived / "rolls.json", {"rolls": []})
    _write_json(
        derived / "roll_outcomes.json",
        {
            "rolls": [
                {
                    "chapter_num": "2",
                    "word_position": 10000 + idx * 200,
                    "source": "predicted",
                    "outcome": "miss",
                    "perk": None,
                    "paid_perks": [],
                    "free_perks": [],
                    "roll_number": idx,
                    "roll_trigger_cp_threshold": 100,
                    "sequence_in_chapter": idx,
                    "rolls_in_chapter": 4,
                    "available_cp": 1000,
                    "banked_cp_after_roll": 1000,
                }
                for idx in range(1, 5)
            ]
        },
    )
    _write_json(
        derived / "obtained_perks.json",
        {
            "perks": [
                _fixture_perk(
                    sequence=1,
                    chapter_num="2",
                    name="Pinned Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=100,
                ),
                {
                    **_fixture_perk(
                        sequence=1,
                        chapter_num="2",
                        name="Free Suit",
                        jump="Fixture Jump",
                        constellation="Clothing",
                        cost=0,
                    ),
                    "free": True,
                    "cost_text": "Free",
                },
            ]
        },
    )
    _write_json(
        derived / "perk_directory.json",
        {
            "perks": [
                _fixture_directory_perk(
                    name="Pinned Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=100,
                ),
                _fixture_directory_perk(
                    name="Free Suit",
                    jump="Fixture Jump",
                    constellation="Clothing",
                    cost=0,
                ),
            ]
        },
    )
    _write_json(derived / "outstanding_perks_by_chapter.json", {"chapters": []})
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "2": {
                    "rolls": [
                        {"outcome": "miss", "constellation": "Vehicles"},
                        {"outcome": "miss", "constellation": "Toolkits"},
                        {
                            "outcome": "hit",
                            "constellation": "Magic",
                            "perks": ["Pinned Spark"],
                            "evidence_quotes": [
                                {
                                    "text": "the pinned spark was secured",
                                    "mention_chapter_num": "2",
                                    "mention_word_position": 600,
                                }
                            ],
                        },
                    ]
                }
            }
        },
    )
    _write_json(manual / "roll_overrides.json", {"roll_overrides": []})
    _patch_pipeline_paths(monkeypatch, project, epub)
    monkeypatch.setattr(
        derive_roll_facts,
        "_load_cp_words_per_chapter",
        lambda: {"1 Fixture": 10000, "2 Fixture": 1000},
    )

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    chapter_rolls = [
        roll for roll in roll_facts["rolls"]
        if roll["mechanical_chapter_num"] == "2"
    ]
    assert [roll["outcome"] for roll in chapter_rolls] == ["miss", "miss", "hit"]
    pinned = chapter_rolls[2]
    assert pinned["rolled_perk_name"] == "Pinned Spark"
    assert pinned["free_perks"] == [
        {
            "id": "Clothing__Fixture_Jump__Free_Suit",
            "name": "Free Suit",
            "jump": "Fixture Jump",
            "constellation": "Clothing",
        }
    ]
    assert pinned["available_cp"] > pinned["banked_cp_after_roll"]


def test_blank_override_slot_preserves_manual_obtained_perk_index(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    _write_json(
        derived / "chapters.json",
        {"chapters": [_fixture_chapter("2", "2 Fixture", sort_key=[2, 0])]},
    )
    _write_json(
        derived / "chapter_sections.json",
        {"chapters": [_fixture_section("2", "2 Fixture", word_count=1000)]},
    )
    _write_json(
        manual / "section_classifications.json",
        {"classifications": {"2@0": {"counts_for_cp": True}}},
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": idx,
                    "cp_offset": idx * 100,
                    "epub_offset": idx * 100,
                    "roll_number": idx,
                    "roll_trigger_cp_threshold": 100,
                }
                for idx in range(1, 4)
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": idx,
                    "chapter_num": "2",
                    "slot_index": idx,
                    "cp_offset": idx * 100,
                    "epub_offset": idx * 100,
                }
                for idx in range(1, 4)
            ]
        },
    )
    _write_json(derived / "rolls.json", {"rolls": []})
    _write_json(
        derived / "roll_outcomes.json",
        {
            "rolls": [
                {
                    "chapter_num": "2",
                    "word_position": idx * 100,
                    "source": "predicted",
                    "outcome": "miss",
                    "perk": None,
                    "paid_perks": [],
                    "free_perks": [],
                    "roll_number": idx,
                    "roll_trigger_cp_threshold": 100,
                    "sequence_in_chapter": idx,
                    "rolls_in_chapter": 3,
                    "available_cp": 1000,
                    "banked_cp_after_roll": 1000,
                }
                for idx in range(1, 4)
            ]
        },
    )
    _write_json(
        derived / "obtained_perks.json",
        {
            "perks": [
                _fixture_perk(
                    sequence=1,
                    chapter_num="2",
                    name="Pinned Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=100,
                ),
            ]
        },
    )
    _write_json(
        derived / "perk_directory.json",
        {
            "perks": [
                _fixture_directory_perk(
                    name="Pinned Spark",
                    jump="Fixture Jump",
                    constellation="Magic",
                    cost=100,
                ),
            ]
        },
    )
    _write_json(derived / "outstanding_perks_by_chapter.json", {"chapters": []})
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "2": {
                    "rolls": [
                        {},
                        {
                            "outcome": "hit",
                            "constellation": "Magic",
                            "perks": ["Pinned Spark"],
                        },
                    ]
                }
            }
        },
    )
    _write_json(manual / "roll_overrides.json", {"roll_overrides": []})
    _patch_pipeline_paths(monkeypatch, project, epub)
    monkeypatch.setattr(
        derive_roll_facts,
        "_load_cp_words_per_chapter",
        lambda: {"2 Fixture": 1000},
    )

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    pinned = next(
        roll for roll in roll_facts["rolls"]
        if roll["rolled_perk_name"] == "Pinned Spark"
    )
    assert pinned["predicted_ordinal"] == 2
    assert pinned["mechanical_word_position"] == 200


def test_fallback_roll_facts_apply_quote_only_manual_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import derive_roll_facts

    project = tmp_path / "project"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = project / "data" / "raw" / "fixture.epub"
    _write_json(
        derived / "chapters.json",
        {"chapters": [_fixture_chapter("2", "2 Fixture", sort_key=[2, 0])]},
    )
    _write_json(
        derived / "chapter_sections.json",
        {"chapters": [_fixture_section("2", "2 Fixture")]},
    )
    _write_json(
        manual / "section_classifications.json",
        {"classifications": {"2@0": {"counts_for_cp": True}}},
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 200,
                    "epub_offset": 200,
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                }
            ]
        },
    )
    _write_json(
        derived / "roll_text_evidence.json",
        {
            "rolls": [
                {
                    "roll_number": 1,
                    "chapter_num": "2",
                    "slot_index": 1,
                    "cp_offset": 200,
                    "epub_offset": 200,
                }
            ]
        },
    )
    _write_json(derived / "rolls.json", {"rolls": []})
    _write_json(
        derived / "roll_outcomes.json",
        {
            "rolls": [
                {
                    "chapter_num": "2",
                    "word_position": 200,
                    "source": "predicted",
                    "outcome": "miss",
                    "perk": None,
                    "paid_perks": [],
                    "free_perks": [],
                    "roll_number": 1,
                    "roll_trigger_cp_threshold": 100,
                    "sequence_in_chapter": 1,
                    "rolls_in_chapter": 1,
                    "available_cp": 100,
                    "banked_cp_after_roll": 100,
                }
            ]
        },
    )
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perk_directory.json", {"perks": []})
    _write_json(derived / "outstanding_perks_by_chapter.json", {"chapters": []})
    _write_json(
        manual / "chapter_roll_overrides.json",
        {
            "chapter_roll_overrides": {
                "2": {
                    "rolls": [
                        {
                            "evidence_quotes": [
                                {
                                    "text": "quote-only fallback evidence",
                                    "mention_chapter_num": "2",
                                    "mention_word_position": 123,
                                }
                            ]
                        }
                    ]
                }
            }
        },
    )
    _write_json(manual / "roll_overrides.json", {"roll_overrides": []})
    _patch_pipeline_paths(monkeypatch, project, epub)

    derive_roll_facts.main()

    roll_facts = json.loads((derived / "roll_facts.json").read_text())
    [roll] = roll_facts["rolls"]
    assert roll["source"] == "roll_outcomes"
    assert roll["source_kind"] == "interpolated"
    assert roll["mechanical_word_position"] == 200
    assert roll["outcome"] == "miss"
    assert roll["evidence_quotes"] == [
        {
            "text": "quote-only fallback evidence",
            "mention_chapter_num": "2",
            "mention_word_position": 123,
        }
    ]


def test_survey_designations_flow_into_visualization_roll_perks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_chapter_facts, derive_roll_facts
    from scripts.build_visualization_facts import build as build_visualization_facts

    project = tmp_path / "project"
    raw = project / "data" / "raw"
    derived = project / "data" / "derived"
    manual = project / "data" / "manual"
    epub = raw / "fixture.epub"
    xlsx = raw / "Brocktons_Celestial_Forge_Reference.xlsx"

    raw.mkdir(parents=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr("EPUB/nav.xhtml", '<nav><a href="chap_1.xhtml">1 Fixture</a></nav>')
        zf.writestr("EPUB/chap_1.xhtml", "<p>Fixture chapter body.</p>")

    wb = Workbook()
    ws = wb.active
    ws.title = "AI Perk Names"
    ws.append([
        "Order Obtained", "Constellation", "Sub-Order", "Cost", "Sub-perk",
        "Name", None, None, None, "Constellation", "AI Designation",
    ])
    ws.append([250, "E", 18, "Null", "Beta", "‘Moon Jump’", None, None, None, "Crafting Skills", "E"])
    ws.append([261, "G", 15, "Hex", "Alpha", "‘Fixture Infusion’", None, None, None, "Magic Constellation", "G"])
    wb.save(xlsx)

    _write_json(derived / "chapters.json", {"chapters": [
        _fixture_chapter("1", "1 Fixture", sort_key=[1, 0]),
    ]})
    _write_json(derived / "chapter_sections.json", {"chapters": [
        _fixture_section("1", "1 Fixture"),
    ]})
    _write_json(manual / "section_classifications.json",
                {"classifications": {"1@0": {"counts_for_cp": True}}})
    _write_json(derived / "predicted_rolls.json", {
        "_count": 1,
        "_total_cp_words": 1000,
        "_total_epub_words": 1000,
        "_regime_summary": {"1": "fixture", "2": "fixture", "3": "fixture"},
        "predicted": [
            {
                "chapter_num": "1",
                "slot_index": 1,
                "cp_offset": 200,
                "epub_offset": 200,
                "roll_number": 1,
                "roll_trigger_cp_threshold": 100,
                "cp_rule_regime": 1,
            }
        ],
    })
    _write_json(derived / "roll_text_evidence.json", {
        "rolls": [
            {
                "roll_number": 1,
                "chapter_num": "1",
                "slot_index": 1,
                "cp_offset": 200,
                "epub_offset": 200,
            }
        ]
    })
    _write_json(derived / "rolls.json", {
        "rolls": [
            {
                "roll_number": 1,
                "chapter_num": "1",
                "kind": "roll",
                "banked_before": 600,
                "banked_after": 0,
                "constellation": "Magic",
                "constellation_revealed": True,
                "perks": [
                    {
                        "name": "Fixture Infusion",
                        "source": "Fixture Jump",
                        "cost": 600,
                        "free": False,
                    },
                    {
                        "name": "Moon Jump",
                        "source": "Fixture Jump",
                        "cost": 0,
                        "free": True,
                    },
                ],
                "raw": "Roll 1 hit",
            }
        ]
    })
    _write_json(derived / "roll_outcomes.json", {"rolls": []})
    _write_json(derived / "obtained_perks.json", {"perks": [
        _fixture_perk(
            sequence=1,
            chapter_num="1",
            name="Fixture Infusion",
            jump="Fixture Jump",
            constellation="Magic",
            cost=600,
        )
    ]})
    _write_json(derived / "perk_directory.json", {"perks": [
        _fixture_directory_perk(
            name="Fixture Infusion",
            jump="Fixture Jump",
            constellation="Magic",
            cost=600,
        ),
        {
            **_fixture_directory_perk(
                name="Moon Jump",
                jump="Fixture Jump",
                constellation="Crafting",
                cost=0,
            ),
            "free": True,
            "cost_text": "Free",
        },
    ]})
    _write_json(derived / "outstanding_perks_by_chapter.json", {"chapters": []})
    _write_json(manual / "chapter_roll_overrides.json", {"chapter_roll_overrides": {}})
    _write_json(manual / "roll_overrides.json", {"roll_overrides": []})
    _write_json(manual / "chapter_publication_dates.json", {
        "_source": "test fixture",
        "_count": 1,
        "chapters": [{
            "chapter_num": "1",
            "published_at": "2024-01-01",
            "published_source": "ao3",
            "last_edited_at": None,
            "last_edited_source": None,
        }],
    })
    _write_json(derived / "timeline.json", {
        "_sources_used": [],
        "_count": 0,
        "_first_in_world_date": None,
        "_last_in_world_date": None,
        "entries": [],
    })
    _write_json(derived / "constellation_wireframes.json", {
        "cluster_constellations": [],
        "jump_constellations": [],
    })
    _write_json(derived / "data_package.json", {
        "package_id": "fixture-pkg",
        "version_label": "fixture label",
        "package_date": "20260101",
        "build_number": 1,
        "source_commit": "deadbeef",
        "story_chapter_ordinal": 1,
        "story_chapter_num": "1",
        "story_chapter_title": "1 Fixture",
    })

    _patch_pipeline_paths(monkeypatch, project, epub)
    monkeypatch.setattr(derive_roll_facts, "SURVEY_DESIGNATIONS", xlsx, raising=False)

    derive_roll_facts.main()
    build_chapter_facts.main()
    bundle = build_visualization_facts(derived)

    roll = bundle["chapters"][0]["rolls"][0]
    assert roll["purchased_perks"][0]["survey_designation"]["code"] == (
        "261-G-15-Hex-Alpha"
    )
    assert roll["free_perks"][0]["survey_designation"]["code"] == (
        "250-E-18-Null-Beta"
    )

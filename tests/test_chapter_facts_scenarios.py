from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


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
        "roll_number": roll_number,
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
        "source_roll_index": sequence,
        "source_word_position": display_word_position,
        "source_cumulative_word_offset": display_word_position,
        "visible_chapter_nums": [chapter_num],
        "purchased_perk_id": None,
        "purchased_perks": [],
        "purchased_perk_cost_total": None,
        "purchased_perk_jump": None,
        "free_perks": [],
        "word_position": mechanical_word_position,
        "predicted_word_position_epub": mechanical_word_position,
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

    build_chapter_facts.main()

    output = json.loads((derived / "chapter_facts.json").read_text())
    by_chapter = {chapter["chapter_num"]: chapter for chapter in output["chapters"]}

    assert by_chapter["1"]["rolls"][0]["display_cumulative_word_offset"] == 250
    assert by_chapter["1"]["rolls"][0]["cumulative_word_offset"] == 250
    assert by_chapter["2"]["rolls"][0]["display_cumulative_word_offset"] == 1500
    assert by_chapter["2"]["skipped_predicted_rolls"] == [
        {
            "slot_index": 1,
            "roll_number": 2,
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 500,
            "mechanical_cumulative_word_offset": 1500,
            "predicted_word_position_epub": 1500,
            "reason": "skipped_to_align_narrative",
        }
    ]
    assert by_chapter["1"]["model_validation"]["current_discrepancy"] is True
    assert by_chapter["2"]["model_validation"]["prior_discrepancy"] is True
    assert by_chapter["2"]["model_validation"]["first_discrepancy_chapter_num"] == "1"

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
                            "source_deferred_to_chapter": "3",
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
                        {"source_roll_number": 3},
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
    rolls_by_number = {
        roll["roll_number"]: roll
        for roll in roll_facts["rolls"]
        if roll["roll_number"] is not None
    }
    assert rolls_by_number[1]["evidence_quotes"] == [
        {
            "text": "quote-only metadata anchors roll one",
            "mention_chapter_num": "1",
            "mention_word_position": 250,
        }
    ]
    assert rolls_by_number[1]["mechanical_word_position"] == 200
    assert rolls_by_number[1]["mention_word_position"] == 250
    assert rolls_by_number[1]["display_position_policy"] == "mention"
    assert rolls_by_number[1]["display_word_position"] == 250
    assert rolls_by_number[1]["word_position"] == 250

    deferred_hit = rolls_by_number[2]
    assert deferred_hit["mechanical_chapter_num"] == "2"
    assert deferred_hit["mechanical_word_position"] == 200
    assert deferred_hit["mention_chapter_num"] == "3"
    assert deferred_hit["mention_word_position"] == 100
    assert deferred_hit["display_position_policy"] == "mechanical"
    assert deferred_hit["display_chapter_num"] == "2"
    assert deferred_hit["visible_chapter_nums"] == ["2", "3"]
    assert deferred_hit["rolled_perk_name"] == "Deferred Spark"
    assert deferred_hit["evidence_quotes"][0]["mention_chapter_num"] == "3"

    source_deferred = rolls_by_number[3]
    assert source_deferred["mechanical_chapter_num"] == "3"
    assert source_deferred["source_chapter_num"] == "2"
    assert source_deferred["source_roll_index"] == 2
    assert source_deferred["source_word_position"] == 850
    assert source_deferred["visible_chapter_nums"] == ["2", "3"]
    assert [
        roll["roll_number"] for roll in roll_facts["rolls"]
        if roll["roll_number"] == 3
    ] == [3]

    chapter_facts = json.loads((derived / "chapter_facts.json").read_text())
    chapters_by_num = {chapter["chapter_num"]: chapter for chapter in chapter_facts["chapters"]}
    chapter_three_roll_numbers = [roll["roll_number"] for roll in chapters_by_num["3"]["rolls"]]
    assert {2, 3}.issubset(set(chapter_three_roll_numbers))
    assert chapters_by_num["3"]["skipped_predicted_rolls"] == [
        {
            "slot_index": 2,
            "roll_number": 4,
            "mechanical_chapter_num": "3",
            "mechanical_word_position": 700,
            "mechanical_cumulative_word_offset": 2700,
            "predicted_word_position_epub": 2700,
            "reason": "skipped_to_align_narrative",
        }
    ]

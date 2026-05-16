from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import scripts.forge_curator.app as forge_app
import scripts.forge_curator.data_loader as data_loader
import scripts.forge_curator.persistence as persistence


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _chapter_words(chapter_num: str) -> list[str]:
    base = [
        f"chapter{chapter_num}",
        "forge",
        "motes",
        "connection",
        "constellation",
        "evidence",
        "marker",
        "cursor",
    ]
    return [base[index % len(base)] for index in range(80)]


def _chapter_html(chapter_num: str) -> str:
    return f"<p>{' '.join(_chapter_words(chapter_num))}</p>"


def _section(chapter_num: str) -> dict:
    return {
        "header": None,
        "word_count": len(_chapter_words(chapter_num)),
        "classification": "mc_pov",
        "confidence": "fixture",
        "structural_markers": [],
        "auto_header_word_count": 0,
    }


def _chapter_fact(chapter_num: str, title: str, *, cp_start: int) -> dict:
    word_count = len(_chapter_words(chapter_num))
    return {
        "chapter_num": chapter_num,
        "full_title": title,
        "cp_earning_word_count": word_count,
        "total_word_count": word_count,
        "banked_cp_at_start": 0,
        "banked_cp_at_end": 0,
        "model_validation": {
            "status": "ok",
            "current_discrepancy": False,
            "raw_current_discrepancy": False,
            "prior_discrepancy": False,
            "first_discrepancy_chapter_num": None,
        },
        "sections": [
            {
                "section_index": 0,
                "header": None,
                "word_count": word_count,
                "cp_earning_word_count": word_count,
                "counts_for_cp": True,
                "span_overrides": [],
                "classification": "mc_pov",
                "classification_confidence": "fixture",
                "structural_markers": [],
            }
        ],
        "rolls": [_roll_fact(chapter_num, cp_start=cp_start)],
        "skipped_predicted_rolls": [],
    }


def _roll_fact(chapter_num: str, *, cp_start: int) -> dict:
    local_word = 20
    cumulative_word = cp_start + local_word
    return {
        "chapter_num": chapter_num,
        "roll_sequence_in_chapter": 1,
        "source_row_index": 1,
        "roll_number": int(chapter_num),
        "outcome": "miss",
        "constellation": "Magic",
        "mechanical_chapter_num": chapter_num,
        "mechanical_word_position": local_word,
        "mechanical_cumulative_word_offset": cumulative_word,
        "mention_chapter_num": chapter_num,
        "mention_word_position": local_word,
        "display_position_policy": "mechanical",
        "display_chapter_num": chapter_num,
        "display_word_position": local_word,
        "display_cumulative_word_offset": cumulative_word,
        "source_chapter_num": chapter_num,
        "source_roll_index": 1,
        "source_word_position": local_word,
        "source_cumulative_word_offset": cumulative_word,
        "visible_chapter_nums": [chapter_num],
        "purchased_perk_id": None,
        "purchased_perks": [],
        "purchased_perk_cost_total": None,
        "purchased_perk_jump": None,
        "free_perks": [],
        "word_position": local_word,
        "cumulative_word_offset": cumulative_word,
        "predicted_word_position_epub": cumulative_word,
        "display_word_position_epub": cumulative_word,
        "predicted_char_offset_in_chapter": None,
        "anchor_char_offset_in_chapter": None,
        "evidence_kind": "direct",
        "evidence_quotes": [
            {
                "text": "forge motes connection",
                "mention_chapter_num": chapter_num,
                "mention_word_position": local_word,
            }
        ],
        "available_cp": 100,
        "banked_cp_after_roll": 0,
        "rolled_perk_name": None,
        "rolled_perk_cost": None,
        "miss_cost_estimate": 100,
        "rolls_in_chapter": 1,
        "source": "curator_rolls",
        "fact_source": "curator_rolls",
        "source_kind": "roll",
    }


@dataclass(frozen=True)
class ForgeCuratorFixture:
    root: Path
    raw: Path
    derived: Path
    manual: Path
    epub: Path
    snapshot_path: Path
    state_path: Path

    def app(self, chapter_num: str = "1") -> forge_app.ForgeCuratorApp:
        return forge_app.ForgeCuratorApp(
            start_chapter=chapter_num,
            state_path=self.state_path,
        )

    def loaded_app(self, chapter_num: str = "1") -> forge_app.ForgeCuratorApp:
        app = self.app(chapter_num)
        app._load_chapter(chapter_num)
        return app


def forge_curator_fixture(tmp_path: Path, monkeypatch) -> ForgeCuratorFixture:
    root = tmp_path / "forge-curator-fixture"
    raw = root / "data" / "raw"
    derived = root / "data" / "derived"
    manual = root / "data" / "manual"
    epub = raw / "fixture.epub"
    snapshot_path = manual / ".forge_curator_snapshot.json"
    state_path = manual / ".forge_curator_state.json"

    raw.mkdir(parents=True, exist_ok=True)
    manual.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(epub, "w") as zf:
        zf.writestr(
            "EPUB/nav.xhtml",
            (
                '<nav><a href="chap_1.xhtml">1 Fixture</a>'
                '<a href="chap_2.xhtml">2 Fixture</a></nav>'
            ),
        )
        zf.writestr("EPUB/chap_1.xhtml", _chapter_html("1"))
        zf.writestr("EPUB/chap_2.xhtml", _chapter_html("2"))

    chapters = [
        {
            "chapter_num": "1",
            "full_title": "1 Fixture",
            "epub_href": "chap_1.xhtml",
            "sort_key": [1, 0],
        },
        {
            "chapter_num": "2",
            "full_title": "2 Fixture",
            "epub_href": "chap_2.xhtml",
            "sort_key": [2, 0],
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
                    "epub_href": "chap_1.xhtml",
                    "total_word_count": len(_chapter_words("1")),
                    "sections": [_section("1")],
                },
                {
                    "chapter_num": "2",
                    "full_title": "2 Fixture",
                    "epub_href": "chap_2.xhtml",
                    "total_word_count": len(_chapter_words("2")),
                    "sections": [_section("2")],
                },
            ]
        },
    )
    _write_json(
        derived / "chapter_facts.json",
        {
            "schema_version": 1,
            "shadow_periods": [],
            "in_world_timeline": {
                "_sources_used": [],
                "_count": 0,
                "_first_in_world_date": None,
                "_last_in_world_date": None,
                "entries": [],
            },
            "chapters": [
                _chapter_fact("1", "1 Fixture", cp_start=0),
                _chapter_fact("2", "2 Fixture", cp_start=len(_chapter_words("1"))),
            ],
        },
    )
    _write_json(
        derived / "roll_facts.json",
        {
            "rolls": [
                _roll_fact("1", cp_start=0),
                _roll_fact("2", cp_start=len(_chapter_words("1"))),
            ]
        },
    )
    _write_json(
        derived / "predicted_rolls.json",
        {
            "predicted": [
                {"chapter_num": "1", "word_position": 20, "roll_number": 1},
                {
                    "chapter_num": "2",
                    "word_position": len(_chapter_words("1")) + 20,
                    "roll_number": 2,
                },
                {
                    "chapter_num": "2",
                    "word_position": len(_chapter_words("1")) + 40,
                    "roll_number": 3,
                },
            ]
        },
    )
    _write_json(
        derived / "roll_validation.json",
        {"chapter_checks": [{"chapter_num": "1"}, {"chapter_num": "2"}]},
    )
    _write_json(derived / "obtained_perks.json", {"perks": []})
    _write_json(derived / "perks_catalog.json", {"perks": []})
    _write_json(derived / "roll_outcomes.json", {"rolls": []})
    _write_json(derived / "outstanding_perks_by_chapter.json", {"chapters": []})
    _write_json(
        manual / "chapter_roll_overrides.json",
        {"chapter_roll_overrides": {}},
    )
    _write_json(manual / "regime_transitions.json", {"transitions": []})
    _write_json(manual / "section_classifications.json", {"classifications": {}})

    monkeypatch.setattr(data_loader, "ROOT", root)
    monkeypatch.setattr(data_loader, "EPUB_PATH", epub)
    monkeypatch.setattr(data_loader, "CHAPTER_SECTIONS", derived / "chapter_sections.json")
    monkeypatch.setattr(data_loader, "CHAPTERS", derived / "chapters.json")
    monkeypatch.setattr(data_loader, "ROLL_FACTS", derived / "roll_facts.json")
    monkeypatch.setattr(data_loader, "PREDICTED", derived / "predicted_rolls.json")
    monkeypatch.setattr(data_loader, "CHAPTER_FACTS", derived / "chapter_facts.json")
    monkeypatch.setattr(data_loader, "ROLL_VALIDATION", derived / "roll_validation.json")
    monkeypatch.setattr(data_loader, "OBTAINED_PERKS", derived / "obtained_perks.json")
    monkeypatch.setattr(data_loader, "PERKS_CATALOG", derived / "perks_catalog.json")
    monkeypatch.setattr(data_loader, "ROLL_OUTCOMES", derived / "roll_outcomes.json")
    monkeypatch.setattr(data_loader, "OUTSTANDING_PERKS", derived / "outstanding_perks_by_chapter.json")
    monkeypatch.setattr(data_loader, "CHAPTER_ROLL_OVERRIDES", manual / "chapter_roll_overrides.json")
    monkeypatch.setattr(data_loader, "REGIME_TRANSITIONS", manual / "regime_transitions.json")
    monkeypatch.setattr(forge_app, "STATE_FILE", state_path)
    monkeypatch.setattr(forge_app, "SNAPSHOT_PATH", snapshot_path)
    monkeypatch.setattr(persistence, "MANUAL", manual)
    monkeypatch.setattr(persistence, "CHAPTER_ROLL_OVERRIDES", manual / "chapter_roll_overrides.json")
    monkeypatch.setattr(persistence, "SECTION_CLASSIFICATIONS", manual / "section_classifications.json")
    monkeypatch.setattr(persistence, "JOURNAL_DIR", manual / ".session_journals")

    return ForgeCuratorFixture(
        root=root,
        raw=raw,
        derived=derived,
        manual=manual,
        epub=epub,
        snapshot_path=snapshot_path,
        state_path=state_path,
    )

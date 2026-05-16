from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_chapter_sections import _classify_section, _split_sections, _text  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _chapter_sections_from_html(
    *,
    chapter_num: str,
    full_title: str,
    html: str,
) -> dict:
    sections = []
    total_words = 0
    for header, start, end in _split_sections(html):
        section_text = _text(html[start:end])
        section = _classify_section(
            header,
            section_text,
            implicit_header=full_title if header is None else None,
        )
        sections.append(asdict(section))
        total_words += section.word_count
    return {
        "chapter_num": chapter_num,
        "full_title": full_title,
        "epub_href": f"{chapter_num}.xhtml",
        "total_word_count": total_words,
        "sections": sections,
    }


def test_extract_classify_predict_uses_curated_section_eligibility(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_section_classifications
    from scripts import predict_rolls

    root = tmp_path / "project"
    sections_path = root / "data" / "derived" / "chapter_sections.json"
    classifications_path = root / "data" / "manual" / "section_classifications.json"
    rolls_path = root / "data" / "derived" / "rolls.json"
    obtained_path = root / "data" / "derived" / "obtained_perks.json"

    eligible_body = " ".join(["forge"] * 4000)
    non_eligible_addendum = " ".join(["forum"] * 1200)
    html = (
        "<p>1 Fixture</p>"
        f"<p>{eligible_body}</p>"
        "<p>Addendum PHO</p>"
        f"<p>{non_eligible_addendum}</p>"
        "<p>Jumpchain abilities this chapter:</p>"
        "<p>Synthetic Perk (Fixture Jump) 100:</p>"
        "<p>Footer text.</p>"
    )
    chapter = _chapter_sections_from_html(
        chapter_num="1",
        full_title="1 Fixture",
        html=html,
    )
    _write_json(
        sections_path,
        {
            "chapters": [chapter],
        },
    )
    _write_json(rolls_path, {"rolls": []})
    _write_json(obtained_path, {"perks": []})

    monkeypatch.setattr(build_section_classifications, "ROOT", root)
    monkeypatch.setattr(build_section_classifications, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(build_section_classifications, "ROLLS_JSON", rolls_path)
    monkeypatch.setattr(build_section_classifications, "OBTAINED_JSON", obtained_path)
    monkeypatch.setattr(build_section_classifications, "OUT", classifications_path)
    build_section_classifications.main()

    monkeypatch.setattr(predict_rolls, "ROOT", root)
    monkeypatch.setattr(predict_rolls, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(predict_rolls, "CLASSIFICATIONS_JSON", classifications_path)
    cp_words = predict_rolls._load_cp_words_per_chapter()

    assert cp_words == {"1 Fixture": 4000}

    predicted = predict_rolls.predict_chapter(
        "1",
        chapters=[
            {
                "chapter_num": "1",
                "full_title": "1 Fixture",
                "sort_key": [1, 0],
            }
        ],
        obtained_perks=[],
        cp_words=cp_words,
        transitions=[],
        multi_overrides={"chapter_roll_overrides": {}},
    )

    assert [roll["word_position"] for roll in predicted["predicted"]] == [2000, 4000]
    assert [roll["roll_trigger_cp_threshold"] for roll in predicted["predicted"]] == [
        100,
        100,
    ]

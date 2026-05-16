from __future__ import annotations

import json
from pathlib import Path


def _section(
    *,
    header: str | None,
    word_count: int,
    sample: str = "Joe worked at the bench.",
    auto_header_word_count: int = 0,
    fp_count: int = 4,
    tp_count: int = 0,
    structural_markers: list[str] | None = None,
) -> dict:
    return {
        "header": header,
        "word_count": word_count,
        "sample": sample,
        "fp_count": fp_count,
        "tp_count": tp_count,
        "structural_markers": structural_markers or [],
        "auto_header_word_count": auto_header_word_count,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def test_build_section_classifications_generates_header_spans_and_preserves_manual_spans(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_section_classifications as classifier

    root = tmp_path / "project"
    out_path = root / "data" / "manual" / "section_classifications.json"
    _write_json(
        out_path,
        {
            "classifications": {
                "1@0": {
                    "span_overrides": [
                        {
                            "word_offset_start": 10,
                            "word_offset_end": 20,
                            "counts_for_cp": False,
                            "reason_code": "author_note",
                            "note": "curated fixture span",
                        }
                    ]
                }
            }
        },
    )
    sections_doc = {
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "1 Fixture",
                "sections": [
                    _section(
                        header=None,
                        word_count=1000,
                        sample="1 Fixture Joe began working.",
                        auto_header_word_count=2,
                    ),
                    _section(
                        header="Jumpchain abilities this chapter:",
                        word_count=200,
                        sample="Perk list.",
                        auto_header_word_count=4,
                    ),
                ],
            }
        ]
    }

    sections_path = root / "data" / "derived" / "chapter_sections.json"
    rolls_path = root / "data" / "derived" / "rolls.json"
    obtained_path = root / "data" / "derived" / "obtained_perks.json"
    _write_json(sections_path, sections_doc)
    _write_json(rolls_path, {"rolls": []})
    _write_json(obtained_path, {"perks": []})

    monkeypatch.setattr(classifier, "ROOT", root)
    monkeypatch.setattr(classifier, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(classifier, "ROLLS_JSON", rolls_path)
    monkeypatch.setattr(classifier, "OBTAINED_JSON", obtained_path)
    monkeypatch.setattr(classifier, "OUT", out_path)

    classifier.main()
    classifications = json.loads(out_path.read_text())["classifications"]

    assert classifications["1@0"]["counts_for_cp"] is True
    assert classifications["1@0"]["span_overrides"] == [
        {
            "word_offset_start": 0,
            "word_offset_end": 2,
            "counts_for_cp": False,
            "reason_code": "chapter_title_header",
            "note": "generated from chapter section header",
            "excerpt": "",
        },
        {
            "word_offset_start": 10,
            "word_offset_end": 20,
            "counts_for_cp": False,
            "reason_code": "author_note",
            "note": "curated fixture span",
        },
    ]
    assert classifications["1@1"]["counts_for_cp"] is False
    assert classifications["1@1"]["span_overrides"] == [
        {
            "word_offset_start": 1000,
            "word_offset_end": 1004,
            "counts_for_cp": False,
            "reason_code": "section_header",
            "note": "generated from chapter section header",
            "excerpt": "Jumpchain abilities this chapter:",
        }
    ]


def test_build_section_classifications_promotes_plausible_section_with_mechanics_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from scripts import build_section_classifications as classifier

    root = tmp_path / "project"
    sections_path = root / "data" / "derived" / "chapter_sections.json"
    rolls_path = root / "data" / "derived" / "rolls.json"
    obtained_path = root / "data" / "derived" / "obtained_perks.json"
    out_path = root / "data" / "manual" / "section_classifications.json"
    sections_doc = {
        "chapters": [
            {
                "chapter_num": "8.1",
                "full_title": "8.1 Interlude Amy",
                "sections": [
                    _section(
                        header=None,
                        word_count=400,
                        sample="Amy waited in the hallway.",
                        fp_count=0,
                        tp_count=5,
                    ),
                    _section(
                        header=None,
                        word_count=1200,
                        sample="Amy spoke with Joe while the Forge stirred.",
                        fp_count=0,
                        tp_count=8,
                    ),
                    _section(
                        header="Jumpchain abilities this chapter:",
                        word_count=100,
                        sample="Footer.",
                    ),
                ],
            }
        ]
    }
    _write_json(sections_path, sections_doc)
    _write_json(rolls_path, {"rolls": [{"kind": "roll", "chapter_num": "8.1"}]})
    _write_json(obtained_path, {"perks": []})

    monkeypatch.setattr(classifier, "ROOT", root)
    monkeypatch.setattr(classifier, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(classifier, "ROLLS_JSON", rolls_path)
    monkeypatch.setattr(classifier, "OBTAINED_JSON", obtained_path)
    monkeypatch.setattr(classifier, "OUT", out_path)

    classifier.main()
    classifications = json.loads(out_path.read_text())["classifications"]

    assert classifications["8.1@0"]["counts_for_cp"] is False
    assert classifications["8.1@1"]["counts_for_cp"] is True
    assert classifications["8.1@1"]["reason"].startswith("mechanics evidence override")
    assert classifications["8.1@2"]["counts_for_cp"] is False

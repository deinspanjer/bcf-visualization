from __future__ import annotations

from pathlib import Path

from scripts._common import write_validated_json


def test_write_validated_json_resolves_internal_schema_refs_locally(tmp_path: Path) -> None:
    payload = {
        "_source": "fixture",
        "_count": 1,
        "chapters": [
            {
                "chapter_num": "1",
                "sort_key": [1, 0],
                "ordinal": 1,
                "title": "Fixture",
                "full_title": "1 Fixture",
                "epub_href": "chap_1.xhtml",
                "total_word_count": 1,
            }
        ],
    }

    out = tmp_path / "chapters.json"
    write_validated_json(out, payload, "chapters")

    assert out.is_file()

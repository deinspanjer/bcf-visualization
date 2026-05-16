"""Scenarios for scripts/seed_chapter_publication_dates.py.

The seed script bootstraps data/manual/chapter_publication_dates.json
(single source of truth for publish + last-edit dates) from the AO3
'Navigate Work' page and the FicHub EPUB. Each scenario uses tiny
purpose-built fixtures so behavior assertions stay decoupled from the
current story state.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _ao3_html(rows: list[tuple[int, str, str, str]]) -> str:
    """Build a minimal AO3 navigate page.

    rows = (display_index, full_title, ao3_chapter_id, YYYY-MM-DD).
    """
    body = "\n".join(
        f'<li><a href="/works/1/chapters/{cid}">{idx}. {full}</a> '
        f'<span class="datetime">({date})</span></li>'
        for idx, full, cid, date in rows
    )
    return f'<html><body><ol class="chapter index group">{body}</ol></body></html>'


def _patch_paths(monkeypatch, project: Path) -> None:
    from scripts import seed_chapter_publication_dates as seed

    monkeypatch.setattr(seed, "ROOT", project)
    monkeypatch.setattr(seed, "AO3_HTML",
                        project / "data" / "raw" / "ao3_index" / "navigate_work.html")
    monkeypatch.setattr(seed, "EPUB",
                        project / "data" / "raw" / "fixture.epub")
    monkeypatch.setattr(seed, "CHAPTERS",
                        project / "data" / "derived" / "chapters.json")
    monkeypatch.setattr(seed, "OUT",
                        project / "data" / "manual" / "chapter_publication_dates.json")


def _stage(project: Path, *, ao3_rows: list[tuple[int, str, str, str]],
           epub_entries: dict[str, str | None],
           chapters: list[dict]) -> None:
    """Write fixture inputs.

    epub_entries maps chap_NN.xhtml href -> 'Last edited: ...' suffix string
    or None to omit the footer.
    """
    raw = project / "data" / "raw"
    ao3_dir = raw / "ao3_index"
    derived = project / "data" / "derived"
    ao3_dir.mkdir(parents=True, exist_ok=True)
    derived.mkdir(parents=True, exist_ok=True)

    (ao3_dir / "navigate_work.html").write_text(_ao3_html(ao3_rows))

    nav_links = "".join(
        f'<a href="{href}">{title}</a>'
        for href, title in [(f"chap_{i+1}.xhtml", c["full_title"])
                            for i, c in enumerate(chapters)]
    )
    with zipfile.ZipFile(raw / "fixture.epub", "w") as zf:
        zf.writestr("EPUB/nav.xhtml", f"<nav>{nav_links}</nav>")
        for href, footer in epub_entries.items():
            body = "<p>body</p>"
            if footer is not None:
                body += f"<p>{footer}</p>"
            zf.writestr(f"EPUB/{href}", body)

    _write_json(derived / "chapters.json", {"chapters": chapters})


def test_seed_writes_ao3_publish_and_epub_last_edited_with_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import seed_chapter_publication_dates as seed

    project = tmp_path / "project"
    _stage(
        project,
        ao3_rows=[
            (1, "1 Intro", "100", "2020-05-01"),
            (2, "2 Next",  "101", "2020-05-02"),
        ],
        epub_entries={
            "chap_1.xhtml": "Last edited: Dec 10, 2020",
            "chap_2.xhtml": None,  # never edited post-publish
        },
        chapters=[
            {"chapter_num": "1", "full_title": "1 Intro", "sort_key": [1, 0],
             "publish_iso": "2020-07-19T21:07:12-0400"},
            {"chapter_num": "2", "full_title": "2 Next",  "sort_key": [2, 0],
             "publish_iso": "2020-07-19T21:09:59-0400"},
        ],
    )
    _patch_paths(monkeypatch, project)

    seed.main()

    out = json.loads(
        (project / "data" / "manual" / "chapter_publication_dates.json").read_text()
    )
    rows = {r["chapter_num"]: r for r in out["chapters"]}

    assert rows["1"]["published_at"] == "2020-05-01"
    assert rows["1"]["published_source"] == "ao3"
    assert rows["1"]["last_edited_at"] == "2020-12-10"
    assert rows["1"]["last_edited_source"] == "epub"

    assert rows["2"]["published_at"] == "2020-05-02"
    assert rows["2"]["published_source"] == "ao3"
    assert rows["2"]["last_edited_at"] is None
    assert rows["2"]["last_edited_source"] is None


def test_seed_falls_back_to_sv_date_when_chapter_missing_from_ao3(
    tmp_path: Path, monkeypatch
) -> None:
    from scripts import seed_chapter_publication_dates as seed

    project = tmp_path / "project"
    _stage(
        project,
        # AO3 carries only chapter 1; chapter 2 is SV-only.
        ao3_rows=[(1, "1 Intro", "100", "2020-05-01")],
        epub_entries={"chap_1.xhtml": None, "chap_2.xhtml": None},
        chapters=[
            {"chapter_num": "1", "full_title": "1 Intro", "sort_key": [1, 0],
             "publish_iso": "2020-07-19T21:07:12-0400"},
            {"chapter_num": "2", "full_title": "2 Next",  "sort_key": [2, 0],
             "publish_iso": "2020-08-15T10:00:00-0400"},
        ],
    )
    _patch_paths(monkeypatch, project)

    seed.main()

    rows = {
        r["chapter_num"]: r for r in json.loads(
            (project / "data" / "manual" / "chapter_publication_dates.json").read_text()
        )["chapters"]
    }
    assert rows["1"]["published_source"] == "ao3"
    assert rows["1"]["published_at"] == "2020-05-01"
    # SV's publish_iso truncated to date for the fallback row.
    assert rows["2"]["published_source"] == "sv"
    assert rows["2"]["published_at"] == "2020-08-15"


def test_seed_output_validates_against_schema(
    tmp_path: Path, monkeypatch
) -> None:
    """The seed writes through write_validated_json; a non-conforming row
    would fail the schema. This test pins the contract by asserting the
    output passes validation for both AO3 and SV-fallback provenance."""
    from scripts import seed_chapter_publication_dates as seed

    project = tmp_path / "project"
    _stage(
        project,
        ao3_rows=[(1, "1 Intro", "100", "2020-05-01")],
        epub_entries={
            "chap_1.xhtml": "Last edited: Dec 10, 2020",
            "chap_2.xhtml": None,
        },
        chapters=[
            {"chapter_num": "1", "full_title": "1 Intro", "sort_key": [1, 0],
             "publish_iso": "2020-07-19T21:07:12-0400"},
            {"chapter_num": "2", "full_title": "2 Next",  "sort_key": [2, 0],
             "publish_iso": "2020-08-15T10:00:00-0400"},
        ],
    )
    _patch_paths(monkeypatch, project)

    seed.main()  # would raise on schema violation

    out = json.loads(
        (project / "data" / "manual" / "chapter_publication_dates.json").read_text()
    )
    assert out["_count"] == 2
    # Provenance covers both expected codes for this fixture.
    sources = {r["published_source"] for r in out["chapters"]}
    assert sources == {"ao3", "sv"}

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest


def _write_fixture_epub(path: Path, chapters: list[tuple[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    nav_links = "\n".join(
        f'<li><a href="chap_{index}.xhtml">{chapter_num} {title}</a></li>'
        for index, (chapter_num, title) in enumerate(chapters, start=1)
    )
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <body>
    <nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">
      <ol>{nav_links}</ol>
    </nav>
  </body>
</html>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("EPUB/nav.xhtml", nav)
        for index, (chapter_num, title) in enumerate(chapters, start=1):
            zf.writestr(
                f"EPUB/chap_{index}.xhtml",
                f"<html><body><h1>{chapter_num} {title}</h1><p>Fixture body.</p></body></html>",
            )
    return path


def test_private_source_epub_is_preferred_and_copied_to_raw(tmp_path: Path) -> None:
    from scripts import hydrate_source_epub

    data_dir = tmp_path / "data"
    private_epub = _write_fixture_epub(
        data_dir / "private-source" / "Brocktons_Celestial_Forge.epub",
        [("1", "Private Start"), ("2.5", "Private Finale")],
    )
    raw_epub = _write_fixture_epub(
        data_dir / "raw" / "Brocktons_Celestial_Forge.epub",
        [("9", "Stale Raw")],
    )
    raw_before = raw_epub.read_bytes()

    metadata = hydrate_source_epub.hydrate_source_epub(data_dir=data_dir)

    assert metadata["source_kind"] == "private-source"
    assert metadata["source_path"] == "data/private-source/Brocktons_Celestial_Forge.epub"
    assert metadata["epub_sha256"] == hashlib.sha256(private_epub.read_bytes()).hexdigest()
    assert metadata["chapter_count"] == 2
    assert metadata["last_chapter_num"] == "2.5"
    assert metadata["last_chapter_title"] == "2.5 Private Finale"
    assert (data_dir / "raw" / "Brocktons_Celestial_Forge.epub").read_bytes() != raw_before
    assert (data_dir / "raw" / "Brocktons_Celestial_Forge.epub").read_bytes() == (
        private_epub.read_bytes()
    )
    assert json.loads(
        (data_dir / "raw" / "Brocktons_Celestial_Forge.source.json").read_text()
    ) == metadata


def test_raw_epub_is_contributor_escape_hatch(tmp_path: Path) -> None:
    from scripts import hydrate_source_epub

    data_dir = tmp_path / "data"
    raw_epub = _write_fixture_epub(
        data_dir / "raw" / "Brocktons_Celestial_Forge.epub",
        [("1", "Raw Start"), ("2", "Raw Finale")],
    )

    metadata = hydrate_source_epub.hydrate_source_epub(data_dir=data_dir)

    assert metadata["source_kind"] == "raw"
    assert metadata["source_path"] == "data/raw/Brocktons_Celestial_Forge.epub"
    assert metadata["private_source_commit"] is None
    assert metadata["epub_sha256"] == hashlib.sha256(raw_epub.read_bytes()).hexdigest()
    assert metadata["chapter_count"] == 2
    assert metadata["last_chapter_num"] == "2"
    assert metadata["last_chapter_title"] == "2 Raw Finale"


def test_missing_source_epub_explains_private_and_byo_options(tmp_path: Path) -> None:
    from scripts import hydrate_source_epub

    with pytest.raises(FileNotFoundError) as excinfo:
        hydrate_source_epub.hydrate_source_epub(data_dir=tmp_path / "data")

    message = str(excinfo.value)
    assert "data/private-source/Brocktons_Celestial_Forge.epub" in message
    assert "data/raw/Brocktons_Celestial_Forge.epub" in message
    assert "provide a compatible EPUB" in message


def test_manual_chapter_references_must_exist_in_source_epub(tmp_path: Path) -> None:
    from scripts import hydrate_source_epub

    data_dir = tmp_path / "data"
    _write_fixture_epub(
        data_dir / "raw" / "Brocktons_Celestial_Forge.epub",
        [("1", "Raw Start"), ("2", "Raw Finale")],
    )
    manual = data_dir / "manual"
    manual.mkdir(parents=True)
    (manual / "section_classifications.json").write_text(
        json.dumps({
            "classifications": {
                "3@0": {
                    "chapter_num": "3",
                    "section_index": 0,
                    "counts_for_cp": True,
                }
            }
        }) + "\n"
    )

    with pytest.raises(ValueError, match="section_classifications.json references missing chapters: 3"):
        hydrate_source_epub.hydrate_source_epub(data_dir=data_dir)


def test_private_source_commit_is_recorded_when_available(tmp_path: Path) -> None:
    from scripts import hydrate_source_epub

    data_dir = tmp_path / "data"
    private_dir = data_dir / "private-source"
    _write_fixture_epub(
        private_dir / "Brocktons_Celestial_Forge.epub",
        [("1", "Private Start")],
    )
    subprocess.run(["git", "init"], cwd=private_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=private_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=private_dir, check=True)
    subprocess.run(["git", "add", "Brocktons_Celestial_Forge.epub"], cwd=private_dir, check=True)
    subprocess.run(["git", "commit", "-m", "source"], cwd=private_dir, check=True, capture_output=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=private_dir, text=True).strip()

    metadata = hydrate_source_epub.hydrate_source_epub(data_dir=data_dir)

    assert metadata["private_source_commit"] == commit

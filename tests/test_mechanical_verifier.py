from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import EPUB, _chapter_word_index, load_chapter_html  # noqa: E402
from scripts.data_paths import DERIVED, MANUAL  # noqa: E402
from scripts.mechanical_verifier import (  # noqa: E402
    build_obtained_perks_index,
    verify_roll,
)
from scripts.perk_name_resolver import build_directory_match_index  # noqa: E402


# ---------------------------------------------------------------------------
# Real-data fixtures shared by the two tracer-style tests (Task 1). These are
# the ONLY tests in this file that touch the real (gitignored, locally
# present) epub or the real corpus — every unit test added by Task 2 uses
# synthetic fixtures instead.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_overrides() -> dict:
    doc = json.loads((MANUAL / "chapter_roll_overrides.json").read_text())
    return doc["chapter_roll_overrides"]


@pytest.fixture(scope="module")
def real_prose_loader():
    chapters = json.loads((DERIVED / "chapters.json").read_text())["chapters"]
    href_by_chapter = {c["chapter_num"]: c["epub_href"] for c in chapters}
    classifications = json.loads(
        (MANUAL / "section_classifications.json").read_text()
    )["classifications"]

    cache: dict[str, tuple[str, list[int]]] = {}

    def _load(chapter_num: str) -> tuple[str, list[int]]:
        if chapter_num not in cache:
            href = href_by_chapter[chapter_num]
            html = load_chapter_html(EPUB, href)
            word_index = _chapter_word_index(html, classifications, chapter_num)
            cache[chapter_num] = (html, word_index)
        return cache[chapter_num]

    return _load


@pytest.fixture(scope="module")
def real_directory_index():
    directory_rows = json.loads((DERIVED / "perk_directory.json").read_text())["perks"]
    aliases = json.loads((MANUAL / "perk_aliases.json").read_text())
    return build_directory_match_index(directory_rows, aliases)


@pytest.fixture(scope="module")
def real_obtained_perks_index():
    obtained_perks_doc = json.loads((DERIVED / "obtained_perks.json").read_text())
    return build_obtained_perks_index(obtained_perks_doc)


def test_tracer_ch67_roll1_personal_reality_multigrab_passes_end_to_end(
    real_overrides, real_prose_loader, real_directory_index, real_obtained_perks_index,
) -> None:
    """The plan's tracer bullet: chapter 67's five-perk Personal Reality
    multi-grab hit — four paid perks resolving via the directory ladder,
    one cost-0 free ride-along ("Neutral Lighting") resolving via
    obtained_perks_index alone. Exercises the tokenizer, both quote tiers,
    the D-04 position check, both perk-resolution branches, and the
    null-tolerant enum check together, end-to-end, against real data.
    """
    roll = real_overrides["67"]["rolls"][1]
    assert roll["perks"] == [
        "The Pond", "The Meaning of Life", "The Pond-Expansion",
        "Neutral Lighting", "Natural Lighting",
    ]
    result = verify_roll(
        "67", 1, roll,
        prose_loader=real_prose_loader,
        directory_index=real_directory_index,
        obtained_perks_index=real_obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "pass"


def test_ch92_roll1_transformers_bundle_free_ride_alongs_resolve(
    real_overrides, real_prose_loader, real_directory_index, real_obtained_perks_index,
) -> None:
    """D-06(c) CORRECTION's canonical example: chapter 92's seven-perk
    Transformers bundle — one paid "Cybertronian Forge" plus six cost-0
    ride-alongs, none of which resolve via directory_index.lookup. This
    is the harder free-path case: every one of the six free names would
    report perk_unresolved under the pre-correction all-through-the-ladder
    design.
    """
    roll = real_overrides["92"]["rolls"][1]
    assert roll["perks"] == [
        "Cybertronian Forge", "Altmode", "Decepticon Terrorize!", "Energon",
        "Energon Battle Pistol", "Energon Melee Weapon",
        "ROBOTS IN DISGUISE! - Medium Chassis",
    ]
    result = verify_roll(
        "92", 1, roll,
        prose_loader=real_prose_loader,
        directory_index=real_directory_index,
        obtained_perks_index=real_obtained_perks_index,
    )
    assert result["issues"] == []
    assert result["status"] == "pass"

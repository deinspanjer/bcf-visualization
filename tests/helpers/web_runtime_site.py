from __future__ import annotations

import contextlib
import http.server
import json
import shutil
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


WEB_FILES = (
    "index.html",
    "app.js",
    "mobile-gestures.js",
    "data-contract.js",
    "viz-model.js",
    "style.css",
    "mobile.css",
)

CONSTELLATION_NAMES = (
    "Toolkits",
    "Knowledge",
    "Vehicles",
    "Time",
    "Crafting",
    "Clothing",
    "Magic",
    "Quality",
    "Size",
    "Resources and Durability",
    "Magitech",
    "Alchemy",
    "Capstone",
    "Personal Reality",
)


@dataclass(frozen=True)
class StagedWebRuntimeSite:
    root: Path
    base_url: str

    def url_for(self, path: str = "/web/") -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"


class _ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _copy_web_files(repo_root: Path, site_root: Path) -> None:
    web_dir = site_root / "web"
    web_dir.mkdir(parents=True, exist_ok=True)
    for filename in WEB_FILES:
        shutil.copy2(repo_root / "web" / filename, web_dir / filename)


def _copy_landing_page(repo_root: Path, site_root: Path) -> None:
    # 04-03-PLAN.md: stage the repo-root landing page (index.html) alongside
    # the already-staged web/ app, so `site.url_for("/")` serves the landing
    # page AND its relative `./web/` link resolves against a real staged app
    # rather than 404ing. Additive only — no existing test targets "/" today.
    shutil.copy2(repo_root / "index.html", site_root / "index.html")


def _manifest(package_id: str) -> dict:
    return {
        "package_id": package_id,
        "contract": "bcf-visualization-data",
        "contract_version": 1,
        "package_date": "20260101",
        "build_number": 1,
        "story_chapter_ordinal": 2,
        "story_chapter_num": "2",
        "story_chapter_title": "2 Synthetic Followup",
        "curation_reviewed_chapter_ordinal": 1,
        "curation_reviewed_chapter_num": "1",
        "curation_reviewed_chapter_title": "1 Synthetic Start",
        "version_label": "BCF data 20260101.1",
        "version_description": "story data through ch 2 / 2; curation data through ch 1 / 1",
        "files": {
            "visualization_facts": {
                "path": "visualization_facts.json",
                "schema_version": 2,
            },
        },
        "entrypoints": {
            "web": {
                "required": ["visualization_facts"],
                "optional": [],
            },
        },
    }


def _roll_hit() -> dict:
    return {
        "predicted_ordinal": 1,
        "predicted_label": "P1",
        "source_ordinal": 1,
        "source_label": "S1",
        "roll_ordinal": 1,
        "roll_label": "R1",
        "chapter_ordinal": 1,
        "chapter_label": "C1",
        "association_source": "auto",
        "outcome": "hit",
        "constellation": "Toolkits",
        "epub_word_offset_predicted": 1500,
        "epub_word_offset_curated": 1500,
        "available_cp": 100,
        "rolled_perk_cost": 100,
        "purchased_perk_cost_total": 100,
        "purchased_perks": [
            {
                "name": "Synthetic Toolkit",
                "cost": 100,
                "constellation": "Toolkits",
                "free": False,
            }
        ],
        "free_perks": [],
    }


def _roll_miss() -> dict:
    return {
        "predicted_ordinal": 2,
        "predicted_label": "P2",
        "source_ordinal": None,
        "source_label": None,
        "roll_ordinal": 2,
        "roll_label": "R2",
        "chapter_ordinal": 1,
        "chapter_label": "C1",
        "association_source": "none",
        "outcome": "miss",
        "constellation": None,
        "epub_word_offset_predicted": 6500,
        "epub_word_offset_curated": 6500,
        "available_cp": 50,
        "rolled_perk_cost": 200,
        "miss_cost_estimate": 200,
        "purchased_perks": [],
        "free_perks": [],
    }


def _chapter(
    chapter_num: str,
    title: str,
    *,
    start_words: int,
    word_count: int,
    cp_words: int,
    rolls: list[dict],
    skipped: list[dict] | None = None,
    visible_toolkits: bool = False,
) -> dict:
    hits = sum(1 for roll in rolls if roll["outcome"] == "hit")
    misses = sum(1 for roll in rolls if roll["outcome"] == "miss")
    return {
        "chapter_num": chapter_num,
        "full_title": title,
        "published_at": "2024-01-01",
        "published_source": "ao3",
        "last_edited_at": "2024-01-02",
        "last_edited_source": "epub",
        "total_word_count": word_count,
        "cumulative_words_through_chapter": start_words + word_count,
        "cp_earning_word_count": word_count,
        "cumulative_cp_earning_words": cp_words + word_count,
        "point_calculation_regime": "synthetic",
        "paid_perks_gained": hits,
        "free_perks_gained": 0,
        "hits_count": hits,
        "misses_count": misses,
        "unknowns_count": 0,
        "sections": [
            {
                "section_index": 1,
                "header": f"{title} section",
                "word_count": word_count,
                "pov_character": "Joe",
                "marker_kind": "pov",
                "classification": "story",
                "classification_confidence": "manual",
                "counts_for_cp": True,
            }
        ],
        "rolls": rolls,
        "skipped_predicted_rolls": skipped or [],
        "constellation_progress": [
            {
                "name": "Toolkits",
                "count": 1 if visible_toolkits else 0,
                "total": 3,
                "discovered": 1 if visible_toolkits else 0,
                "discovered_pct": 33 if visible_toolkits else 0,
                "visible": visible_toolkits,
                "complete": False,
            }
        ],
    }


# MOBP-01 encoding edge (02-01-PLAN.md Task 2): a purchased-perk name with a
# long multibyte string (>= 60 chars, includes an em-dash and accented
# letters) used to prove the top-cluster/focal-label overlap bar holds even
# when the active roll's perk name is unusually long.
LONG_MULTIBYTE_PERK_NAME = "AEtherial Reforged Toolkit — Ómnia Perpetuum Improvementum Ünicode"
assert len(LONG_MULTIBYTE_PERK_NAME) >= 60


# Phase 3 Task 2 (03-01-PLAN.md): a >100-char evidence quote containing
# literal angle-bracket characters, added to exactly ONE dense-rolls roll
# (see _dense_chapter_facts) so the landscape field log's D-27 truncation
# and T-03-01 markup-escaping ("renders as literal characters, never parsed
# HTML") assertions have a real subject. tiny-default/tiny-alt payloads stay
# byte-identical (see the branch note in _visualization_facts below).
LANDSCAPE_EVIDENCE_QUOTE_TEXT = (
    "The forge hummed <awakening> as Joe reached for the battered toolkit, "
    "each rivet catching pale light in a way that made the whole workshop "
    "feel briefly, impossibly alive with promise."
)
assert len(LANDSCAPE_EVIDENCE_QUOTE_TEXT) > 100
assert "<" in LANDSCAPE_EVIDENCE_QUOTE_TEXT and ">" in LANDSCAPE_EVIDENCE_QUOTE_TEXT


def _dense_roll(
    offset: int,
    roll_ordinal: int,
    outcome: str,
    *,
    perk_name: str | None = None,
    evidence_quotes: list[dict] | None = None,
) -> dict:
    common = {
        "predicted_ordinal": roll_ordinal,
        "predicted_label": f"P{roll_ordinal}",
        "roll_ordinal": roll_ordinal,
        "roll_label": f"R{roll_ordinal}",
        "chapter_ordinal": 1,
        "chapter_label": "C1",
        "epub_word_offset_predicted": offset,
        "epub_word_offset_curated": offset,
    }
    if outcome == "hit":
        return {
            **common,
            "source_ordinal": roll_ordinal,
            "source_label": f"S{roll_ordinal}",
            "association_source": "auto",
            "outcome": "hit",
            "constellation": "Toolkits",
            "available_cp": 100,
            "rolled_perk_cost": 100,
            "purchased_perk_cost_total": 100,
            "purchased_perks": [
                {
                    "name": perk_name or f"Dense Perk {roll_ordinal}",
                    "cost": 100,
                    "constellation": "Toolkits",
                    "free": False,
                }
            ],
            "free_perks": [],
            "evidence_quotes": evidence_quotes or [],
        }
    return {
        **common,
        "source_ordinal": None,
        "source_label": None,
        "association_source": "none",
        "outcome": "miss",
        "constellation": None,
        "available_cp": 50,
        "rolled_perk_cost": 200,
        "miss_cost_estimate": 200,
        "purchased_perks": [],
        "free_perks": [],
    }


def _dense_chapter_facts() -> dict:
    # 8 rolls clustered within 70 words of each other (chapter 2) — merges
    # into ONE cluster bin at both 390px and 320px rail widths, 1x zoom
    # (MOBP-04, 02-03-PLAN.md) — plus 4 rolls spread across chapter 3, each
    # > 5% of total words (500 of 10,000) apart from its neighbors. Mixed
    # hit/miss throughout; the first clustered hit carries the long
    # multibyte perk name.
    #
    # binRolls' split test compares each roll's word_position against the
    # CURRENTLY OPEN bin's firstWord (verbatim port of the prototype's
    # `r.wordPosition - cur.firstWord > minWords`), not the pairwise gap to
    # its immediate neighbor — so the bin only stays open while the roll's
    # distance from the bin's FIRST member stays under minWords. At a real
    # ~300-370px rail width and 10,000 total words, minWords is
    # (5/pxWidth)*10000 ~= 135-167 words; a 70-word total cluster span (10
    # words/roll * 7 gaps) merges with comfortable margin at every rail
    # width this phase's viewports use, while the previous 280-word-span
    # version of this fixture (40 words/roll) exceeded minWords partway
    # through and split into two 4-roll bins instead of the intended one.
    cluster_offsets = [3100, 3110, 3120, 3130, 3140, 3150, 3160, 3170]
    cluster_outcomes = ["hit", "miss", "hit", "miss", "hit", "miss", "hit", "miss"]
    cluster_rolls = [
        _dense_roll(
            offset,
            index + 1,
            outcome,
            perk_name=LONG_MULTIBYTE_PERK_NAME if index == 0 else None,
        )
        for index, (offset, outcome) in enumerate(zip(cluster_offsets, cluster_outcomes))
    ]

    spread_offsets = [7200, 8200, 9200, 9800]
    spread_outcomes = ["hit", "miss", "hit", "miss"]
    spread_rolls = [
        _dense_roll(
            offset,
            len(cluster_rolls) + index + 1,
            outcome,
            # The first spread roll (chapter 3, word 7200) carries the sole
            # landscape evidence-quote fixture — kept separate from the
            # cluster's long-multibyte-perk-name roll above so the two edge
            # cases stay independently seekable/bookmarkable in tests.
            evidence_quotes=[{
                "text": LANDSCAPE_EVIDENCE_QUOTE_TEXT,
                "mention_chapter_num": "3",
                "mention_word_position": offset,
            }] if index == 0 else None,
        )
        for index, (offset, outcome) in enumerate(zip(spread_offsets, spread_outcomes))
    ]

    return {
        "schema_version": 1,
        "shadow_periods": [],
        "chapters": [
            _chapter(
                "1",
                "1 Dense Chapter One",
                start_words=0,
                word_count=3000,
                cp_words=0,
                rolls=[],
            ),
            _chapter(
                "2",
                "2 Dense Chapter Two",
                start_words=3000,
                word_count=4000,
                cp_words=3000,
                rolls=cluster_rolls,
                visible_toolkits=True,
            ),
            _chapter(
                "3",
                "3 Dense Chapter Three",
                start_words=7000,
                word_count=3000,
                cp_words=7000,
                rolls=spread_rolls,
                visible_toolkits=True,
            ),
        ],
    }


# MOBP-04/UI-SPEC "empty-zero-rolls" fixture (02-03-PLAN.md Task 1): chapters
# (and therefore chapter ticks + POV bands) exist, but NOT ONE roll exists
# anywhere in the story — the only way to exercise "the rail still renders
# ticks/bands/playhead with zero bins and zero active diamond, and does not
# throw". tiny-default carries two real rolls elsewhere in the story (one in
# chapter 2, one in chapter 3), so it cannot stand in for a genuinely
# zero-roll story; this dedicated fixture is required.
def _no_rolls_chapter_facts() -> dict:
    return {
        "schema_version": 1,
        "shadow_periods": [],
        "chapters": [
            _chapter(
                "1",
                "1 No-Rolls Chapter One",
                start_words=0,
                word_count=3000,
                cp_words=0,
                rolls=[],
            ),
            _chapter(
                "2",
                "2 No-Rolls Chapter Two",
                start_words=3000,
                word_count=4000,
                cp_words=3000,
                rolls=[],
                visible_toolkits=False,
            ),
            _chapter(
                "3",
                "3 No-Rolls Chapter Three",
                start_words=7000,
                word_count=3000,
                cp_words=7000,
                rolls=[],
                visible_toolkits=False,
            ),
        ],
    }


def _chapter_facts() -> dict:
    return {
        "schema_version": 1,
        "shadow_periods": [],
        "chapters": [
            _chapter(
                "1",
                "1 Synthetic Chapter One",
                start_words=0,
                word_count=3000,
                cp_words=0,
                rolls=[],
            ),
            _chapter(
                "2",
                "2 Synthetic Chapter Two",
                start_words=3000,
                word_count=4000,
                cp_words=3000,
                rolls=[_roll_hit()],
                skipped=[
                    {
                        "predicted_ordinal": 3,
                        "predicted_label": "P3",
                        "source_ordinal": None,
                        "source_label": None,
                        "roll_ordinal": None,
                        "roll_label": None,
                        "skipped_ordinal": 1,
                        "skipped_label": "X1",
                        "slot_index": 1,
                        "mechanical_chapter_num": "2",
                        "display_chapter_num": "2",
                        "predicted_word_position_epub": 5000,
                        "display_word_position_epub": 5000,
                    }
                ],
                visible_toolkits=True,
            ),
            _chapter(
                "3",
                "3 Synthetic Chapter Three",
                start_words=7000,
                word_count=3000,
                cp_words=7000,
                rolls=[_roll_miss()],
                visible_toolkits=True,
            ),
        ],
    }


def _wireframes() -> dict:
    clusters = []
    for index, name in enumerate(CONSTELLATION_NAMES):
        x = 0.2 + (index % 4) * 0.18
        y = 0.2 + (index // 4) * 0.18
        clusters.append({
            "name": name,
            "slug": f"{index + 1:02d}-{name.lower().replace(' ', '-')}",
            "slot_position": index + 1,
            "shape_concept": f"Synthetic {name} outline",
            "vertex_source": "jumps",
            "revealed_at_chapter": "1",
            "completed_at_chapter": None,
            "entered_pool_at_chapter": "1",
            "marker_positions": [[x, y]],
            "silhouette": [],
        })
    return {
        "schema_version": 2,
        "_source": "tests/helpers/web_runtime_site.py synthetic fixture",
        "_count": len(clusters),
        "_jumps_count": 1,
        "_note": "Tiny wireframe fixture for web integration tests.",
        "cluster_constellations": clusters,
        "jump_constellations": [
            {
                "constellation": "Toolkits",
                "jump": "Fixture Jump",
                "shape_concept": "Synthetic toolkit triangle",
                "stars": [
                    {
                        "id": "toolkits-fixture-synthetic-toolkit",
                        "perk_name": "Synthetic Toolkit",
                        "cost": 100,
                        "size": 0.35,
                        "x": 0.25,
                        "y": 0.25,
                        "status": "Obtained",
                        "acquired_chapter_num": "2",
                        "acquired_epub_sequence": 1,
                        "instances_count": 1,
                    }
                ],
                "edges": [],
            }
        ],
    }


def _visualization_facts(package_id: str) -> dict:
    # Branch on package id rather than mutating the shared builders in
    # place — tiny-default/tiny-alt payloads must stay byte-identical.
    if package_id == "chapterless":
        # UI-SPEC "unknown chapter" fallback fixture (02-01-PLAN.md Task 2):
        # zero chapters means chapterAtWord() returns undefined, which is the
        # only reachable path to the dock title's "—" fallback — every real
        # chapter always resolves a non-empty title (normChapterTitle falls
        # back to "Chapter N"), so this is the sole way to exercise it.
        chapter_facts: dict = {"chapters": []}
    elif package_id == "dense-rolls":
        chapter_facts = _dense_chapter_facts()
    elif package_id == "no-rolls":
        chapter_facts = _no_rolls_chapter_facts()
    else:
        chapter_facts = _chapter_facts()
    wireframes = _wireframes()
    predicted_rolls = [] if package_id in ("chapterless", "no-rolls") else [
        # Use renamed field `regime`, not the upstream `cp_rule_regime`.
        {"roll_number": 1, "cp_offset": 2000, "epub_offset": 2253,
         "chapter_num": "1", "slot_index": 1, "regime": 1,
         "roll_trigger_cp_threshold": 100},
    ]
    return {
        "schema_version": 2,
        "_source": "tests/helpers/web_runtime_site.py",
        "_method": "synthetic test fixture",
        "shadow_periods": chapter_facts.get("shadow_periods", []),
        "in_world_timeline": chapter_facts.get("in_world_timeline", {
            "_sources_used": [], "_count": 0,
            "_first_in_world_date": None, "_last_in_world_date": None,
            "entries": [],
        }),
        "chapters": chapter_facts.get("chapters", []),
        "constellation_wireframes": {
            "cluster_constellations": wireframes.get("cluster_constellations", []),
            "jump_constellations": wireframes.get("jump_constellations", []),
        },
        "predicted_rolls": predicted_rolls,
        "predicted_rolls_meta": {
            "_count": len(predicted_rolls),
            "_total_cp_words": 2000 if predicted_rolls else 0,
            "_total_epub_words": 2253,
            "_regime_summary": {"1": "synthetic", "2": "synthetic", "3": "synthetic"},
        },
    }


def _stage_package(
    site_root: Path,
    package_id: str,
    *,
    derived: bool = False,
) -> None:
    package_dir = site_root / ("data/derived" if derived else f"data/packages/{package_id}")
    _write_json(package_dir / "data_package.json", _manifest(package_id))
    _write_json(package_dir / "visualization_facts.json", _visualization_facts(package_id))


@contextlib.contextmanager
def _serve(site_root: Path) -> Iterator[str]:
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *args,
        directory=str(site_root),
        **kwargs,
    )
    with _ThreadingTCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


@contextlib.contextmanager
def staged_web_runtime_site(
    tmp_path: Path,
) -> Iterator[StagedWebRuntimeSite]:
    repo_root = Path(__file__).resolve().parents[2]
    site_root = tmp_path / "runtime-site"
    _copy_web_files(repo_root, site_root)
    _copy_landing_page(repo_root, site_root)
    _write_json(
        site_root / "data/packages.json",
        {
            "schema_version": 1,
            "default_package_id": "tiny-default",
            "packages": [
                {
                    "package_id": "tiny-default",
                    "path": "data/packages/tiny-default",
                    "package_date": "20260101",
                    "build_number": 1,
                    "story_chapter_ordinal": 2,
                    "story_chapter_num": "2",
                    "curation_reviewed_chapter_ordinal": 1,
                    "curation_reviewed_chapter_num": "1",
                    "version_label": "BCF data 20260101.1",
                    "version_description": "story data through ch 2 / 2; curation data through ch 1 / 1",
                    "smoke_status": "passed",
                },
                {
                    "package_id": "tiny-alt",
                    "path": "data/packages/tiny-alt",
                    "package_date": "20260101",
                    "build_number": 2,
                    "story_chapter_ordinal": 2,
                    "story_chapter_num": "2",
                    "curation_reviewed_chapter_ordinal": 1,
                    "curation_reviewed_chapter_num": "1",
                    "version_label": "BCF data 20260101.2",
                    "version_description": "story data through ch 2 / 2; curation data through ch 1 / 1",
                    "smoke_status": "passed",
                },
                {
                    # MOBP-01/MOBP-04 fixture (02-01-PLAN.md Task 2): denser
                    # roll distribution + a long multibyte perk name, used by
                    # the portrait overlap/binning tests.
                    "package_id": "dense-rolls",
                    "path": "data/packages/dense-rolls",
                    "package_date": "20260101",
                    "build_number": 1,
                    "story_chapter_ordinal": 3,
                    "story_chapter_num": "3",
                    "curation_reviewed_chapter_ordinal": 1,
                    "curation_reviewed_chapter_num": "1",
                    "version_label": "BCF data 20260101.dense",
                    "version_description": "synthetic dense-roll fixture for portrait layout tests",
                    "smoke_status": "passed",
                },
                {
                    # UI-SPEC "unknown chapter" fallback fixture (02-01-PLAN.md
                    # Task 2): zero chapters, used only by the portrait
                    # empty/partial-state test.
                    "package_id": "chapterless",
                    "path": "data/packages/chapterless",
                    "package_date": "20260101",
                    "build_number": 1,
                    "story_chapter_ordinal": 0,
                    "story_chapter_num": "0",
                    "curation_reviewed_chapter_ordinal": 0,
                    "curation_reviewed_chapter_num": "0",
                    "version_label": "BCF data 20260101.chapterless",
                    "version_description": "synthetic zero-chapter fixture for portrait fallback tests",
                    "smoke_status": "passed",
                },
                {
                    # UI-SPEC "empty-zero-rolls" fixture (02-03-PLAN.md Task 1):
                    # real chapters (ticks + POV bands render) but zero rolls
                    # anywhere in the story — used only by the cluster-binning
                    # empty-data test.
                    "package_id": "no-rolls",
                    "path": "data/packages/no-rolls",
                    "package_date": "20260101",
                    "build_number": 1,
                    "story_chapter_ordinal": 3,
                    "story_chapter_num": "3",
                    "curation_reviewed_chapter_ordinal": 0,
                    "curation_reviewed_chapter_num": "0",
                    "version_label": "BCF data 20260101.no-rolls",
                    "version_description": "synthetic zero-roll fixture for portrait rail binning tests",
                    "smoke_status": "passed",
                },
            ],
        },
    )
    _stage_package(site_root, "tiny-default")
    _stage_package(site_root, "tiny-alt")
    _stage_package(site_root, "dense-rolls")
    _stage_package(site_root, "chapterless")
    _stage_package(site_root, "no-rolls")
    _stage_package(site_root, "synthetic-derived", derived=True)

    with _serve(site_root) as base_url:
        yield StagedWebRuntimeSite(root=site_root, base_url=base_url)

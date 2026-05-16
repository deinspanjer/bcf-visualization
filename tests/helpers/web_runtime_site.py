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
    "data-contract.js",
    "viz-model.js",
    "style.css",
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


def _manifest(package_id: str, *, include_wireframes: bool = False) -> dict:
    files = {
        "chapter_facts": {
            "path": "chapter_facts.json",
            "schema_version": 1,
        },
    }
    if include_wireframes:
        files["constellation_wireframes"] = {
            "path": "constellation_wireframes.json",
            "schema_version": 1,
        }
    return {
        "package_id": package_id,
        "contract": "bcf-visualization-data",
        "contract_version": 1,
        "version_label": f"Synthetic {package_id}",
        "files": files,
        "entrypoints": {
            "web": {
                "required": ["chapter_facts"],
                "optional": ["constellation_wireframes"],
            },
        },
    }


def _roll_hit() -> dict:
    return {
        "roll_number": 1,
        "global_roll_number": 1,
        "outcome": "hit",
        "constellation": "Toolkits",
        "predicted_word_position_epub": 1500,
        "display_word_position_epub": 1500,
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
        "roll_number": 2,
        "global_roll_number": 2,
        "outcome": "miss",
        "constellation": None,
        "predicted_word_position_epub": 6500,
        "display_word_position_epub": 6500,
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
        "published_at": "2024-01-01T00:00:00+00:00",
        "last_edited_at": "2024-01-02T00:00:00+00:00",
        "last_edited_known": True,
        "post_url": f"https://example.test/chapters/{chapter_num}",
        "likes": 10,
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
                        "roll_number": 3,
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
        jump = "Fixture Jump" if name == "Toolkits" else f"{name} Fixture"
        clusters.append({
            "name": name,
            "shape_concept": f"Synthetic {name} outline",
            "cluster_vertices": [
                {
                    "jump": jump,
                    "x": 0.2 + (index % 4) * 0.18,
                    "y": 0.2 + (index // 4) * 0.18,
                }
            ],
        })
    return {
        "schema_version": 1,
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


def _stage_package(
    site_root: Path,
    package_id: str,
    *,
    derived: bool = False,
    include_wireframes: bool = False,
) -> None:
    package_dir = site_root / ("data/derived" if derived else f"data/packages/{package_id}")
    _write_json(
        package_dir / "data_package.json",
        _manifest(package_id, include_wireframes=include_wireframes),
    )
    _write_json(package_dir / "chapter_facts.json", _chapter_facts())
    if include_wireframes:
        _write_json(package_dir / "constellation_wireframes.json", _wireframes())


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
    *,
    include_wireframes: bool = False,
) -> Iterator[StagedWebRuntimeSite]:
    repo_root = Path(__file__).resolve().parents[2]
    site_root = tmp_path / "runtime-site"
    _copy_web_files(repo_root, site_root)
    _write_json(
        site_root / "data/packages.json",
        {
            "schema_version": 1,
            "default_package_id": "tiny-default",
            "packages": [
                {
                    "package_id": "tiny-default",
                    "path": "data/packages/tiny-default",
                    "version_label": "Synthetic Default",
                    "smoke_status": "passed",
                },
                {
                    "package_id": "tiny-alt",
                    "path": "data/packages/tiny-alt",
                    "version_label": "Synthetic Alternate",
                    "smoke_status": "passed",
                },
            ],
        },
    )
    _stage_package(site_root, "tiny-default", include_wireframes=include_wireframes)
    _stage_package(site_root, "tiny-alt", include_wireframes=include_wireframes)
    _stage_package(
        site_root,
        "synthetic-derived",
        derived=True,
        include_wireframes=include_wireframes,
    )

    with _serve(site_root) as base_url:
        yield StagedWebRuntimeSite(root=site_root, base_url=base_url)

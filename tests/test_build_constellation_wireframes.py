"""Round-trip + invariant tests for scripts/build_constellation_wireframes.

These tests run against the real `data/derived/constellation_wireframes.json`
produced by the build script. They guard the Phase 5 contract:

  - Every cluster carries `marker_positions` (len >= 1) and `silhouette`
    (a list; may be empty).
  - Every constellation present in `perk_directory.json` (excluding Felyne
    Perks) has a slot in `cluster_constellations[]`.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIREFRAMES = ROOT / "data" / "derived" / "constellation_wireframes.json"
DIRECTORY = ROOT / "data" / "derived" / "perk_directory.json"


def _load_wireframes() -> dict:
    assert WIREFRAMES.exists(), (
        f"Run scripts/build_constellation_wireframes.py first; missing {WIREFRAMES}"
    )
    return json.loads(WIREFRAMES.read_text())


def test_schema_version_is_2() -> None:
    doc = _load_wireframes()
    assert doc["schema_version"] == 2


def test_each_cluster_has_marker_positions_and_silhouette() -> None:
    doc = _load_wireframes()
    clusters = doc["cluster_constellations"]
    assert len(clusters) == 14
    for cluster in clusters:
        markers = cluster["marker_positions"]
        silhouette = cluster["silhouette"]
        name = cluster["name"]

        assert isinstance(markers, list), f"{name}: marker_positions not a list"
        assert len(markers) >= 1, f"{name}: marker_positions is empty"
        for pt in markers:
            assert isinstance(pt, list) and len(pt) == 2, (
                f"{name}: marker point is not a 2-array: {pt!r}"
            )

        assert isinstance(silhouette, list), f"{name}: silhouette not a list"
        for polyline in silhouette:
            assert isinstance(polyline, list) and len(polyline) >= 2, (
                f"{name}: silhouette polyline has fewer than 2 points: {polyline!r}"
            )
            for pt in polyline:
                assert isinstance(pt, list) and len(pt) == 2, (
                    f"{name}: silhouette point is not a 2-array: {pt!r}"
                )


def test_each_cluster_carries_lifecycle_and_identity_fields() -> None:
    doc = _load_wireframes()
    for cluster in doc["cluster_constellations"]:
        assert isinstance(cluster["slug"], str) and cluster["slug"]
        assert 1 <= cluster["slot_position"] <= 14
        assert cluster["vertex_source"] in ("jumps", "perks")
        # Lifecycle fields are nullable strings; ensure key presence.
        for key in (
            "revealed_at_chapter",
            "completed_at_chapter",
            "entered_pool_at_chapter",
        ):
            value = cluster[key]
            assert value is None or isinstance(value, str), (
                f"{cluster['name']}: {key} is not a string|null: {value!r}"
            )


def test_every_directory_constellation_has_a_wireframe_slot() -> None:
    directory = json.loads(DIRECTORY.read_text())["perks"]
    expected = {
        p["constellation"]
        for p in directory
        if p.get("constellation") and p["constellation"] != "Felyne Perks"
    }
    actual = {cluster["name"] for cluster in _load_wireframes()["cluster_constellations"]}
    missing = expected - actual
    assert not missing, (
        f"perk_directory constellations missing from wireframes: {sorted(missing)}"
    )
    extra = actual - expected
    assert not extra, (
        f"wireframes contain constellations not in perk_directory: {sorted(extra)}"
    )


def test_cluster_vertices_field_is_gone() -> None:
    doc = _load_wireframes()
    for cluster in doc["cluster_constellations"]:
        assert "cluster_vertices" not in cluster, (
            f"{cluster['name']}: stale cluster_vertices field still present"
        )

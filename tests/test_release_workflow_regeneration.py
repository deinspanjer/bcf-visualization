from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text()


def test_release_regeneration_uses_constellation_asset_pipeline() -> None:
    """Release workflows must rebuild constellation-derived data before packaging.

    The visualization bundle schema includes constellation lifecycle and SVG-derived
    wireframes. A clean runner may hydrate older dev data before regenerating story
    facts, so release workflows need the canonical constellation rebuild step after
    chapter facts are regenerated instead of calling the visualization bundler
    directly against whatever wireframe JSON happened to be hydrated.
    """
    for workflow in ("auto-data-release.yml", "data-release.yml"):
        text = _workflow_text(workflow)
        chapter_facts = text.index("python3 scripts/build_chapter_facts.py")
        constellation_assets = text.index("scripts/rebuild_constellation_assets.sh")
        assert chapter_facts < constellation_assets, workflow
        assert "python3 scripts/build_visualization_facts.py" not in text, workflow

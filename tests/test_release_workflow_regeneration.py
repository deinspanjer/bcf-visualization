from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text()


def test_release_regeneration_uses_dependency_graph_runner() -> None:
    """Release workflows must delegate data ordering to the pipeline graph."""
    for workflow in ("release.yml", "data-release.yml"):
        text = _workflow_text(workflow)
        assert "python3 scripts/pipeline.py" in text, workflow
        assert "python3 scripts/derive_roll_facts.py" not in text, workflow
        assert "scripts/rebuild_constellation_assets.sh" not in text, workflow


def test_push_release_workflow_uses_visualization_facts_as_hydration_sentinel() -> None:
    text = _workflow_text("release.yml")

    assert "[ ! -f data/derived/visualization_facts.json ]" in text
    assert "[ ! -f data/derived/chapter_facts.json ]" not in text


def test_release_classification_uses_full_push_range_and_publishable_paths() -> None:
    text = _workflow_text("release.yml")

    assert "fetch-depth: 0" in text
    assert 'git diff --name-only "$BEFORE_SHA" "$GITHUB_SHA"' in text
    for pattern in (
        "data/manual/*",
        "data/raw/*",
        "data/labeled/*",
        "data/derived/_schemas/*",
        "data/constellations/*",
        "scripts/*.py",
        ".github/workflows/data-release.yml",
        ".github/workflows/deploy-pages.yml",
        "web/*",
        "figures/*",
        ".nojekyll",
        "index.html",
    ):
        assert pattern in text

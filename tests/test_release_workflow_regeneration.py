from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _workflow_text(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text()


def _classify_changed_paths_script() -> str:
    lines = _workflow_text("release.yml").splitlines()
    in_classify_step = False
    in_run_block = False
    block: list[str] = []
    for line in lines:
        if line.startswith("      - name: "):
            in_classify_step = line.strip() == "- name: Classify changed paths"
            if in_run_block:
                break
        elif in_classify_step and line.strip() == "run: |":
            in_run_block = True
            continue
        if in_run_block:
            block.append(line)
    return textwrap.dedent("\n".join(block))


def _commit_path(repo: Path, path: str, contents: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents)
    subprocess.run(["git", "add", path], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", f"change {path}"], cwd=repo, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _run_release_classifier(tmp_path: Path, changed_path: str) -> dict[str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    before = _commit_path(repo, "README.md", "baseline\n")
    head = _commit_path(repo, changed_path, "changed\n")
    output = repo / "github-output.txt"
    env = {
        **os.environ,
        "GITHUB_EVENT_NAME": "push",
        "GITHUB_SHA": head,
        "GITHUB_OUTPUT": str(output),
        "FORCE_DATA_REBUILD": "false",
        "DATA_BUNDLE_TAG": "",
        "BEFORE_SHA": before,
    }
    subprocess.run(
        ["bash", "-c", _classify_changed_paths_script()],
        cwd=repo,
        check=True,
        env=env,
    )
    return dict(line.split("=", 1) for line in output.read_text().splitlines())


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
        "scripts/smoke_pages_site.py",
        "scripts/scaffold_constellation_pages.py",
        ".github/workflows/data-release.yml",
        ".github/workflows/deploy-pages.yml",
        "web/*",
        "figures/*",
        ".nojekyll",
        "index.html",
    ):
        assert pattern in text


def test_release_classifier_treats_smoke_script_as_web_only(tmp_path: Path) -> None:
    outputs = _run_release_classifier(tmp_path, "scripts/smoke_pages_site.py")

    assert outputs == {
        "data_changed": "false",
        "web_changed": "true",
        "should_run": "true",
    }


def test_release_classifier_treats_pipeline_scripts_as_data_changes(tmp_path: Path) -> None:
    outputs = _run_release_classifier(tmp_path, "scripts/derive_roll_facts.py")

    assert outputs["data_changed"] == "true"
    assert outputs["should_run"] == "true"

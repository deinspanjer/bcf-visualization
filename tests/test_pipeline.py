from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts import pipeline


ROOT = Path(__file__).resolve().parent.parent
DATA_STEP_NAMES = [
    "parse_chapters",
    "extract_chapter_sections",
    "predict_rolls",
    "find_text_backed_rolls",
    "derive_roll_outcomes",
    "derive_timeline",
    "build_perk_directory",
    "derive_outstanding_perks",
    "derive_roll_facts",
    "build_chapter_facts",
    "derive_constellation_lifecycle",
    "build_constellation_wireframes",
    "build_visualization_facts",
]


def test_target_data_resolves_expected_steps_in_dependency_order() -> None:
    plan = pipeline.plan_execution(
        pipeline.build_steps(ROOT),
        target="data",
        force=True,
    )
    names = [step.name for step in plan]

    assert set(names) == set(DATA_STEP_NAMES)
    assert len(names) == len(DATA_STEP_NAMES)
    for producer, consumer in [
        ("parse_chapters", "extract_chapter_sections"),
        ("extract_chapter_sections", "predict_rolls"),
        ("predict_rolls", "find_text_backed_rolls"),
        ("find_text_backed_rolls", "derive_roll_facts"),
        ("build_perk_directory", "derive_outstanding_perks"),
        ("derive_roll_facts", "build_chapter_facts"),
        ("build_chapter_facts", "build_visualization_facts"),
        ("build_constellation_wireframes", "build_visualization_facts"),
    ]:
        assert names.index(producer) < names.index(consumer)


def test_dry_run_on_real_derived_tree_lists_data_steps(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = pipeline.main(["--target", "data", "--dry-run", "--force"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "DRY-RUN data: 13 step(s)" in out
    assert "find_text_backed_rolls" in out
    assert out.index("find_text_backed_rolls") < out.index("derive_roll_facts")


def test_missing_output_rebuilds_only_consumers_in_topological_order(tmp_path: Path) -> None:
    root = tmp_path
    for path in pipeline.all_declared_paths(pipeline.build_steps(root)):
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n")

    now = 1_800_000_000
    for path in pipeline.all_declared_paths(pipeline.build_steps(root)):
        if path.exists():
            os.utime(path, (now, now))

    missing = root / "data" / "derived" / "roll_text_evidence.json"
    missing.unlink()

    plan = pipeline.plan_execution(
        pipeline.build_steps(root),
        target="data",
        hash_cache_path=root / "data" / "derived" / ".pipeline_hashes.json",
    )

    assert [step.name for step in plan] == [
        "find_text_backed_rolls",
        "derive_roll_facts",
        "build_chapter_facts",
        "build_visualization_facts",
    ]


def test_deploy_target_stages_site_before_browser_smoke() -> None:
    plan = pipeline.plan_execution(
        pipeline.build_steps(ROOT),
        target="deploy",
        force=True,
    )
    names = [step.name for step in plan]

    assert "stage_pages_site" in names
    assert "smoke_pages_site" in names
    assert names.index("package_data_release") < names.index("stage_pages_site")
    assert names.index("stage_pages_site") < names.index("smoke_pages_site")

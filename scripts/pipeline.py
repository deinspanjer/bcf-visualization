"""Dependency-graph runner for the BCF derived-data pipeline.

The graph is declared in terms of file contracts. Step ordering is inferred
from matching a step's inputs to another step's outputs, then executed through
``graphlib.TopologicalSorter``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from graphlib import TopologicalSorter
from pathlib import Path

try:
    from data_paths import ROOT
except ModuleNotFoundError:  # package import path used by tests
    from scripts.data_paths import ROOT


Fn = Callable[[], None]


@dataclass(frozen=True)
class Step:
    name: str
    inputs: tuple[Path, ...]
    outputs: tuple[Path, ...]
    fn: Fn | None = None
    cmd: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if (self.fn is None) == (self.cmd is None):
            raise ValueError(f"{self.name}: declare exactly one of fn or cmd")


def _p(root: Path, *parts: str) -> Path:
    return root.joinpath(*parts)


def _py(root: Path, script: str) -> tuple[str, str]:
    return (sys.executable, str(_p(root, "scripts", script)))


def _runtime_manifest_package_id(tar_path: Path) -> str:
    with tarfile.open(tar_path, "r:gz") as tf:
        member = tf.extractfile("data_package.json")
        if member is None:
            raise ValueError(f"{tar_path} has no data_package.json")
        manifest = json.load(member)
    package_id = manifest.get("package_id")
    if not isinstance(package_id, str) or not package_id:
        raise ValueError(f"{tar_path} has no package_id")
    return package_id


def _extract_optional_scaffold_inputs(runtime_tar: Path, derived: Path) -> None:
    optional = {
        "perk_directory.json",
        "constellation_lifecycle.json",
        "constellation_wireframes.json",
    }
    derived.mkdir(parents=True, exist_ok=True)
    with tarfile.open(runtime_tar, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name not in optional or not member.isfile():
                continue
            target = derived / member.name
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            target.write_bytes(extracted.read())


def _stage_pages_site(root: Path) -> None:
    try:
        from data_release import prepare_pages
    except ModuleNotFoundError:
        from scripts.data_release import prepare_pages

    site = root / "_site"
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    for file_name in (".nojekyll", "index.html"):
        src = root / file_name
        if src.exists():
            shutil.copy2(src, site / file_name)
    for dir_name in ("figures", "web"):
        src = root / dir_name
        if src.exists():
            shutil.copytree(src, site / dir_name)

    runtime_tars = sorted((root / ".data-release").glob("bcf-visualization-runtime-*.tar.gz"))
    if not runtime_tars:
        raise FileNotFoundError("no runtime tarballs found in .data-release")
    primary_runtime = runtime_tars[-1]
    _extract_optional_scaffold_inputs(primary_runtime, root / "data" / "derived")
    optional_ready = all(
        (root / "data" / "derived" / name).is_file()
        for name in (
            "perk_directory.json",
            "constellation_lifecycle.json",
            "constellation_wireframes.json",
        )
    )
    if optional_ready:
        subprocess.run(
            [sys.executable, str(root / "scripts" / "scaffold_constellation_pages.py")],
            cwd=root,
            check=True,
        )
        shutil.copytree(root / "web", site / "web", dirs_exist_ok=True)

    package_id = _runtime_manifest_package_id(primary_runtime)
    prepare_pages(
        runtime_tars=runtime_tars,
        site_dir=site,
        default_package_id=package_id,
        smoke_status_by_package_id={package_id: "passed"},
        skip_incompatible_runtime=True,
    )


def _smoke_pages_site(root: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "smoke_pages_site.py"),
            "--site-dir",
            str(root / "_site"),
            "--browser",
        ],
        cwd=root,
        check=True,
    )
    (root / "_site" / ".pipeline-smoke-ok").write_text("ok\n")


def build_steps(root: Path = ROOT) -> list[Step]:
    root = root.resolve()
    derived = _p(root, "data", "derived")
    manual = _p(root, "data", "manual")
    raw = _p(root, "data", "raw")

    epub = raw / "Brocktons_Celestial_Forge.epub"
    section_classifications = manual / "section_classifications.json"
    chapter_roll_overrides = manual / "chapter_roll_overrides.json"
    script_inputs = tuple(sorted((root / "scripts").glob("*.py")))

    def inputs(*paths: Path) -> tuple[Path, ...]:
        return (*paths, *script_inputs)

    return [
        Step(
            name="parse_chapters",
            inputs=inputs(
                epub,
                manual / "chapter_publication_dates.json",
            ),
            outputs=(derived / "chapters.json",),
            cmd=_py(root, "parse_chapters.py"),
        ),
        Step(
            name="extract_chapter_sections",
            inputs=inputs(
                epub,
                derived / "chapters.json",
            ),
            outputs=(
                derived / "chapter_sections.json",
                derived / "extracted_perks.json",
            ),
            cmd=_py(root, "extract_chapter_sections.py"),
        ),
        Step(
            name="predict_rolls",
            inputs=inputs(
                derived / "chapters.json",
                derived / "obtained_perks.json",
                derived / "chapter_sections.json",
                section_classifications,
                manual / "multi_grab_overrides.json",
            ),
            outputs=(
                derived / "predicted_rolls.json",
                derived / "chapter_alignment_fingerprints.json",
            ),
            cmd=_py(root, "predict_rolls.py"),
        ),
        Step(
            name="find_text_backed_rolls",
            inputs=inputs(
                epub,
                derived / "predicted_rolls.json",
                derived / "chapters.json",
                derived / "chapter_sections.json",
                section_classifications,
                derived / "roll_locations_regex.json",
            ),
            outputs=(derived / "roll_text_evidence.json",),
            cmd=_py(root, "find_text_backed_rolls.py"),
        ),
        Step(
            name="derive_roll_outcomes",
            inputs=inputs(
                derived / "predicted_rolls.json",
                derived / "obtained_perks.json",
                derived / "chapters.json",
                derived / "chapter_sections.json",
                section_classifications,
                manual / "multi_grab_overrides.json",
            ),
            outputs=(derived / "roll_outcomes.json",),
            cmd=_py(root, "derive_roll_outcomes.py"),
        ),
        Step(
            name="derive_timeline",
            inputs=inputs(
                derived / "timeline_xlsx.json",
                derived / "timeline_wiki.json",
                _p(root, "data", "labeled", "spans"),
                manual / "timeline_manual.json",
            ),
            outputs=(derived / "timeline.json",),
            cmd=_py(root, "derive_timeline.py"),
        ),
        Step(
            name="build_perk_directory",
            inputs=inputs(
                raw / "Brocktons_Celestial_Forge_Reference.xlsx",
                derived / "perks_catalog.json",
                derived / "obtained_perks.json",
            ),
            outputs=(derived / "perk_directory.json",),
            cmd=_py(root, "build_perk_directory.py"),
        ),
        Step(
            name="derive_outstanding_perks",
            inputs=inputs(
                derived / "perk_directory.json",
                derived / "obtained_perks.json",
                derived / "chapters.json",
            ),
            outputs=(derived / "outstanding_perks_by_chapter.json",),
            cmd=_py(root, "derive_outstanding_perks.py"),
        ),
        Step(
            name="derive_roll_facts",
            inputs=inputs(
                derived / "rolls.json",
                derived / "roll_outcomes.json",
                derived / "predicted_rolls.json",
                chapter_roll_overrides,
                manual / "roll_overrides.json",
                derived / "roll_text_evidence.json",
                derived / "perk_directory.json",
                derived / "outstanding_perks_by_chapter.json",
                derived / "obtained_perks.json",
                derived / "chapters.json",
                derived / "chapter_sections.json",
                section_classifications,
            ),
            outputs=(
                derived / "roll_facts.json",
                derived / "roll_validation.json",
            ),
            cmd=_py(root, "derive_roll_facts.py"),
        ),
        Step(
            name="build_chapter_facts",
            inputs=inputs(
                epub,
                derived / "chapters.json",
                derived / "chapter_sections.json",
                section_classifications,
                derived / "roll_facts.json",
                derived / "roll_validation.json",
                derived / "predicted_rolls.json",
                chapter_roll_overrides,
                derived / "obtained_perks.json",
                derived / "perk_directory.json",
                manual / "chapter_publication_dates.json",
                derived / "timeline.json",
            ),
            outputs=(
                derived / "chapter_facts.json",
            ),
            cmd=_py(root, "build_chapter_facts.py"),
        ),
        Step(
            name="derive_constellation_lifecycle",
            inputs=inputs(
                derived / "constellation_knowledge_by_chapter.json",
                derived / "outstanding_perks_by_chapter.json",
                _p(root, "data", "constellations"),
            ),
            outputs=(derived / "constellation_lifecycle.json",),
            cmd=_py(root, "derive_constellation_lifecycle.py"),
        ),
        Step(
            name="build_constellation_wireframes",
            inputs=inputs(
                derived / "perk_directory.json",
                derived / "constellation_lifecycle.json",
                _p(root, "data", "constellations"),
            ),
            outputs=(derived / "constellation_wireframes.json",),
            cmd=_py(root, "build_constellation_wireframes.py"),
        ),
        Step(
            name="build_visualization_facts",
            inputs=inputs(
                derived / "chapter_facts.json",
                derived / "constellation_wireframes.json",
                derived / "predicted_rolls.json",
                derived / "data_package.json",
            ),
            outputs=(
                derived / "visualization_facts.json",
                derived / "data_package.json",
            ),
            cmd=_py(root, "build_visualization_facts.py"),
        ),
        Step(
            name="package_data_release",
            inputs=inputs(
                derived / "visualization_facts.json",
                derived / "perk_directory.json",
                derived / "constellation_lifecycle.json",
                derived / "constellation_wireframes.json",
            ),
            outputs=(_p(root, ".data-release", "SHA256SUMS"),),
            cmd=(
                sys.executable,
                str(_p(root, "scripts", "data_release.py")),
                "package",
                "--output-dir",
                str(_p(root, ".data-release")),
            ),
        ),
        Step(
            name="stage_pages_site",
            inputs=inputs(
                _p(root, ".data-release", "SHA256SUMS"),
            ),
            outputs=(_p(root, "_site", "data", "packages.json"),),
            fn=lambda root=root: _stage_pages_site(root),
        ),
        Step(
            name="smoke_pages_site",
            inputs=inputs(_p(root, "_site", "data", "packages.json")),
            outputs=(_p(root, "_site", ".pipeline-smoke-ok"),),
            fn=lambda root=root: _smoke_pages_site(root),
        ),
    ]


TARGET_FINAL_STEPS = {
    "data": ("build_visualization_facts",),
    "package": ("package_data_release",),
    "deploy": ("smoke_pages_site",),
    "all": ("smoke_pages_site",),
}


def all_declared_paths(steps: Iterable[Step]) -> set[Path]:
    paths: set[Path] = set()
    for step in steps:
        paths.update(step.inputs)
        paths.update(step.outputs)
    return paths


def _producer_by_output(steps: Sequence[Step]) -> dict[Path, str]:
    producers: dict[Path, str] = {}
    for step in steps:
        for output in step.outputs:
            if output in producers:
                raise ValueError(
                    f"{output} is produced by both {producers[output]} and {step.name}"
                )
            producers[output] = step.name
    return producers


def _dependencies(steps: Sequence[Step]) -> dict[str, set[str]]:
    producers = _producer_by_output(steps)
    deps: dict[str, set[str]] = {}
    for step in steps:
        deps[step.name] = {
            producers[path]
            for path in step.inputs
            if path in producers and producers[path] != step.name
        }
    return deps


def _target_closure(steps: Sequence[Step], target: str) -> set[str]:
    by_name = {step.name: step for step in steps}
    if target not in TARGET_FINAL_STEPS:
        valid = ", ".join(sorted(TARGET_FINAL_STEPS))
        raise ValueError(f"unknown target {target!r}; expected one of: {valid}")

    deps = _dependencies(steps)
    wanted: set[str] = set()

    def visit(name: str) -> None:
        if name in wanted:
            return
        if name not in by_name:
            raise ValueError(f"target {target!r} references unknown step {name!r}")
        wanted.add(name)
        for dep in deps[name]:
            visit(dep)

    for final_step in TARGET_FINAL_STEPS[target]:
        visit(final_step)
    return wanted


def _topological_order(steps: Sequence[Step], names: set[str]) -> list[Step]:
    deps = _dependencies(steps)
    sorter = TopologicalSorter()
    for step in steps:
        if step.name in names:
            sorter.add(step.name, *(dep for dep in deps[step.name] if dep in names))
    order = tuple(sorter.static_order())
    by_name = {step.name: step for step in steps}
    return [by_name[name] for name in order]


def _path_mtime(path: Path) -> float | None:
    if not path.exists():
        return None
    if path.is_dir():
        mtimes = [path.stat().st_mtime]
        mtimes.extend(p.stat().st_mtime for p in path.rglob("*") if p.exists())
        return max(mtimes)
    return path.stat().st_mtime


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_path(path: Path) -> dict[str, str | None]:
    if not path.exists():
        return {"kind": "missing", "sha256": None}
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(p for p in path.rglob("*") if p.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(_hash_file(child).encode("ascii"))
            digest.update(b"\0")
        return {"kind": "dir", "sha256": digest.hexdigest()}
    return {"kind": "file", "sha256": _hash_file(path)}


def _effective_inputs(step: Step) -> tuple[Path, ...]:
    outputs = set(step.outputs)
    return tuple(path for path in step.inputs if path not in outputs)


def _step_hashes(step: Step) -> dict[str, dict[str, dict[str, str | None]]]:
    return {
        "inputs": {str(path): _hash_path(path) for path in _effective_inputs(step)},
        "outputs": {str(path): _hash_path(path) for path in step.outputs},
    }


def _load_hash_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _write_hash_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")


def _is_stale(
    step: Step,
    *,
    force: bool,
    planned_producers: set[str],
    producer_by_output: dict[Path, str],
    hash_cache: dict,
) -> bool:
    if force:
        return True
    if any(not path.exists() for path in step.outputs):
        return True
    if any(
        producer_by_output.get(path) in planned_producers
        for path in _effective_inputs(step)
    ):
        return True

    input_mtimes = [
        mtime
        for path in _effective_inputs(step)
        if (mtime := _path_mtime(path)) is not None
    ]
    output_mtimes = [
        mtime
        for path in step.outputs
        if (mtime := _path_mtime(path)) is not None
    ]
    if input_mtimes and output_mtimes and max(input_mtimes) > min(output_mtimes):
        return True

    previous = hash_cache.get(step.name)
    if previous is not None and previous != _step_hashes(step):
        return True

    return False


def plan_execution(
    steps: Sequence[Step],
    *,
    target: str,
    force: bool = False,
    hash_cache_path: Path | None = None,
) -> list[Step]:
    selected = _target_closure(steps, target)
    topo_steps = _topological_order(steps, selected)
    cache = _load_hash_cache(hash_cache_path) if hash_cache_path else {}
    producers = _producer_by_output(steps)
    planned_names: set[str] = set()
    plan: list[Step] = []
    for step in topo_steps:
        if _is_stale(
            step,
            force=force,
            planned_producers=planned_names,
            producer_by_output=producers,
            hash_cache=cache,
        ):
            plan.append(step)
            planned_names.add(step.name)
    return plan


def _run_step(step: Step, *, cwd: Path) -> None:
    if step.fn is not None:
        step.fn()
        return
    assert step.cmd is not None
    subprocess.run(step.cmd, cwd=cwd, check=True)


def run_plan(
    plan: Sequence[Step],
    *,
    root: Path,
    hash_cache_path: Path,
) -> None:
    cache = _load_hash_cache(hash_cache_path)
    for step in plan:
        print(f"RUN {step.name}", flush=True)
        _run_step(step, cwd=root)
        cache[step.name] = _step_hashes(step)
        _write_hash_cache(hash_cache_path, cache)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=sorted(TARGET_FINAL_STEPS),
        default="data",
        help="Named target to build.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild all steps in the selected target closure.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the steps that would run without executing them.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    steps = build_steps(root)
    hash_cache_path = root / "data" / "derived" / ".pipeline_hashes.json"
    plan = plan_execution(
        steps,
        target=args.target,
        force=args.force,
        hash_cache_path=hash_cache_path,
    )

    if args.dry_run:
        print(f"DRY-RUN {args.target}: {len(plan)} step(s)")
        for step in plan:
            print(f"  {step.name}")
        return 0

    if not plan:
        print(f"{args.target}: up to date")
        return 0

    run_plan(plan, root=root, hash_cache_path=hash_cache_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

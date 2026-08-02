from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.chapter_roll_overrides_io import (  # noqa: E402
    DEFAULT_DOC,
    load_chapter_roll_overrides_doc,
    write_chapter_roll_overrides_doc,
)


def test_missing_curated_by_raises(tmp_path: Path) -> None:
    """D-01/D-12: an existing chapter entry missing curated_by is a hard
    validation error at load time, never a silent default."""
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "1": {"rolls": []},
        },
    }))

    with pytest.raises(ValueError, match="curated_by"):
        load_chapter_roll_overrides_doc(path)


def test_invalid_curated_by_enum_raises(tmp_path: Path) -> None:
    """D-01: curated_by is enum ["human", "agent"] — anything else is a
    validation error, not a value the loader passes through."""
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "1": {"curated_by": "robot", "rolls": []},
        },
    }))

    with pytest.raises(ValueError, match="curated_by"):
        load_chapter_roll_overrides_doc(path)


def test_live_corpus_loads_and_all_118_entries_are_human() -> None:
    """D-12: loading the live 118-chapter corpus must succeed, and every
    existing entry must carry curated_by == "human" after the bulk stamp.

    Loads the real committed data/manual/chapter_roll_overrides.json
    directly (it is git-tracked, not gitignored) rather than a synthetic
    fixture, formalizing this phase's manual verify step as a test.
    """
    live_path = ROOT / "data" / "manual" / "chapter_roll_overrides.json"

    doc = load_chapter_roll_overrides_doc(live_path)

    entries = doc["chapter_roll_overrides"]
    assert len(entries) == 118
    assert all(entry.get("curated_by") == "human" for entry in entries.values())


def test_missing_file_returns_default_without_validation(tmp_path: Path) -> None:
    """Mirrors test_missing_override_file_has_no_legacy_fallback against
    the new module directly: a genuinely absent file defaults cleanly
    without any schema validation running (nothing on disk to validate)."""
    result = load_chapter_roll_overrides_doc(tmp_path / "chapter_roll_overrides.json")

    assert result == DEFAULT_DOC


# ---------------------------------------------------------------------------
# Gap-closure follow-up (CINF-01): a validated writer, and a regression
# guard proving every write path to chapter_roll_overrides.json is now
# routed through it.
# ---------------------------------------------------------------------------

def test_writer_rejects_missing_curated_by(tmp_path: Path) -> None:
    """The writer validates before touching disk -- an entry missing
    curated_by must raise and must NOT leave a partially-written file."""
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {"chapter_roll_overrides": {"1": {"rolls": []}}}

    with pytest.raises(ValueError, match="curated_by"):
        write_chapter_roll_overrides_doc(doc, path)

    assert not path.exists()


def test_writer_round_trip_matches_load(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {
        "chapter_roll_overrides": {
            "1": {"curated_by": "human", "rolls": [{"perks": ["A"]}]},
        }
    }

    write_chapter_roll_overrides_doc(doc, path)
    reloaded = load_chapter_roll_overrides_doc(path)

    assert reloaded == doc


def test_writer_preserves_non_ascii_characters_verbatim(tmp_path: Path) -> None:
    """D-13 (deferred-items.md, phase 01): the writer must use
    ensure_ascii=False -- a bare json.dumps() default would escape every
    literal unicode character (en-dash, ellipsis, curly quotes) in
    evidence_quotes into \\uXXXX sequences, producing spurious whole-file
    diffs across hand-curated data on every re-stamp."""
    path = tmp_path / "chapter_roll_overrides.json"
    doc = {
        "chapter_roll_overrides": {
            "1": {
                "curated_by": "human",
                "rolls": [{
                    "evidence_quotes": [
                        {"text": "The pre–installed system… “worked”."}
                    ],
                }],
            },
        }
    }

    write_chapter_roll_overrides_doc(doc, path)
    raw = path.read_text(encoding="utf-8")

    assert "–" in raw  # en-dash, literal
    assert "…" in raw  # ellipsis, literal
    assert "“" in raw  # left curly quote, literal
    assert "\\u" not in raw  # never escaped


def test_writer_round_trip_on_live_corpus_is_byte_identical(tmp_path: Path) -> None:
    """The single most important check in this task (per the gap-closure
    objective): loading the real 118-chapter hand-curated corpus through
    the loader and writing it straight back through the new writer must
    reproduce the file byte-for-byte. This is what proves the
    formatting/escaping convention matches exactly -- a regression here
    would silently damage hand-curated data on the next re-stamp run."""
    live_path = ROOT / "data" / "manual" / "chapter_roll_overrides.json"
    original = live_path.read_bytes()

    doc = load_chapter_roll_overrides_doc(live_path)
    scratch_path = tmp_path / "chapter_roll_overrides.json"
    write_chapter_roll_overrides_doc(doc, scratch_path)

    assert scratch_path.read_bytes() == original


# ---------------------------------------------------------------------------
# AST-based scan machinery shared by the two tests below. Widened
# (gap-closure follow-up, CINF-01 second sweep) after the original
# regex-based version of this guard missed a sixth write path:
# scripts/forge_curator/persistence.py wrote the overrides file through a
# local helper (``_atomic_write_json(path, doc)``) that took the
# destination path as a *parameter* rather than referencing a bound path
# constant directly, and that file lives in scripts/forge_curator/ -- a
# subdirectory the original scan (``scripts_dir.glob("*.py")``,
# non-recursive) never looked at. Both gaps are closed here:
# ``scripts_dir.rglob("*.py")`` walks subdirectories, and the scan
# additionally tracks "write-sink" function parameters (a parameter that
# a function passes to ``.write_text``/``.write_bytes`` or as the
# destination of ``os.replace``/``shutil.move``) and flags call sites
# where such a helper is invoked with a path bound to
# chapter_roll_overrides.json.
#
# This remains a static source scan, not a full dataflow analysis: "bound
# to chapter_roll_overrides.json" is computed per-file (a name is bound
# if its assignment's right-hand side contains the literal
# "chapter_roll_overrides.json", or if it is assigned from another name
# already known to be bound -- including names imported from another
# scripts/ module that binds them the same way). Propagation is scoped to
# a single file at a time specifically so that unrelated same-named
# variables in different modules (`OUT`, `path`, `target`, ...) never
# cross-contaminate each other's bound-name sets.


def _idents(src: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", src))


def _resolve_module(scripts_dir: Path, dotted: str) -> Path | None:
    parts = dotted.split(".")
    if parts and parts[0] == "scripts":
        parts = parts[1:]
    if not parts:
        return None
    candidate = scripts_dir.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        return candidate
    candidate_init = scripts_dir.joinpath(*parts, "__init__.py")
    if candidate_init.exists():
        return candidate_init
    return None


def _find_overrides_write_offenders(
    scripts_dir: Path, *, literal: str, sanctioned_files: set[str]
) -> list[str]:
    """Return source locations that write to a path bound to ``literal``
    outside of ``sanctioned_files``, directly or via a write-sink helper.
    """
    py_files = sorted(scripts_dir.rglob("*.py"))
    trees: dict[Path, ast.Module] = {}
    for f in py_files:
        trees[f] = ast.parse(f.read_text(), filename=str(f))

    bound_cache: dict[Path, set[str]] = {}
    in_progress: set[Path] = set()

    def bound_names_for_file(f: Path) -> set[str]:
        if f in bound_cache:
            return bound_cache[f]
        if f in in_progress:
            return set()  # break import cycles
        in_progress.add(f)
        tree = trees[f]

        local_assigns: list[tuple[str, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                rhs_src = ast.unparse(node.value)
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_assigns.append((target.id, rhs_src))
                    elif (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "self"
                    ):
                        local_assigns.append((f"self.{target.attr}", rhs_src))

        bound: set[str] = {
            name for name, rhs in local_assigns if literal in rhs
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                src_file = _resolve_module(scripts_dir, node.module)
                if src_file is None or src_file == f or src_file not in trees:
                    continue
                src_bound = bound_names_for_file(src_file)
                for alias in node.names:
                    if alias.name in src_bound:
                        bound.add(alias.asname or alias.name)

        changed = True
        while changed:
            changed = False
            for name, rhs in local_assigns:
                if name not in bound and _idents(rhs) & bound:
                    bound.add(name)
                    changed = True

        in_progress.discard(f)
        bound_cache[f] = bound
        return bound

    bound_by_file = {f: bound_names_for_file(f) for f in trees}

    # Write-sink parameters: for every function/method, any parameter
    # that is itself the target of .write_text/.write_bytes, or the
    # destination argument of os.replace(...)/shutil.move(...).
    sinks: dict[str, list[tuple[str, int]]] = {}
    for tree in trees.values():
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [a.arg for a in node.args.args]
            sink_params: set[str] = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Attribute):
                    continue
                func = sub.func
                if (
                    func.attr in {"write_text", "write_bytes"}
                    and isinstance(func.value, ast.Name)
                    and func.value.id in params
                ):
                    sink_params.add(func.value.id)
                if (
                    func.attr in {"replace", "move"}
                    and len(sub.args) >= 2
                    and isinstance(sub.args[1], ast.Name)
                    and sub.args[1].id in params
                ):
                    sink_params.add(sub.args[1].id)
            for p in sink_params:
                sinks.setdefault(node.name, []).append((p, params.index(p)))

    offenders: list[str] = []
    for f, tree in trees.items():
        if f.name in sanctioned_files:
            continue
        local_bound = bound_by_file[f]

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"write_text", "write_bytes"}:
                continue
            target = node.func.value
            hit = (
                isinstance(target, ast.Name) and target.id in local_bound
            ) or (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
                and f"self.{target.attr}" in local_bound
            )
            if hit:
                offenders.append(
                    f"{f}:{node.lineno}: direct {ast.unparse(node.func)}(...)"
                )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = None
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname not in sinks:
                continue
            for param_name, idx in sinks[fname]:
                arg_node = None
                if idx < len(node.args):
                    arg_node = node.args[idx]
                else:
                    for kw in node.keywords:
                        if kw.arg == param_name:
                            arg_node = kw.value
                if arg_node is None:
                    continue
                arg_src = ast.unparse(arg_node)
                if arg_src in local_bound or (_idents(arg_src) & local_bound):
                    offenders.append(
                        f"{f}:{node.lineno}: indirect via "
                        f"{fname}(...) arg={arg_src!r}"
                    )

    return offenders


def test_no_bare_write_path_to_overrides_file() -> None:
    """Regression guard: the only sanctioned way to write
    data/manual/chapter_roll_overrides.json is
    chapter_roll_overrides_io.write_chapter_roll_overrides_doc (which
    delegates to _common.write_validated_json). This closes two gaps
    found in successive sweeps:

    1. Five scripts/*.py modules read/wrote the file directly with bare
       json.loads/json.dumps/write_text, bypassing schema validation
       entirely -- two of them wrote the corpus back unvalidated and
       with ensure_ascii defaulting to True, corrupting unicode in
       hand-curated evidence quotes on every run (deferred-items.md,
       phase 01).
    2. A sixth path in scripts/forge_curator/persistence.py (the Forge
       Curator TUI's auto-save, the highest-traffic write to this file)
       wrote through a local ``_atomic_write_json(path, doc)`` helper
       with zero schema validation -- missed by the original version of
       this guard because it only scanned scripts/*.py non-recursively
       and only matched literal ``<bound_name>.write_text(...)``, not a
       helper that receives the path as a parameter.

    This is a durable, grep/AST-style source assertion (not an
    exhaustive behavioral test) precisely because the failure mode it
    guards against is a *future* contributor adding a seventh bare (or
    indirect) write path -- it should fail loudly and immediately,
    without needing a fixture that exercises the new code. See
    ``test_scan_detects_synthetic_indirect_write_helper`` below for a
    fixture-based proof that the indirect-write detection itself works.
    """
    offenders = _find_overrides_write_offenders(
        SCRIPTS,
        literal="chapter_roll_overrides.json",
        sanctioned_files={"_common.py", "chapter_roll_overrides_io.py"},
    )

    assert not offenders, (
        "found a write to a path bound to chapter_roll_overrides.json "
        "outside chapter_roll_overrides_io.write_chapter_roll_overrides_doc "
        f"(direct or via a helper) -- route through it instead: {offenders}"
    )


def test_scan_detects_synthetic_indirect_write_helper(tmp_path: Path) -> None:
    """Proves the indirect-write detection in
    _find_overrides_write_offenders actually catches the shape of bug it
    was added for, rather than merely asserting a clean bill of health
    on the (now-fixed) real repo. Reproduces the exact pre-fix
    persistence.py shape in a throwaway fixture tree: a module-level
    path constant bound to the overrides file, and a sibling module
    whose helper function receives the path as a parameter and writes
    to it via tmp-then-os.replace -- structurally identical to
    ``_atomic_write_json`` / ``_write_chapter_roll_overrides`` before
    the CINF-01 gap-closure fix."""
    scripts_dir = tmp_path / "scripts"
    (scripts_dir / "sub").mkdir(parents=True)

    (scripts_dir / "data_paths.py").write_text(
        "from pathlib import Path\n"
        'MANUAL = Path(".")\n'
        'CHAPTER_ROLL_OVERRIDES = MANUAL / "chapter_roll_overrides.json"\n'
    )
    (scripts_dir / "sub" / "persistence.py").write_text(
        "import os\n"
        "from pathlib import Path\n"
        "from data_paths import CHAPTER_ROLL_OVERRIDES\n"
        "\n"
        "def _atomic_write_json(path, doc):\n"
        '    tmp = path.with_suffix(path.suffix + ".tmp")\n'
        "    tmp.write_text(str(doc))\n"
        "    os.replace(tmp, path)\n"
        "\n"
        "class CurationPersistence:\n"
        "    def __init__(self):\n"
        "        self.chapter_roll_overrides_path = CHAPTER_ROLL_OVERRIDES\n"
        "        self.doc = {}\n"
        "\n"
        "    def _write(self):\n"
        "        _atomic_write_json(self.chapter_roll_overrides_path, self.doc)\n"
    )

    offenders = _find_overrides_write_offenders(
        scripts_dir,
        literal="chapter_roll_overrides.json",
        sanctioned_files={"_common.py", "chapter_roll_overrides_io.py"},
    )

    assert any("_atomic_write_json" in o for o in offenders), (
        "expected the synthetic indirect-write helper to be flagged, "
        f"got offenders={offenders}"
    )

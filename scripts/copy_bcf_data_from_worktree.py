"""Copy local generated BCF data from another registered git worktree."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_DERIVED = Path("data/derived")


def git_worktrees() -> list[Path]:
    output = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"],
        text=True,
    )
    paths: list[Path] = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.removeprefix("worktree ")))
    return paths


def find_source_dir(source_dir: Path) -> Path:
    cwd = Path.cwd().resolve()
    candidates: list[Path] = []
    for worktree in git_worktrees():
        worktree = worktree.resolve()
        if worktree == cwd:
            continue
        candidate = worktree / source_dir
        if (candidate / "chapter_facts.json").is_file():
            candidates.append(candidate)

    if not candidates:
        raise RuntimeError(
            f"could not find hydrated {source_dir} in another registered git worktree"
        )

    def sort_key(path: Path) -> tuple[int, int, str]:
        path_text = str(path)
        is_codex_worktree = "/.codex/worktrees/" in path_text
        return (int(is_codex_worktree), len(path_text), path_text)

    return sorted(candidates, key=sort_key)[0]


def copy_derived_json(source: Path, output_dir: Path, *, force: bool = False) -> list[Path]:
    files = sorted(path for path in source.glob("*.json") if path.is_file())
    if not files:
        raise RuntimeError(f"no top-level derived JSON files found in {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source_path in files:
        dest = output_dir / source_path.name
        if dest.exists() and not force:
            continue
        shutil.copy2(source_path, dest)
        copied.append(dest)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_DERIVED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DERIVED)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if (args.output_dir / "chapter_facts.json").exists() and not args.force:
        print(f"{args.output_dir} already hydrated; skipping copy")
        return 0

    try:
        source = find_source_dir(args.source_dir)
        copied = copy_derived_json(source, args.output_dir, force=args.force)
    except Exception as exc:
        print(f"failed to copy derived data from another worktree: {exc}", file=sys.stderr)
        return 1

    print(f"copied {len(copied)} derived JSON files from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

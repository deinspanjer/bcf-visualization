"""Copy the local BCF EPUB from another registered git worktree."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_EPUB = Path("data/raw/Brocktons_Celestial_Forge.epub")


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


def find_source_epub(source_path: Path, output: Path) -> Path:
    cwd = Path.cwd().resolve()
    output_abs = output.resolve()
    candidates: list[Path] = []
    for worktree in git_worktrees():
        worktree = worktree.resolve()
        if worktree == cwd:
            continue
        candidate = worktree / source_path
        if candidate.exists() and candidate.resolve() != output_abs:
            candidates.append(candidate)

    if not candidates:
        raise RuntimeError(
            f"could not find {source_path} in another registered git worktree"
        )

    def sort_key(path: Path) -> tuple[int, int, str]:
        path_text = str(path)
        is_codex_worktree = "/.codex/worktrees/" in path_text
        return (int(is_codex_worktree), len(path_text), path_text)

    return sorted(candidates, key=sort_key)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-path", type=Path, default=DEFAULT_EPUB)
    parser.add_argument("--output", type=Path, default=DEFAULT_EPUB)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; skipping copy")
        return 0

    try:
        source = find_source_epub(args.source_path, args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, args.output)
    except Exception as exc:
        print(f"failed to copy EPUB from another worktree: {exc}", file=sys.stderr)
        return 1

    print(f"copied {args.output} from {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

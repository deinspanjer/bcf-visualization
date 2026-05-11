"""Run the repo-local verification gate agents should use before completion."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def verification_commands(python: str = sys.executable) -> list[list[str]]:
    return [
        ["git", "diff", "--check"],
        [python, "scripts/data_release.py", "check-derived"],
        [python, "-m", "pytest"],
    ]


def main() -> None:
    for cmd in verification_commands():
        print(f"+ {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

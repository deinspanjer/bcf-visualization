"""Run the default repo-local verification gate.

This gate covers Forge Curator, generated-data contracts, and the static
visualization. The local NLP scaffold has a separate gate in
``scripts/verify_nlp.py`` so FastAPI/model-server environment issues do
not block curation/data-flow work.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

NLP_TESTS = [
    "tests/test_bootstrap.py",
    "tests/test_candidates.py",
    "tests/test_encode.py",
    "tests/test_schema.py",
    "tests/test_serve.py",
    "tests/test_train_smoke.py",
    "tests/test_tui_persist.py",
]


def verification_commands(python: str = sys.executable) -> list[list[str]]:
    return [
        ["git", "diff", "--check"],
        [python, "scripts/data_release.py", "check-derived"],
        [
            python,
            "-m",
            "pytest",
            *[arg for test_path in NLP_TESTS for arg in ("--ignore", test_path)],
        ],
    ]


def main() -> None:
    for cmd in verification_commands():
        print(f"+ {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

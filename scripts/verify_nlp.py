"""Run the local NLP scaffold verification gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    from scripts.verify import NLP_TESTS
except ModuleNotFoundError:  # direct execution: python scripts/verify_nlp.py
    from verify import NLP_TESTS


ROOT = Path(__file__).resolve().parent.parent


def verification_commands(python: str = sys.executable) -> list[list[str]]:
    return [
        [python, "-m", "pytest", *NLP_TESTS],
    ]


def main() -> None:
    for cmd in verification_commands():
        print(f"+ {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

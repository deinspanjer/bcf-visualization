from __future__ import annotations

from scripts import verify
from scripts import verify_nlp


def test_verification_commands_include_coherence_whitespace_and_non_nlp_pytest() -> None:
    commands = verify.verification_commands("python")

    assert commands == [
        ["git", "diff", "--check"],
        ["python", "scripts/data_release.py", "check-derived"],
        [
            "python",
            "-m",
            "pytest",
            "--ignore",
            "tests/test_bootstrap.py",
            "--ignore",
            "tests/test_candidates.py",
            "--ignore",
            "tests/test_encode.py",
            "--ignore",
            "tests/test_schema.py",
            "--ignore",
            "tests/test_serve.py",
            "--ignore",
            "tests/test_train_smoke.py",
            "--ignore",
            "tests/test_tui_persist.py",
        ],
    ]


def test_nlp_verification_command_runs_only_nlp_tests() -> None:
    commands = verify_nlp.verification_commands("python")

    assert commands == [
        [
            "python",
            "-m",
            "pytest",
            "tests/test_bootstrap.py",
            "tests/test_candidates.py",
            "tests/test_encode.py",
            "tests/test_schema.py",
            "tests/test_serve.py",
            "tests/test_train_smoke.py",
            "tests/test_tui_persist.py",
        ],
    ]

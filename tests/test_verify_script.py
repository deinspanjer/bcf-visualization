from __future__ import annotations

from scripts import verify


def test_verification_commands_include_coherence_whitespace_and_full_pytest() -> None:
    commands = verify.verification_commands("python")

    assert commands == [
        ["git", "diff", "--check"],
        ["python", "scripts/data_release.py", "check-derived"],
        ["python", "-m", "pytest"],
    ]

"""Smoke test: run train_span and train_section on the tiny fixtures.

Skips entirely if torch is not installed (designed for the iMac).
On the GPU box with torch: runs one epoch, checks artifacts exist.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Skip the whole module at collection time if torch is not available.
torch = pytest.importorskip("torch", reason="torch not installed")

pytestmark = pytest.mark.skipif(
    os.environ.get("BCF_RUN_TRAIN_SMOKE") != "1",
    reason="training smoke tests download and train a backbone; set BCF_RUN_TRAIN_SMOKE=1",
)

FIXTURES = Path(__file__).parent / "fixtures"
TINY_SPANS = FIXTURES / "tiny_spans.jsonl"
TINY_SECTIONS = FIXTURES / "tiny_sections.jsonl"
SMOKE_BACKBONE = os.environ.get(
    "BCF_TRAIN_SMOKE_BACKBONE",
    "hf-internal-testing/tiny-random-bert",
)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(REPO_ROOT)
        if not existing_pythonpath
        else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"
    )
    return subprocess.run(
        [sys.executable] + cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
    )


REPO_ROOT = Path(__file__).parent.parent


@pytest.mark.slow
def test_train_span_smoke(tmp_path, monkeypatch):
    """train_span.py runs end-to-end on tiny fixture without crashing."""
    # Patch checkpoints dir to a temp location to avoid polluting the repo
    monkeypatch.chdir(tmp_path)
    result = _run(
        [
            "-m",
            "nlp.train_span",
            "--train", str(TINY_SPANS),
            "--eval", str(TINY_SPANS),
            "--version", "vtest",
            "--epochs", "1",
            "--batch-size", "1",
            "--backbone", SMOKE_BACKBONE,
        ],
        cwd=tmp_path,
    )
    print("STDOUT:", result.stdout[-2000:])
    print("STDERR:", result.stderr[-2000:])
    assert result.returncode == 0, f"train_span.py exited {result.returncode}:\n{result.stderr}"

    # Check artifacts
    ckpt = tmp_path / "checkpoints" / "span" / "vtest"
    assert (ckpt / "metrics_final.json").exists()
    assert (ckpt / "dataset_manifest.json").exists()
    assert (ckpt / "git_state.json").exists()
    assert (ckpt / "env.json").exists()


@pytest.mark.slow
def test_train_section_smoke(tmp_path, monkeypatch):
    """train_section.py runs end-to-end on tiny fixture without crashing."""
    monkeypatch.chdir(tmp_path)
    result = _run(
        [
            "-m",
            "nlp.train_section",
            "--train", str(TINY_SECTIONS),
            "--eval", str(TINY_SECTIONS),
            "--version", "vtest",
            "--epochs", "1",
            "--batch-size", "1",
            "--backbone", SMOKE_BACKBONE,
        ],
        cwd=tmp_path,
    )
    print("STDOUT:", result.stdout[-2000:])
    print("STDERR:", result.stderr[-2000:])
    assert result.returncode == 0, f"train_section.py exited {result.returncode}:\n{result.stderr}"

    ckpt = tmp_path / "checkpoints" / "section" / "vtest"
    assert (ckpt / "metrics_final.json").exists()
    assert (ckpt / "dataset_manifest.json").exists()

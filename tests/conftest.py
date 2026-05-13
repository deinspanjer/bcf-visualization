from __future__ import annotations

import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_ROOT = ROOT / "tests" / ".tmp-data" / f"data-{os.getpid()}"


def _copy_project_data_for_tests() -> None:
    if TEST_DATA_ROOT.exists():
        shutil.rmtree(TEST_DATA_ROOT)
    for dirname in ("raw", "manual", "derived"):
        shutil.copytree(ROOT / "data" / dirname, TEST_DATA_ROOT / dirname)


_copy_project_data_for_tests()
os.environ["BCF_DATA_DIR"] = str(TEST_DATA_ROOT)

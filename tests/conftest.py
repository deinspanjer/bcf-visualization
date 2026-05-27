from __future__ import annotations

import atexit
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TEST_DATA_ROOT = ROOT / "tests" / ".tmp-data" / f"data-{os.getpid()}"


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _cleanup_stale_test_data() -> None:
    tmp_root = ROOT / "tests" / ".tmp-data"
    if not tmp_root.exists():
        return
    current_name = f"data-{os.getpid()}"
    for child in tmp_root.iterdir():
        if not child.is_dir() or not child.name.startswith("data-"):
            continue
        if child.name == current_name:
            continue
        try:
            pid = int(child.name.removeprefix("data-"))
        except ValueError:
            pid = -1
        if pid > 0 and _pid_is_running(pid):
            continue
        shutil.rmtree(child, ignore_errors=True)


def _cleanup_current_test_data() -> None:
    shutil.rmtree(TEST_DATA_ROOT, ignore_errors=True)


def _copy_project_data_for_tests() -> None:
    _cleanup_stale_test_data()
    if TEST_DATA_ROOT.exists():
        shutil.rmtree(TEST_DATA_ROOT)
    for dirname in ("raw", "manual", "derived"):
        shutil.copytree(ROOT / "data" / dirname, TEST_DATA_ROOT / dirname)


_copy_project_data_for_tests()
atexit.register(_cleanup_current_test_data)
os.environ["BCF_DATA_DIR"] = str(TEST_DATA_ROOT)

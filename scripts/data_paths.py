"""Shared data-directory paths.

Production uses ``data/`` at the repository root. Tests may set
``BCF_DATA_DIR`` before importing project modules to isolate generated data.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("BCF_DATA_DIR", ROOT / "data")).resolve()
RAW = DATA / "raw"
DERIVED = DATA / "derived"
MANUAL = DATA / "manual"

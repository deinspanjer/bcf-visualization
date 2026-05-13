from __future__ import annotations

import os
from pathlib import Path

from scripts import data_paths
from scripts.forge_curator import data_loader


def test_pytest_uses_isolated_project_data_copy() -> None:
    data_dir = Path(os.environ["BCF_DATA_DIR"])

    assert data_dir.parent.parts[-2:] == ("tests", ".tmp-data")
    assert data_dir.name.startswith("data-")
    assert data_paths.DERIVED == data_dir / "derived"
    assert data_loader.CHAPTER_FACTS == data_dir / "derived" / "chapter_facts.json"
    assert data_loader.CHAPTER_ROLL_OVERRIDES == (
        data_dir / "manual" / "chapter_roll_overrides.json"
    )

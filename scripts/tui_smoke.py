"""Smoke test / operator aid for the BCF Annotation TUI.

Builds 3 synthetic Candidates (no llama.cpp, no EPUB), launches the TUI
pointed at a tmp JSONL file, then prints copy/paste instructions.

Usage::

    python scripts/tui_smoke.py

After the TUI opens:
  - Press 's' to save the current passage and advance.
  - Press 's' again for the second, 's' again for the third.
  - Press 'q' to quit.
  - Then check the tmp JSONL file for 3 saved records.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Make sure the nlp package is importable when run from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from nlp.tui.app import BcfAnnotationApp
from nlp.tui.candidates import Candidate, QueueState

SYNTHETIC_CANDIDATES = [
    Candidate(
        passage_id="smoke_ch01_p00",
        chapter_num="1",
        section_index=0,
        epub_char_start=0,
        epub_char_end=200,
        text=(
            "Joe stared at the spinning wheel, heart hammering in his chest. "
            "It clicked and stuttered — then locked. The screen announced he'd "
            "gained Perfect Pitch. He blinked, not quite believing it."
        ),
        source="predicted_roll",
    ),
    Candidate(
        passage_id="smoke_ch01_p01",
        chapter_num="1",
        section_index=0,
        epub_char_start=201,
        epub_char_end=400,
        text=(
            "The Toolkit constellation unfolded before him like a blueprint "
            "made of starlight. Each node a possibility, each edge a path "
            "not yet walked."
        ),
        source="predicted_roll",
    ),
    Candidate(
        passage_id="smoke_ch01_p02",
        chapter_num="1",
        section_index=1,
        epub_char_start=401,
        epub_char_end=600,
        text=(
            "Garment crossed her arms, watching Joe from across the workshop. "
            "'You missed again,' she said simply. The wheel had stopped on nothing."
        ),
        source="regex_anchor",
    ),
]


def main() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="bcf_smoke_")
    jsonl_path = Path(tmp_dir) / "smoke.jsonl"
    wal_path = Path(tmp_dir) / ".smoke_wal.jsonl"

    print("=" * 60)
    print("BCF Annotation TUI — smoke test")
    print("=" * 60)
    print(f"Output JSONL : {jsonl_path}")
    print(f"WAL file     : {wal_path}")
    print()
    print("3 synthetic candidates loaded (no llama.cpp required).")
    print()
    print("Instructions:")
    print("  1. The TUI will open. Read the first passage.")
    print("  2. Press 'a' to add a span (start=0, end=10, label=ACQUISITION).")
    print("  3. Press 's' to save and advance.")
    print("  4. Press 's' twice more for the remaining passages.")
    print("  5. Press 'q' to quit.")
    print()
    print(f"After quitting, verify: python3 -c \"")
    print(f"  import json, pathlib")
    print(f"  lines = pathlib.Path('{jsonl_path}').read_text().splitlines()")
    print(f"  print(f'Records saved: {{len(lines)}}')\"")
    print("=" * 60)
    print()

    # Build app with synthetic queue (bypass fill_queue by pre-populating)
    app = BcfAnnotationApp(
        jsonl_path=jsonl_path,
        wal_path=wal_path,
        annotator="smoke_tester",
        strategy="balanced",
    )

    # Inject synthetic candidates directly into the queue
    app._queue._queue = list(SYNTHETIC_CANDIDATES)
    app._queue._cursor = 0

    app.run()

    # Post-run report
    print()
    if jsonl_path.exists():
        lines = [l for l in jsonl_path.read_text().splitlines() if l.strip()]
        print(f"Records saved: {len(lines)}")
        for line in lines:
            import json
            data = json.loads(line)
            pid = data.get("passage_id", "?")
            nspans = len(data.get("spans", []))
            print(f"  {pid}: {nspans} span(s)")
    else:
        print("No records written (nothing was saved).")


if __name__ == "__main__":
    main()

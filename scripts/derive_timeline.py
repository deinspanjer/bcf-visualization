"""Merge all in-world timeline sources into a single canonical file.

Inputs (each a separate "source" of timeline events):
  - data/derived/timeline_xlsx.json   - parsed by scripts/parse_reference.py
  - data/derived/timeline_wiki.json   - parsed by scripts/parse_wiki_timeline.py
  - data/labeled/spans/*.jsonl        - TUI-labeled DATE_REF spans (future)
  - data/manual/timeline_manual.json  - hand-curated entries

Output:
  - data/derived/timeline.json   - canonical merged timeline (schema v2)

Design rules (NOT negotiable - reflect explicit user requirements):

  1. IN-NARRATION ONLY. Pre-narration backstory dates (Joe's high
     school graduation, Sabah's trigger, etc.) carry zero value to
     the planetarium visualization and are dropped at the cutoff
     CUTOFF_IN_WORLD_DATE_ISO. The xlsx upstream still parses them;
     they just don't enter the canonical file.
  2. NO automated deduplication. Multiple entries on the same in-world
     date from different sources are kept as separate entries; consumers
     decide presentation.
  3. NO guessed chapter linkage. xlsx and wiki entries always carry
     chapter_num=null. Only TUI spans (which carry the chapter context
     of the passage they were labeled in) and manual entries (which a
     human typed) may attest a chapter_num.
  4. NO free-form attributes. Only the fields enumerated in
     data/derived/_schemas/timeline.schema.json are emitted; the writer
     is schema-validated on every run.
  5. Atomic events. xlsx rows that contain newline-separated prose are
     split into one entry per line (the curator's own newlines define
     the boundaries; we don't invent new ones). Wiki bullets are
     already atomic.
  6. Stable ids. Each entry gets a deterministic id derived from its
     source + position, so re-runs yield the same ids.

Empty inputs are skipped silently. The TUI source is currently a
placeholder (no DATE_REF spans labeled yet) and contributes zero
entries until annotation work resumes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Allow `from _common import ...` whether run as module or script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import write_validated_json  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_XLSX = ROOT / "data" / "derived" / "timeline_xlsx.json"
DEFAULT_WIKI = ROOT / "data" / "derived" / "timeline_wiki.json"
DEFAULT_TUI_DIR = ROOT / "data" / "labeled" / "spans"
DEFAULT_MANUAL = ROOT / "data" / "manual" / "timeline_manual.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "timeline.json"

SCHEMA_VERSION = 2

# Earliest in-world date the canonical timeline includes.
#
# Cutoff is Joe's trigger (2011-04-01) — the narrative moment his power
# is "working", even though by the simulator's word-accumulation
# mechanic he doesn't start gaining points until story narration begins
# in chapter 1 on 2011-04-08. Trigger week (April 1-7) is therefore
# kept; everything earlier (high school, college, depression backstory)
# is dropped at merge time. The in-narration window is what the
# planetarium will actually visualize.
CUTOFF_IN_WORLD_DATE_ISO = "2011-04-01"

# Allowed entry source values, mirrored from timeline.schema.json.
_SOURCES = ("xlsx", "wiki", "tui", "manual")


def _make_entry(
    *,
    id: str,
    in_world_date_iso: str,
    event_text: str,
    source: str,
    source_ref: str,
    chapter_num: str | None,
    time_of_day: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Build a single canonical entry. Centralised so every entry has the
    exact same shape — the schema validator catches drift, but doing it
    here keeps the writer simple and consistent.

    Schema invariant: xlsx and wiki sources may not attest time_of_day
    or chapter_num; the schema enforces this and so do we, defensively.
    """
    if source in ("xlsx", "wiki"):
        if time_of_day is not None or chapter_num is not None:
            raise ValueError(
                f"source={source} may not attest time_of_day/chapter_num "
                f"(got time_of_day={time_of_day!r}, chapter_num={chapter_num!r})"
            )
    return {
        "id": id,
        "in_world_date_iso": in_world_date_iso,
        "time_of_day": time_of_day,
        "event_text": event_text.strip(),
        "source": source,
        "source_ref": source_ref,
        "chapter_num": chapter_num,
        "tags": tags or [],
    }


def load_xlsx_entries(path: Path) -> list[dict]:
    """Convert timeline_xlsx.json rows into canonical entries.

    Rows dated before CUTOFF_IN_WORLD_DATE_ISO (pre-narration backstory),
    or with no extractable ISO date, are dropped. Rows whose `events`
    field contains newlines are split into one entry per line.
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    out: list[dict] = []
    for row in data["entries"]:
        iso = row.get("in_world_date_iso")
        if not iso or iso < CUTOFF_IN_WORLD_DATE_ISO:
            continue
        seq = row["sequence"]
        # Split on newlines; preserve order.
        parts = [p.strip() for p in str(row["events"]).split("\n") if p.strip()]
        if not parts:
            continue
        for i, part in enumerate(parts):
            entry_id = f"xlsx:{seq}" if len(parts) == 1 else f"xlsx:{seq}.{i + 1}"
            ref = (
                f"Reference.xlsx#Timeline of Events row {seq}"
                + (f" line {i + 1}" if len(parts) > 1 else "")
                + f" [{row.get('attribution', 'unknown')}]"
            )
            out.append(_make_entry(
                id=entry_id,
                in_world_date_iso=iso,
                event_text=part,
                source="xlsx",
                source_ref=ref,
                chapter_num=None,
            ))
    return out


def load_wiki_entries(path: Path) -> list[dict]:
    """Convert timeline_wiki.json bullets into canonical entries.

    Each bullet becomes one entry. chapter_num is always null. Bullets
    dated before CUTOFF_IN_WORLD_DATE_ISO are dropped.
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    out: list[dict] = []
    for entry in data["entries"]:
        iso = entry["in_world_date_iso"]
        if iso < CUTOFF_IN_WORLD_DATE_ISO:
            continue
        for i, bullet in enumerate(entry["events"]):
            text = bullet["text"] if isinstance(bullet, dict) else str(bullet)
            entry_id = f"wiki:{iso}:{i}"
            ref = f"Wiki Timeline / {entry['date_text']} / bullet {i + 1}"
            out.append(_make_entry(
                id=entry_id,
                in_world_date_iso=iso,
                event_text=text,
                source="wiki",
                source_ref=ref,
                chapter_num=None,
            ))
    return out


def load_manual_entries(path: Path) -> list[dict]:
    """Convert manual entries into canonical form.

    Entries dated before CUTOFF_IN_WORLD_DATE_ISO are dropped (the
    curator is welcome to add them, but the canonical timeline is
    in-narration only). The on-disk schema lets the curator omit
    `chapter_num` and `tags` for ergonomics; we normalise here.
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    out: list[dict] = []
    for raw in data.get("entries", []):
        iso = raw["in_world_date_iso"]
        if iso < CUTOFF_IN_WORLD_DATE_ISO:
            continue
        entry_id = f"manual:{raw['id']}"
        ref = raw.get("note", "").strip() or f"timeline_manual.json#{raw['id']}"
        out.append(_make_entry(
            id=entry_id,
            in_world_date_iso=iso,
            event_text=raw["event_text"],
            source="manual",
            source_ref=ref,
            chapter_num=raw.get("chapter_num"),
            time_of_day=raw.get("time_of_day"),
            tags=raw.get("tags") or [],
        ))
    return out


def load_tui_entries(span_dir: Path) -> list[dict]:
    """Extract DATE_REF spans from labeled TUI output as timeline entries.

    Currently a placeholder: scans for *.jsonl files with SpanRecord
    payloads carrying Layer-B DATE_REF labels. When no such spans
    exist, returns []. This wiring keeps the seam ready for when
    annotation work resumes; no invention happens here.
    """
    if not span_dir.exists():
        return []
    out: list[dict] = []
    for path in sorted(span_dir.glob("*.jsonl")):
        # Skip TUI editor sidecar files (start with underscore) and
        # anything obviously not annotator output.
        if path.name.startswith(".") or path.name.startswith("_"):
            continue
        with path.open() as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                spans = rec.get("spans") or []
                date_spans = [
                    s for s in spans
                    if s.get("layer") == "B" and s.get("label") == "DATE_REF"
                ]
                if not date_spans:
                    continue
                # We need an ISO date to enter the canonical timeline.
                # SpanRecord carries the prose snippet but not a parsed
                # date — so for now we skip emission. When the TUI/derive
                # step gains date parsing this branch will populate
                # entries; the seam is intentional.
                # NOTE: do not invent dates here.
                continue
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    p.add_argument("--wiki", type=Path, default=DEFAULT_WIKI)
    p.add_argument("--tui-dir", type=Path, default=DEFAULT_TUI_DIR)
    p.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    xlsx_entries = load_xlsx_entries(args.xlsx)
    wiki_entries = load_wiki_entries(args.wiki)
    tui_entries = load_tui_entries(args.tui_dir)
    manual_entries = load_manual_entries(args.manual)

    all_entries = xlsx_entries + wiki_entries + tui_entries + manual_entries

    # Sort: by in-world date ascending, then by source order, then by id
    # for deterministic output.
    source_order = {s: i for i, s in enumerate(_SOURCES)}
    all_entries.sort(key=lambda e: (
        e["in_world_date_iso"],
        source_order[e["source"]],
        e["id"],
    ))

    # Verify id uniqueness.
    ids_seen: set[str] = set()
    for e in all_entries:
        if e["id"] in ids_seen:
            raise SystemExit(f"duplicate timeline entry id: {e['id']!r}")
        ids_seen.add(e["id"])

    sources_used = sorted(
        {e["source"] for e in all_entries},
        key=lambda s: source_order[s],
    )
    isos = [e["in_world_date_iso"] for e in all_entries]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "_generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "_sources_used": sources_used,
        "_count": len(all_entries),
        "_first_in_world_date": isos[0] if isos else None,
        "_last_in_world_date": isos[-1] if isos else None,
        "entries": all_entries,
    }

    write_validated_json(args.output, payload, "timeline")

    rel = args.output.relative_to(ROOT)
    print(f"wrote {rel}")
    print(f"  xlsx entries:   {len(xlsx_entries):>4}")
    print(f"  wiki entries:   {len(wiki_entries):>4}")
    print(f"  tui entries:    {len(tui_entries):>4}")
    print(f"  manual entries: {len(manual_entries):>4}")
    print(f"  total entries:  {len(all_entries):>4}")
    print(f"  date range:     "
          f"{payload['_first_in_world_date']} .. {payload['_last_in_world_date']}")
    chap_attested = sum(1 for e in all_entries if e["chapter_num"] is not None)
    tod_attested = sum(1 for e in all_entries if e["time_of_day"] is not None)
    print(f"  with chapter_num attested: {chap_attested}")
    print(f"  with time_of_day attested: {tod_attested}")


if __name__ == "__main__":
    main()

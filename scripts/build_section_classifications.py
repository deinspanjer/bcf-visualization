"""Apply rule-based MC-POV classifications to every chapter section.

Output: data/manual/section_classifications.json — one entry per
(chapter_num, section_index) pair. The rules are derived from
manual review of the section samples extracted by
extract_chapter_sections.py.

Rules in order of precedence:
  1. Implicit (no header) section:
     a. has author's-note marker  -> non-MC (chapter scaffolding + AN)
     b. tiny (<500 words)         -> non-MC (also AN/scaffolding)
     c. chapter is "X.Y Interlude Y" with Y not "Joe" -> non-MC
     d. otherwise                 -> MC (chapter body)
  2. Header is a meta marker (Jumpchain abilities, New Abilities for,
     Author/Note/A/N) -> non-MC.
  3. Header is "Preamble/Addendum/Interlude X" -> MC iff X starts
     with "Joe", else non-MC.
  4. Header is the chapter's full title or part of it; if the title
     itself matches the "X.Y Interlude/Preamble/Addendum Y" pattern,
     apply the Joe-vs-other-character check on Y. Otherwise MC.
  5. Header is "Celestial Forge X Y" (the chapter-heading marker
     used in some chapters) -> MC.
  6. Header is "EMERGENCY NEWS ALERT" / "***" / similar -> non-MC.
  7. Evidence override: if the curator roll log or acquired-perk list
     says mechanics happened in a chapter, at least one non-meta
     narrative section must count for CP. This catches non-Joe POV
     interludes where Joe is still on-screen/interacting enough to earn.

Two specific manual overrides (sections that the rules would mark
REVIEW but I confirmed by reading the prose):
  - ch 43 sec 1 "43 Ripples - Aisha"  -> non-MC (third-person Aisha)
  - ch 46.2 sec 1 "46.2-2 Interlude Colin" -> non-MC (third-person Colin)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS_JSON = ROOT / "data" / "derived" / "chapter_sections.json"
ROLLS_JSON = ROOT / "data" / "derived" / "rolls.json"
OBTAINED_JSON = ROOT / "data" / "derived" / "obtained_perks.json"
OUT = ROOT / "data" / "manual" / "section_classifications.json"

AN_RE = re.compile(r"author'?s?\s+note", re.I)
# Detects an inline "Preamble Lisa Lisa walked..." marker — the keyword,
# a capitalized name, then that same name as the subject of the next
# clause. Catches Preamble/Addendum/Interlude content embedded in an
# implicit section without a <p><strong>...</strong></p> wrapper.
INLINE_PAI_RE = re.compile(
    r"\b(Preamble|Addendum|Interlude)[:\s]+([A-Z][a-zA-Z]+)\b\s+\2\b", re.I
)
# Require a name (alphabetic) after the keyword. The separator can be
# whitespace, a colon, or both: "3.1 Interlude: Brian" and "16.1
# Interlude Weld" both need to match. This avoids matching things like
# "28 Preamble - Addendum Sophia" where the word after "Preamble" is
# just a hyphen (the "Preamble" there is a section-label, not a
# character name).
TITLE_INTERLUDE_RE = re.compile(
    r"^\d+(?:\.\d+)?\s+(Interlude|Preamble|Addendum)[:\s]+([A-Z][a-zA-Z]+)", re.I
)
HEADER_PAI_RE = re.compile(r"^(preamble|addendum|interlude)[:\s]+([A-Z][a-zA-Z]+)", re.I)
# For "Celestial Forge X Y Interlude Z" — if the suffix names a non-Joe
# character, the whole section is that character's POV.
CF_HEADER_RE = re.compile(
    r"celestial forge.*?(Interlude|Preamble|Addendum)[:\s]+([A-Z][a-zA-Z]+)", re.I
)

# Manual overrides for headers the rule-based classifier can't match.
# Both confirmed by reading the section's first paragraph.
MANUAL_OVERRIDES: dict[tuple[str, int], tuple[bool, str]] = {
    ("43", 1): (False, "manual: third-person Aisha POV per sample"),
    ("46.2", 1): (False, "manual: third-person Colin POV per sample"),
}


def classify(section: dict, full_title: str) -> tuple[bool, str]:
    header = section["header"]
    word_count = section["word_count"]
    sample = section["sample"]
    fp = section.get("fp_count", 0)
    tp = section.get("tp_count", 0)

    if header is None:
        # Structural markers (PHO forum / news article / meeting report)
        # indicate non-MC content style ONLY when the pronouns also
        # back that up. ch 37 has a passing "Director X" mention that
        # trips the meeting-report regex but the section is firmly Joe
        # POV (fp=34, tp=0). Use the marker as a tiebreaker, not a
        # blanket override.
        non_mc_markers = [m for m in section.get("structural_markers", [])
                          if m in ("pho", "news", "meeting_report")]
        if non_mc_markers and not (fp > tp and fp >= 5):
            return False, f"implicit with non-MC markers: {','.join(non_mc_markers)}"
        # Author's-note marker: small section is all AN/scaffolding;
        # large section with fp-dominant content is "AN prefix + main
        # story" (chapters 83, 84, etc.).
        if AN_RE.search(sample):
            if word_count < 500:
                return False, f"implicit + AN + tiny ({word_count}w)"
            if fp > tp:
                return True, f"implicit + AN prefix + fp-dominant ({fp}/{tp})"
            return False, f"implicit + AN + non-fp-dominant ({fp}/{tp})"
        if word_count < 500:
            return False, f"implicit but tiny ({word_count}w) — scaffolding/AN"
        # Inline Preamble/Addendum/Interlude marker for non-Joe POV
        # (e.g., "Preamble James James walked through the..." with no
        # <strong> wrapper around the heading).
        m = INLINE_PAI_RE.search(sample)
        if m and not m.group(2).lower().startswith("joe"):
            return False, f"implicit with inline {m.group(1).lower()} {m.group(2)!r}"
        # Whole-chapter interlude / preamble / addendum
        m = TITLE_INTERLUDE_RE.match(full_title)
        if m and not m.group(2).strip().lower().startswith("joe"):
            return False, f"entire {m.group(1).lower()} chapter ({m.group(2)!r})"
        return True, "implicit large MC story"

    h = header.strip()
    hl = h.lower()
    if hl.startswith(("jumpchain abilities", "jumpchain perks")):
        return False, "perks footer"
    if hl.startswith("new abilities for"):
        return False, "companion perks footer"
    if hl.startswith(("author", "a/n", "note")):
        return False, "author note section"

    m = HEADER_PAI_RE.match(h)
    if m:
        target = m.group(2).strip().lower()
        if target.startswith("joe"):
            return True, f"{m.group(1).lower()} Joe → MC"
        return False, f"{m.group(1).lower()} {target!r} (non-Joe)"

    m = TITLE_INTERLUDE_RE.match(h)
    if m:
        target = m.group(2).strip().lower()
        if target.startswith("joe"):
            return True, f"chapter-title {m.group(1).lower()} Joe → MC"
        return False, f"chapter-title {m.group(1).lower()} {target!r}"

    if hl.startswith("celestial forge"):
        # The "Celestial Forge X Y" pattern is sometimes the chapter
        # heading and sometimes a longer title that names an interlude
        # at its tail (e.g., "Celestial Forge 119.4 Interlude Elle").
        m = CF_HEADER_RE.search(h)
        if m and not m.group(2).strip().lower().startswith("joe"):
            return False, f"Celestial Forge title names {m.group(1).lower()} {m.group(2)!r}"
        return True, "Celestial Forge chapter-heading marker"

    if h == full_title or full_title.startswith(h + " ") or full_title.startswith(h + " -"):
        return True, "header matches chapter main title"

    if "EMERGENCY" in h.upper() or "NEWS ALERT" in h.upper():
        return False, "in-story news alert"
    if h.strip() == "***":
        return False, "scene-break / special note marker"

    return True, f"defaulted to MC (unrecognized header {h!r})"


def mechanics_evidence_chapters() -> set[str]:
    """Chapters where trusted mechanics data proves CP-earning text exists."""
    chapters: set[str] = set()
    if ROLLS_JSON.exists():
        rolls = json.loads(ROLLS_JSON.read_text())["rolls"]
        for roll in rolls:
            if roll.get("kind") in {"trigger", "roll", "miss"}:
                chapters.add(roll["chapter_num"])
    if OBTAINED_JSON.exists():
        perks = json.loads(OBTAINED_JSON.read_text())["perks"]
        for perk in perks:
            chapters.add(perk["chapter_num"])
    return chapters


def is_meta_section(section: dict) -> bool:
    header = (section.get("header") or "").strip().lower()
    return header.startswith((
        "jumpchain abilities",
        "jumpchain perks",
        "new abilities for",
        "author",
        "a/n",
        "note",
    ))


def mechanics_override_section_index(sections: list[dict]) -> int | None:
    """Pick the most plausible CP-earning section for a mechanics override."""
    candidates = [
        (i, section)
        for i, section in enumerate(sections)
        if not is_meta_section(section)
    ]
    if not candidates:
        return None
    substantial = [
        (i, section)
        for i, section in candidates
        if section.get("word_count", 0) >= 500
    ]
    pool = substantial or candidates
    return max(pool, key=lambda item: item[1].get("word_count", 0))[0]


def header_span_override(
    section: dict,
    section_word_start: int,
) -> dict | None:
    """Return the generated ineligible span for a section header."""
    word_count = int(section.get("auto_header_word_count") or 0)
    if word_count <= 0:
        return None
    reason_code = (
        "chapter_title_header"
        if section.get("header") is None else "section_header"
    )
    return {
        "word_offset_start": section_word_start,
        "word_offset_end": section_word_start + word_count,
        "counts_for_cp": False,
        "reason_code": reason_code,
        "note": "generated from chapter section header",
        "excerpt": section.get("header") or "",
    }


def merge_span_overrides(
    generated: list[dict],
    existing: list[dict],
) -> list[dict]:
    """Merge generated structural spans with curated manual spans."""
    out: list[dict] = []
    generated_keys = {
        (
            int(span.get("word_offset_start", -1)),
            int(span.get("word_offset_end", -1)),
            str(span.get("reason_code") or ""),
        )
        for span in generated
    }
    for span in generated:
        out.append(span)
    for span in existing:
        key = (
            int(span.get("word_offset_start", -1)),
            int(span.get("word_offset_end", -1)),
            str(span.get("reason_code") or ""),
        )
        if key not in generated_keys:
            out.append(span)
    out.sort(key=lambda span: (
        int(span.get("word_offset_start", 0)),
        int(span.get("word_offset_end", 0)),
        str(span.get("reason_code") or ""),
    ))
    return out


def curator_section_toggle(existing: dict) -> tuple[bool, str] | None:
    """Return explicit curator section eligibility, if one exists."""
    reason = str(existing.get("reason") or "")
    if not reason.startswith("curator toggle:"):
        return None
    return bool(existing.get("counts_for_cp", True)), reason


def main() -> None:
    sections_data = json.loads(SECTIONS_JSON.read_text())
    mechanics_chapters = mechanics_evidence_chapters()
    existing_classifications = {}
    if OUT.exists():
        try:
            existing_classifications = (
                json.loads(OUT.read_text()).get("classifications") or {}
            )
        except Exception:
            existing_classifications = {}

    classifications = {}
    review_count = 0
    for c in sections_data["chapters"]:
        section_word_start = 0
        for i, section in enumerate(c["sections"]):
            override = MANUAL_OVERRIDES.get((c["chapter_num"], i))
            if override is not None:
                counts, reason = override
            else:
                counts, reason = classify(section, c["full_title"])
            key = f"{c['chapter_num']}@{i}"
            existing = existing_classifications.get(key) or {}
            curator_toggle = curator_section_toggle(existing)
            if curator_toggle is not None:
                counts, reason = curator_toggle
            classifications[key] = {
                "chapter_num": c["chapter_num"],
                "section_index": i,
                "header": section["header"],
                "counts_for_cp": counts,
                "reason": reason,
            }
            generated_spans = [
                span for span in [header_span_override(section, section_word_start)]
                if span is not None
            ]
            span_overrides = merge_span_overrides(
                generated_spans,
                existing.get("span_overrides") or [],
            )
            if span_overrides:
                classifications[key]["span_overrides"] = span_overrides
            section_word_start += int(section.get("word_count") or 0)

        chapter_keys = [
            f"{c['chapter_num']}@{i}"
            for i in range(len(c["sections"]))
        ]
        if (
            c["chapter_num"] in mechanics_chapters
            and not any(classifications[key]["counts_for_cp"] for key in chapter_keys)
            and not any(
                curator_section_toggle(existing_classifications.get(key) or {})
                is not None
                for key in chapter_keys
            )
        ):
            override_index = mechanics_override_section_index(c["sections"])
            if override_index is not None:
                key = f"{c['chapter_num']}@{override_index}"
                previous_reason = classifications[key]["reason"]
                classifications[key]["counts_for_cp"] = True
                classifications[key]["reason"] = (
                    "mechanics evidence override: curator roll/acquisition "
                    "exists in chapter, so at least one narrative section "
                    f"must count for CP (was: {previous_reason})"
                )

    n_mc = sum(1 for v in classifications.values() if v["counts_for_cp"])
    n_non = sum(1 for v in classifications.values() if not v["counts_for_cp"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_source": (
            "scripts/build_section_classifications.py applied to "
            "data/derived/chapter_sections.json"
        ),
        "_count": len(classifications),
        "_mc_sections": n_mc,
        "_non_mc_sections": n_non,
        "_note": (
            "Per-section MC POV classifications, used by predict_rolls.py "
            "to compute CP-earning word counts. Overrides for ambiguous "
            "headers are listed in the script. Explicit curator section "
            "eligibility toggles and curated span_overrides from existing "
            "entries are preserved across regeneration."
        ),
        "classifications": classifications,
    }, indent=2, ensure_ascii=False) + "\n")

    print(f"wrote {OUT.relative_to(ROOT)}: {len(classifications)} sections "
          f"({n_mc} mc, {n_non} non-mc)")


if __name__ == "__main__":
    main()

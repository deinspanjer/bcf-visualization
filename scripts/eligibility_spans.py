"""Helpers for section-level CP eligibility span overrides."""

from __future__ import annotations

from typing import Any


def merge_word_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort and merge overlapping or adjacent half-open word ranges."""
    out: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def subtract_word_ranges(
    ranges: list[tuple[int, int]],
    removals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return ``ranges`` minus ``removals``."""
    remaining = merge_word_ranges(ranges)
    for remove_start, remove_end in merge_word_ranges(removals):
        if remove_end <= remove_start:
            continue
        next_remaining: list[tuple[int, int]] = []
        for start, end in remaining:
            if remove_end <= start or end <= remove_start:
                next_remaining.append((start, end))
                continue
            if start < remove_start:
                next_remaining.append((start, remove_start))
            if remove_end < end:
                next_remaining.append((remove_end, end))
        remaining = next_remaining
    return remaining


def section_span_overrides(
    classification_entry: dict[str, Any],
    section_word_start: int,
    section_word_end: int,
) -> list[dict[str, Any]]:
    """Return valid span overrides clipped to a section's word range.

    Overrides are stored in chapter-local word coordinates in
    ``data/manual/section_classifications.json``.
    """
    out: list[dict[str, Any]] = []
    for override in classification_entry.get("span_overrides") or []:
        try:
            start = int(override.get("word_offset_start"))
            end = int(override.get("word_offset_end"))
        except (TypeError, ValueError):
            continue
        start = max(section_word_start, start)
        end = min(section_word_end, end)
        if end <= start:
            continue
        cleaned = dict(override)
        cleaned["word_offset_start"] = start
        cleaned["word_offset_end"] = end
        cleaned["counts_for_cp"] = bool(override.get("counts_for_cp"))
        out.append(cleaned)
    return out


def section_cp_word_count(
    *,
    section_word_start: int,
    section_word_end: int,
    base_counts_for_cp: bool,
    span_overrides: list[dict[str, Any]],
) -> int:
    """Compute CP-earning words after manual span overrides.

    Section eligibility is the base state. Span overrides are then
    applied in file order, so a later overlapping span wins.
    """
    eligible = (
        [(int(section_word_start), int(section_word_end))]
        if base_counts_for_cp else []
    )
    for override in span_overrides:
        start = int(override["word_offset_start"])
        end = int(override["word_offset_end"])
        if bool(override.get("counts_for_cp")):
            eligible = merge_word_ranges([*eligible, (start, end)])
        else:
            eligible = subtract_word_ranges(eligible, [(start, end)])
    return sum(end - start for start, end in eligible)

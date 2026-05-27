from __future__ import annotations

from pathlib import Path

import pytest

from scripts.forge_curator.app import StatsPanel
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def _render_stats_text(app) -> tuple[str, StatsPanel]:
    stats = StatsPanel()
    stats.render_stats(app.state, app)
    rendered = getattr(stats, "_renderable", None) or stats.render()
    return str(rendered) if rendered is not None else "", stats


def test_gutter_marks_use_fixture_semantic_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    cs.regex_hits[3].word_indices = [5]

    by_glyph: dict[str, set[int]] = {}
    for mark in app._compute_gutter_marks():
        by_glyph.setdefault(mark.glyph, set()).add(mark.word_idx)

    assert by_glyph["R"] == {20, 40}
    assert by_glyph["M"] == {20}
    assert by_glyph["Q"] == {17}
    assert by_glyph["N"] == {0}
    assert by_glyph["*"] == {5}
    assert {2, 4}.issubset(by_glyph["."])


def test_gutter_marks_include_hits_annotation_spans_and_suppress_off_chapter_quotes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    cs.derived.roll_facts[0]["outcome"] = "hit"
    cs.meta.sections[0]["span_overrides"] = [
        {
            "word_offset_start": 10,
            "word_offset_end": 12,
            "counts_for_cp": False,
            "reason_code": "joe_not_on_screen",
        }
    ]

    by_glyph: dict[str, set[int]] = {}
    for mark in app._compute_gutter_marks():
        by_glyph.setdefault(mark.glyph, set()).add(mark.word_idx)

    assert by_glyph["H"] == {app._roll_marker_word_index_from_cp(cs, 20)}
    assert by_glyph["A"] == {10}

    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    cs.derived.roll_facts[0]["evidence_quotes"] = []
    app.data.roll_facts["rolls"][0]["evidence_quotes"] = []
    app.persistence.set_roll_visualization_anchor(
        "1",
        1,
        mention_chapter_num="2",
        mention_word_position=None,
        display_position_policy="mechanical",
    )
    app.persistence.append_roll_evidence_at_indices(
        "1",
        [1],
        text="chapter2 forge motes",
        mention_chapter_num="2",
        mention_word_position=0,
    )

    assert [mark for mark in app._compute_gutter_marks() if mark.glyph == "Q"] == []


def test_global_roll_quote_highlights_in_mention_chapter_without_visible_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    quote = "chapter2 forge motes"
    app.data.roll_facts["rolls"][0]["evidence_quotes"] = [
        {
            "text": quote,
            "mention_chapter_num": "2",
            "mention_word_position": 0,
        }
    ]
    text = app.state.chapter.prose.text
    start = text.find(quote)

    assert start >= 0
    assert (start, start + len(quote)) in app._roll_evidence_char_spans(app.state.chapter)


def test_prior_curated_roll_without_source_identity_does_not_leak_into_evidence_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    prior_roll = app.data.roll_facts["rolls"][0]
    prior_roll.pop("source_ordinal", None)
    prior_roll.pop("source_label", None)

    rows = app._roll_evidence_picker_rolls(app.state.chapter)

    assert not any(
        row.get("display_kind") == "predicted_slot"
        and row.get("target_chapter_num") == "1"
        and row.get("target_roll_index") == 1
        for row in rows
    )


def test_stats_panel_groups_prior_visible_rolls_before_current_chapter_rolls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    prior_roll = app.data.roll_facts["rolls"][0]
    prior_roll["visible_chapter_nums"] = ["1", "2"]
    prior_roll["source_chapter_num"] = "2"
    prior_roll["source_word_position"] = 10
    prior_roll["source_cumulative_word_offset"] = 90
    app.state.chapter.derived.roll_facts.insert(0, prior_roll)

    text, _stats = _render_stats_text(app)

    prior_section = text.index("Prior Chapter Rolls")
    current_section = text.index("Rolls (")
    prior_roll_line = text.index("(R1/P1/S1)")
    current_roll_line = text.index("(R2/P2/S2)")

    assert prior_section < prior_roll_line < current_section < current_roll_line


def test_quote_highlight_uses_saved_mention_position_for_duplicate_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    quote = "chapter2 forge"
    cs.derived.roll_facts[0]["evidence_quotes"] = [
        {
            "text": quote,
            "mention_chapter_num": "2",
            "mention_word_position": 8,
        }
    ]

    first_start = cs.prose.text.find(quote)
    expected = (cs.prose.word_offsets[8][0], cs.prose.word_offsets[9][1])

    assert first_start == cs.prose.word_offsets[0][0]
    assert expected in app._roll_evidence_char_spans(cs)


def test_distance_stats_use_predicted_curated_and_evidence_position_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.data.predicted["predicted"] = [
        {"cp_offset": 60},
        {"cp_offset": 140},
    ]
    app.data.roll_facts["rolls"] = [
        {
            "source_kind": "roll",
            "display_cumulative_word_offset": 70,
            "cumulative_word_offset": 70,
            "evidence_quotes": [
                {
                    "text": "first",
                    "mention_chapter_num": "2",
                    "mention_word_position": 0,
                }
            ],
            "display_chapter_num": "2",
            "display_word_position": 10,
            "display_position_policy": "mechanical",
        },
        {
            "source_kind": "roll",
            "display_cumulative_word_offset": 150,
            "cumulative_word_offset": 150,
            "evidence_quotes": [
                {
                    "text": "second",
                    "mention_chapter_num": "2",
                    "mention_word_position": 20,
                }
            ],
            "display_chapter_num": "2",
            "display_word_position": 10,
            "display_position_policy": "mechanical",
        },
    ]

    assert app._predicted_roll_distance_stats(100) == (40, 40)
    assert app._curated_roll_distance_stats(100) == (30, 50)
    assert app._curated_evidence_distance_stats(100) == (40, 60)


def test_stats_registers_roll_targets_for_curated_and_open_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    text, stats = _render_stats_text(app)
    targets = list(stats._roll_line_targets.values())

    assert "Rolls" in text
    assert [
            (
                target["display_kind"],
                target["target_roll_index"],
                target.get("roll_ordinal") or target.get("predicted_ordinal"),
                target["outcome"],
            )
        for target in targets
    ] == [
        ("chapter_roll", 1, 2, "miss"),
        ("predicted_slot", 2, 3, "open"),
    ]


def test_stats_roll_marker_prefers_quote_target_over_mechanical_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    app.state.set_cursor_char(cs.prose.word_offsets[45][0])
    quote_roll = next(
        roll for roll in app._roll_slot_rows(cs, app._unified_rolls(cs))
        if roll.get("target_roll_index") == 1
    )
    monkeypatch.setattr(
        app,
        "_roll_evidence_quote_targets_at_selection_or_cursor",
        lambda: [{
            "roll": quote_roll,
            "target_chapter": "2",
            "target_index": 1,
            "quote": {
                "text": "chapter2 forge motes",
                "mention_chapter_num": "2",
                "mention_word_position": 0,
            },
        }],
    )

    text, _stats = _render_stats_text(app)

    assert "▸ # 1" in text
    assert "▸ # 2" not in text


def test_stats_panel_summarizes_long_curation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app._last_curation_error = "\n".join(
        [
            "8 chapter(s) have curator overrides anchored to a stale predicted-roll shape:",
            "  ch 65: stored=sha256:old current=sha256:new",
            "  ch 67: stored=sha256:old current=sha256:new",
            "",
            "The predicted-roll slot sequence in these chapters has changed.",
        ]
    )

    text, _stats = _render_stats_text(app)

    curation_lines = [
        line for line in text.splitlines()
        if "Curation" in line or "Details" in line
    ]
    assert len(curation_lines) == 2
    assert "ch 65" not in text
    assert "ch 67" not in text


def test_roll_stat_line_repeats_q_for_each_evidence_quote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "roll_number": 7,
            "outcome": "hit",
            "constellation": "Clothing",
            "available_cp": 100,
            "purchased_perks": [{"name": "Fashion", "cost": 100}],
            "evidence_quotes": [
                {"text": "first", "mention_chapter_num": "2", "mention_word_position": 10},
                {"text": "second", "mention_chapter_num": "2", "mention_word_position": 20},
            ],
        },
        ">",
    )

    assert "hit QQ" in line


def test_roll_stat_line_notes_later_chapter_evidence_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "roll_number": 27,
            "outcome": "miss",
            "constellation": None,
            "available_cp": 200,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mention_chapter_num": "2",
            "mention_word_position": 24,
            "display_position_policy": "mechanical",
            "display_chapter_num": "1",
            "display_word_position": 20,
            "evidence_quotes": [
                {
                    "text": "a few failed connections",
                    "mention_chapter_num": "2",
                    "mention_word_position": 24,
                },
            ],
        },
        " ",
    )

    assert "narrative in ch 2" in line
    assert "display at predicted roll position" in line


def test_roll_stat_line_notes_prior_chapter_evidence_as_source_location(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "roll_number": 44,
            "outcome": "miss",
            "constellation": "Size",
            "available_cp": 100,
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 20,
            "mention_chapter_num": "1",
            "mention_word_position": 24,
            "display_position_policy": "mechanical",
            "display_chapter_num": "2",
            "display_word_position": 20,
            "evidence_quotes": [
                {
                    "text": "ignored the Celestial Forge as it missed a connection",
                    "mention_chapter_num": "1",
                    "mention_word_position": 24,
                },
            ],
        },
        " ",
    )

    assert "narrative evidence from ch 1" in line
    assert "narrative in ch 1" not in line
    assert "display at predicted roll position" in line


def test_roll_stat_line_notes_unchanged_quote_marker_stays_predicted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "roll_number": 34,
            "outcome": "hit",
            "constellation": "Magitech",
            "available_cp": 200,
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 20,
            "mention_chapter_num": "2",
            "mention_word_position": None,
            "display_position_policy": "mechanical",
            "display_chapter_num": "2",
            "display_word_position": 20,
            "purchased_perks": [{"name": "Mechanist", "cost": 100}],
            "evidence_quotes": [
                {
                    "text": "The final constellation was called Magitech.",
                    "mention_chapter_num": "2",
                    "mention_word_position": 24,
                },
            ],
        },
        " ",
    )

    assert "display at predicted roll position" in line


def test_roll_stat_line_uses_stable_target_index_when_display_order_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 4,
            "target_roll_index": 3,
            "roll_ordinal": 19,
            "roll_label": "R19",
            "outcome": "hit",
            "constellation": "Magic",
            "available_cp": 200,
            "purchased_perks": [{"name": "Magic: Enchanting", "cost": 200}],
            "evidence_quotes": [
                {
                    "text": "quote",
                    "mention_chapter_num": "2",
                    "mention_word_position": 24,
                },
            ],
        },
        " ",
    )

    assert "# 3 (R19)" in line


def test_roll_stat_line_shows_roll_predicted_and_source_ordinals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "target_roll_index": 1,
            "roll_ordinal": 48,
            "roll_label": "R48",
            "predicted_ordinal": 53,
            "predicted_label": "P53",
            "source_ordinal": 48,
            "source_label": "S48",
            "outcome": "miss",
            "constellation": "Magic",
            "available_cp": 100,
            "rolled_perk_cost": 200,
            "evidence_quotes": [
                {
                    "text": "The Celestial Forge missed a connection",
                    "mention_chapter_num": "13",
                    "mention_word_position": 599,
                },
            ],
        },
        " ",
    )
    predicted_line = app._format_roll_stat_line(
        {
            "display_kind": "predicted_slot",
            "target_roll_index": 5,
            "predicted_ordinal": 48,
            "predicted_label": "P48",
            "outcome": "open",
            "word_position": 9631,
        },
        " ",
    )

    assert "# 1 (R48/P53/S48)" in line
    assert "# 5 predicted (P48)" in predicted_line


def test_roll_stat_line_labels_cross_chapter_targets_with_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "target_chapter_num": "1",
            "target_roll_index": 2,
            "roll_ordinal": 15,
            "roll_label": "R15",
            "source_ordinal": 15,
            "source_label": "S15",
            "outcome": "hit",
            "constellation": "Vehicles",
            "available_cp": 100,
            "purchased_perks": [
                {"name": "Aerospace Engineering Makes Things Go Fast", "cost": 100}
            ],
            "evidence_quotes": [
                {
                    "text": "The Vehicles constellation swung towards me",
                    "mention_chapter_num": "2",
                    "mention_word_position": 24,
                },
            ],
        },
        " ",
    )

    assert "ch 1 # 2 (R15/S15)" in line


def test_miss_possible_suffix_counts_all_outstanding_perks_at_or_above_miss_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    app.data._outstanding_doc = {
        "chapters": [
            {
                "chapter_num": "1",
                "before_chapter": {
                    "by_constellation": {
                        "Magic": [
                            {"name": "Cheap Fixture", "cost": 200},
                            {"name": "Exact Fixture", "cost": 400},
                            {"name": "Higher Fixture", "cost": 600},
                        ]
                    }
                },
            }
        ]
    }

    line = app._format_roll_stat_line(
        {
            "index": 1,
            "roll_number": 7,
            "outcome": "miss",
            "constellation": "Magic",
            "available_cp": 300,
            "miss_cost_estimate": 400,
            "mechanical_chapter_num": "1",
        },
        " ",
    )

    assert "missed >= 400 CP (2 possible)" in line


def test_roll_stat_line_does_not_render_future_narrative_status_for_predicted_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")

    line = app._format_roll_stat_line(
        {
            "display_kind": "predicted_slot",
            "target_roll_index": 2,
            "target_chapter_num": "2",
            "mention_chapter_num": "3",
            "mention_word_position": None,
            "evidence_quotes": [],
            "roll_number": 3,
            "word_position": 40,
            "outcome": "open",
        },
        " ",
    )

    assert "predicted" in line
    assert "narrative" not in line
    assert "at CP 40" in line


def test_skipped_slots_source_markers_status_and_click_targets_use_stats_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    app.persistence.mark_roll_skipped("2", 2)

    skipped = next(
        roll for roll in app._open_predicted_slot_rolls(cs)
        if roll["target_roll_index"] == 2
    )
    source_line = app._format_roll_stat_line(
        {
            "index": 1,
            "target_roll_index": 1,
            "roll_number": 2,
            "source": "curator_rolls",
            "source_kind": "roll",
            "outcome": "miss",
            "evidence_quotes": [
                {"text": "first"},
                {"text": "second"},
            ],
        },
        " ",
    )
    app._last_curation_message = "fixture status"
    text, stats = _render_stats_text(app)

    assert skipped["skipped"] is True
    assert "skipped" in app._format_roll_stat_line(skipped, " ")
    assert "SQQ" in source_line
    assert "fixture status" in text

    target_line = next(
        line for line, target in stats._roll_line_targets.items()
        if target.get("display_kind") == "predicted_slot"
        and target.get("target_roll_index") == 2
    )
    stats.on_click(type("Mouse", (), {"y": target_line, "button": 1, "stop": lambda self: None})())

    selected = app._selected_roll_target_if_visible()
    assert selected is not None
    assert selected["display_kind"] == "predicted_slot"
    assert selected["target_roll_index"] == 2

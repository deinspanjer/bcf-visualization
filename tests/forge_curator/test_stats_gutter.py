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
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    app.persistence.append_roll_evidence_at_indices(
        "1",
        [1],
        text="chapter2 forge motes",
        mention_chapter_num="2",
        mention_word_position=0,
    )

    assert [mark for mark in app._compute_gutter_marks() if mark.glyph == "Q"] == []


def test_deferred_quote_highlights_in_mention_chapter_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    quote = "chapter2 forge motes"
    app.persistence.append_roll_evidence_at_indices(
        "1",
        [1],
        text=quote,
        mention_chapter_num="2",
        mention_word_position=0,
    )

    text = app.state.chapter.prose.text
    start = text.find(quote)

    assert start >= 0
    assert (start, start + len(quote)) in app._roll_evidence_char_spans(app.state.chapter)


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
            target["roll_number"],
            target["outcome"],
        )
        for target in targets
    ] == [
        ("chapter_roll", 1, 2, "miss"),
        ("predicted_slot", 2, 3, "open"),
    ]


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


def test_stats_registers_deferred_predicted_slot_before_current_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")

    text, stats = _render_stats_text(app)
    targets = list(stats._roll_line_targets.values())

    assert "Deferred rolls" in text
    assert targets[0]["display_kind"] == "deferred_in"
    assert targets[0]["source_kind"] == "predicted_slot"
    assert targets[0]["target_chapter_num"] == "1"
    assert targets[0]["target_roll_index"] == 1
    assert [target["display_kind"] for target in targets[1:]] == [
        "chapter_roll",
        "predicted_slot",
    ]


def test_stats_groups_source_deferred_projection_with_deferred_rolls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    source_projected = dict(cs.derived.roll_facts[0])
    source_projected.update(
        {
            "chapter_num": "1",
            "roll_sequence_in_chapter": 2,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "1",
            "display_word_position": 20,
            "display_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_roll_index": 1,
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]

    text, stats = _render_stats_text(app)
    targets = list(stats._roll_line_targets.values())

    assert "Deferred rolls" in text
    assert "deferred from ch 1 #2 source" in text
    assert targets[0]["display_kind"] == "source_deferred"
    assert targets[0]["target_chapter_num"] == "1"
    assert targets[0]["target_roll_index"] == 2
    assert all(
        target.get("display_kind") != "source_deferred"
        for target in targets[1:]
    )


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


def test_roll_stat_line_notes_later_chapter_evidence_as_deferred(
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

    assert "narrative deferred to ch 2" in line
    assert "display at predicted roll position" in line


def test_roll_stat_line_notes_prior_chapter_evidence_without_deferral_label(
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
    assert "narrative deferred to ch 1" not in line
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
            "roll_number": 19,
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

    assert "# 3 (19)" in line


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


def test_roll_stat_line_labels_locationless_predicted_deferral_as_future(
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

    assert "deferred to future chapter" in line
    assert "deferred to ch 3" not in line
    assert "at CP" not in line


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

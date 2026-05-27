from __future__ import annotations

from scripts.forge_curator.data_loader import _compute_word_offsets
from scripts.forge_curator.miss_quote_matcher import find_miss_quote_candidates


def test_miss_quote_matcher_selects_sentence_sized_constellation_miss() -> None:
    text = (
        "The conversation continued for a while. "
        "The Size constellation passed by without a connection. "
        "Then everyone got back to work."
    )
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Size",
        anchor_word_index=4,
    )

    assert candidates
    assert candidates[0].text == "The Size constellation passed by without a connection."
    assert candidates[0].word_index == 6
    assert "constellation" in candidates[0].reason_tags
    assert "miss_language" in candidates[0].reason_tags


def test_miss_quote_matcher_allows_adjacent_sentence_context_when_split() -> None:
    text = (
        "The Forge shifted again. "
        "The Knowledge constellation drifted near. "
        "No connection formed before it moved on."
    )
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Knowledge",
        anchor_word_index=0,
    )

    assert candidates
    assert candidates[0].text == (
        "The Knowledge constellation drifted near. "
        "No connection formed before it moved on."
    )


def test_miss_quote_matcher_ranks_target_constellation_above_distractor() -> None:
    text = (
        "The Magic constellation missed a connection. "
        "The Time constellation missed a connection."
    )
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Time",
        anchor_word_index=0,
    )

    assert candidates[0].text == "The Time constellation missed a connection."


def test_miss_quote_matcher_trims_leading_unrelated_clause() -> None:
    text = "The second duplicate quipped as the Clothing constellation missed a connection."
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Clothing",
        anchor_word_index=0,
    )

    assert candidates[0].text == "the Clothing constellation missed a connection"
    assert [variant.label for variant in candidates[0].variants] == ["focused", "sentence"]
    assert candidates[0].variants[1].text == text


def test_miss_quote_matcher_keeps_full_sentence_when_forge_failure_clause_is_related() -> None:
    text = "The Time constellation moved by as the Celestial Forge failed to secure a connection."
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Time",
        anchor_word_index=0,
    )

    assert candidates[0].text == text


def test_miss_quote_matcher_focuses_short_forge_name_miss_clause() -> None:
    text = (
        "Skidmark started to turn to Trickster as the Forge missed a connection "
        "to the Size constellation, but the cape jumped in."
    )
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Size",
        anchor_word_index=0,
    )

    assert candidates[0].text == "the Forge missed a connection to the Size constellation"


def test_miss_quote_matcher_trims_trailing_unrelated_clause() -> None:
    text = (
        "Somewhat appropriately, the Celestial Forge missed a connection "
        "to the Alchemy constellation as I reviewed Tetra's progress."
    )
    word_offsets = _compute_word_offsets(text)

    candidates = find_miss_quote_candidates(
        text,
        word_offsets,
        constellation="Alchemy",
        anchor_word_index=0,
    )

    assert candidates[0].text == (
        "the Celestial Forge missed a connection to the Alchemy constellation"
    )

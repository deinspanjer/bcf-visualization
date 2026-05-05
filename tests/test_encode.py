"""Tests for nlp/encode.py — BIO conversion edge cases.

Skips the entire module if `transformers` is not installed so the iMac
can run the test suite without a GPU stack.
"""

from __future__ import annotations

import pytest

transformers = pytest.importorskip("transformers", reason="transformers not installed")

from transformers import AutoTokenizer  # noqa: E402

from nlp.encode import (  # noqa: E402
    LABEL2ID_A,
    LABEL2ID_B,
    EncodedExample,
    encode_passage,
)
from nlp.schema import SpanAnnotation, SpanRecord  # noqa: E402

_TOKENIZER_NAME = "hf-internal-testing/tiny-random-bert"

@pytest.fixture(scope="module")
def tok():
    return AutoTokenizer.from_pretrained(_TOKENIZER_NAME)


def _record(text: str, spans: list[dict]) -> SpanRecord:
    return SpanRecord(
        passage_id="test_p",
        chapter_num="1",
        section_index=0,
        epub_char_start=0,
        epub_char_end=len(text),
        text=text,
        spans=[SpanAnnotation(**s) for s in spans],
        source="manual",
        annotator="test",
        annotated_at="2026-05-05T00:00:00Z",
        schema_version=1,
    )


def _bio_ids(example: EncodedExample, layer: str) -> list[int]:
    return (
        example.labels_layer_a if layer == "A" else example.labels_layer_b
    )


def _non_special(example: EncodedExample) -> list[tuple[int, int]]:
    """Return (layer_a_id, layer_b_id) for non-special token positions."""
    result = []
    for a, b in zip(example.labels_layer_a, example.labels_layer_b):
        if a != -100:
            result.append((a, b))
    return result


# ---------------------------------------------------------------------------
# Test 1: Span exactly on a word boundary
# ---------------------------------------------------------------------------

def test_span_on_word_boundary(tok):
    text = "Joe gained Perfect Pitch today"
    # "Joe" is [0,3)
    spans = [{"layer": "B", "start": 0, "end": 3, "label": "JOE_NAME"}]
    record = _record(text, spans)
    examples = encode_passage(record, tok)
    assert len(examples) == 1
    ex = examples[0]
    ids = ex.labels_layer_b

    b_joe = LABEL2ID_B["B-JOE_NAME"]
    i_joe = LABEL2ID_B["I-JOE_NAME"]
    o = LABEL2ID_B["O"]

    # Filter out -100 positions
    non_special = [(i, v) for i, v in enumerate(ids) if v != -100]
    # First non-special token should be B-JOE_NAME
    assert non_special[0][1] == b_joe, f"Expected B-JOE_NAME at first token, got {non_special[0]}"
    # No I-JOE_NAME since 'Joe' is one token
    for _, v in non_special[1:]:
        assert v != i_joe, "Unexpected I-JOE_NAME beyond first token"


# ---------------------------------------------------------------------------
# Test 2: Span starting mid-token (rounds to enclosing token)
# ---------------------------------------------------------------------------

def test_span_midtoken_rounding(tok):
    # Tokenize and find a word that becomes one token, then offset by 1 char
    text = "gained Perfect Pitch"
    # "Perfect" starts at char 7 — offset the span by 1 to land mid-word
    # The tokenizer will produce a token for "Perfect"; start=8 (mid-token)
    # should still round to include the enclosing token.
    spans = [{"layer": "B", "start": 8, "end": 14, "label": "PERK_NAME"}]
    record = _record(text, spans)
    examples = encode_passage(record, tok)
    assert len(examples) == 1
    ex = examples[0]
    ids = ex.labels_layer_b

    b_perk = LABEL2ID_B["B-PERK_NAME"]
    i_perk = LABEL2ID_B["I-PERK_NAME"]

    non_special_vals = [v for v in ids if v != -100]
    # At least one B or I perk tag should appear
    assert any(v in (b_perk, i_perk) for v in non_special_vals), (
        f"Expected PERK_NAME tag for mid-token span; got {non_special_vals}"
    )


# ---------------------------------------------------------------------------
# Test 3: Two same-layer spans in one passage
# ---------------------------------------------------------------------------

def test_two_spans_same_layer(tok):
    text = "Joe gained Perfect Pitch and then Iron Lung."
    spans = [
        {"layer": "B", "start": 14, "end": 26, "label": "PERK_NAME"},  # Perfect Pitch
        {"layer": "B", "start": 34, "end": 43, "label": "PERK_NAME"},  # Iron Lung
    ]
    record = _record(text, spans)
    examples = encode_passage(record, tok)
    assert len(examples) == 1
    ex = examples[0]
    ids = ex.labels_layer_b

    b_perk = LABEL2ID_B["B-PERK_NAME"]
    non_special_vals = [v for v in ids if v != -100]
    b_count = non_special_vals.count(b_perk)
    assert b_count == 2, f"Expected 2 B-PERK_NAME tags, got {b_count}: {non_special_vals}"


# ---------------------------------------------------------------------------
# Test 4: Layer-A and layer-B overlap (PERK_NAME inside ACQUISITION)
# ---------------------------------------------------------------------------

def test_layer_a_b_overlap(tok):
    text = "Joe gained Perfect Pitch today."
    # ACQUISITION spans "gained Perfect Pitch" [4,24)
    # PERK_NAME spans "Perfect Pitch" [11,24)
    spans = [
        {"layer": "A", "start": 4, "end": 24, "label": "ACQUISITION"},
        {"layer": "B", "start": 11, "end": 24, "label": "PERK_NAME"},
    ]
    record = _record(text, spans)
    examples = encode_passage(record, tok)
    assert len(examples) == 1
    ex = examples[0]

    b_acq = LABEL2ID_A["B-ACQUISITION"]
    b_perk = LABEL2ID_B["B-PERK_NAME"]

    layer_a_vals = [v for v in ex.labels_layer_a if v != -100]
    layer_b_vals = [v for v in ex.labels_layer_b if v != -100]

    assert b_acq in layer_a_vals, "Expected B-ACQUISITION in layer A"
    assert b_perk in layer_b_vals, "Expected B-PERK_NAME in layer B"


# ---------------------------------------------------------------------------
# Test 5: Span longer than entire window raises ValueError
# ---------------------------------------------------------------------------

def test_span_longer_than_window_raises(tok):
    # Use a short max_length so the span can exceed the window
    text = "Joe gained Perfect Pitch as the wheel clicked into place and kept on spinning forever."
    # span covers the entire text — with a tiny max_length window it will be wider
    spans = [{"layer": "A", "start": 0, "end": len(text), "label": "ACQUISITION"}]
    record = _record(text, spans)
    with pytest.raises(ValueError, match="wider than the entire window"):
        encode_passage(record, tok, max_length=16, stride=4)


# ---------------------------------------------------------------------------
# Test 6: Long passage forces windowing → multiple EncodedExamples
# ---------------------------------------------------------------------------

def test_long_passage_windowing(tok):
    # Build a passage that is long enough to trigger windowing at max_length=32
    words = ["token"] * 60
    text = " ".join(words)
    spans = []  # no spans needed for this test
    record = _record(text, spans)
    examples = encode_passage(record, tok, max_length=32, stride=8)
    assert len(examples) > 1, (
        f"Expected multiple windows for a long passage; got {len(examples)}"
    )
    for i, ex in enumerate(examples):
        assert ex.window_index == i
        assert ex.passage_id == "test_p"
        # All non-special tokens should have O (0) since no spans
        for v in ex.labels_layer_a:
            assert v in (-100, 0), f"Unexpected layer_a value {v} in window {i}"


# ---------------------------------------------------------------------------
# Bonus: Fixture files validate against SpanRecord schema
# ---------------------------------------------------------------------------

def test_fixture_span_records_valid():
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "tiny_spans.jsonl"
    assert fixture.exists(), f"Fixture not found: {fixture}"
    records = []
    for line in fixture.read_text().splitlines():
        if line.strip():
            records.append(SpanRecord.model_validate(json.loads(line)))
    assert len(records) == 5


def test_fixture_section_records_valid():
    import json
    from pathlib import Path

    from nlp.schema import SectionRecord

    fixture = Path(__file__).parent / "fixtures" / "tiny_sections.jsonl"
    assert fixture.exists(), f"Fixture not found: {fixture}"
    records = []
    for line in fixture.read_text().splitlines():
        if line.strip():
            records.append(SectionRecord.model_validate(json.loads(line)))
    assert len(records) == 5

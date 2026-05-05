"""Char-span to token-BIO encoder for the BCF span model.

Pure-function core: `encode_passage` and `encode_dataset`.

`datasets` is imported lazily inside `encode_dataset` so that
`import nlp.encode` works without the `datasets` package installed
(needed for iMac-only checks). All other imports are standard-library
or pydantic, which are always available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

from .schema import (
    LAYER_A_BIO,
    LAYER_B_BIO,
    SCHEMA_VERSION,
    SpanRecord,
)

if TYPE_CHECKING:
    pass  # keep mypy happy; tokenizer is duck-typed at runtime

log = logging.getLogger(__name__)

# BIO label → integer id maps (built once at module import)
LABEL2ID_A: dict[str, int] = {tag: i for i, tag in enumerate(LAYER_A_BIO)}
LABEL2ID_B: dict[str, int] = {tag: i for i, tag in enumerate(LAYER_B_BIO)}
ID2LABEL_A: dict[int, str] = {i: tag for tag, i in LABEL2ID_A.items()}
ID2LABEL_B: dict[int, str] = {i: tag for tag, i in LABEL2ID_B.items()}

_IGNORE_ID = -100  # PyTorch cross-entropy ignore index for special tokens


@dataclass
class EncodedExample:
    input_ids: list[int]
    attention_mask: list[int]
    labels_layer_a: list[int]   # BIO ids; -100 for special tokens
    labels_layer_b: list[int]
    passage_id: str
    window_index: int           # 0 if not windowed
    span_drop_count: int        # spans straddling the window boundary


def _project_spans(
    offsets: list[tuple[int, int]],
    layer_spans: list[tuple[int, int, str]],
    label2id: dict[str, int],
    text_len: int,
) -> tuple[list[int], int]:
    """Project char spans onto token BIO ids for one layer.

    Returns (bio_ids, drop_count).

    Each token gets:
    - `_IGNORE_ID` if its offset is (0, 0) and it is a special token
      (CLS/SEP/PAD).
    - `LABEL2ID["O"]` (i.e. 0) if it falls outside every span.
    - `LABEL2ID["B-X"]` for the first token inside span X.
    - `LABEL2ID["I-X"]` for subsequent tokens inside span X.

    "Inside span" means token_start >= span_start and token_end <= span_end
    (after rounding mid-token starts to the enclosing token's start).

    Spans partially overlapping the window (i.e. partially outside [0, text_len))
    are skipped and counted in drop_count.

    A span whose width exceeds text_len is treated as spanning the entire window,
    which means it is partially outside — we raise ValueError for that case.
    """
    n = len(offsets)
    bio = [0] * n  # default O
    drop_count = 0

    # Mark special tokens as -100
    for i, (ts, te) in enumerate(offsets):
        if ts == 0 and te == 0:
            bio[i] = _IGNORE_ID

    for span_start, span_end, label in layer_spans:
        # Validate span fits within text
        if span_end - span_start > text_len:
            raise ValueError(
                f"Span [{span_start}, {span_end}) is wider than the entire "
                f"window text ({text_len} chars). This span cannot be encoded."
            )

        # Find the real text boundaries for this window.
        # offsets of non-special tokens give us the window's char range.
        real_offsets = [(ts, te) for ts, te in offsets if not (ts == 0 and te == 0)]
        if not real_offsets:
            break
        win_start = real_offsets[0][0]
        win_end = real_offsets[-1][1]

        # Span fully outside window → skip silently
        if span_end <= win_start or span_start >= win_end:
            continue

        # Span partially outside window → drop + count
        if span_start < win_start or span_end > win_end:
            drop_count += 1
            log.debug(
                "Dropped span [%d, %d) %r: straddles window boundary [%d, %d)",
                span_start, span_end, label, win_start, win_end,
            )
            continue

        b_tag = f"B-{label}"
        i_tag = f"I-{label}"
        if b_tag not in label2id or i_tag not in label2id:
            log.warning("Unknown label %r; skipping span.", label)
            continue

        b_id = label2id[b_tag]
        i_id = label2id[i_tag]

        first = True
        for idx, (ts, te) in enumerate(offsets):
            if ts == 0 and te == 0:
                continue  # special token
            # Token overlaps span: token_start < span_end and token_end > span_start
            if ts < span_end and te > span_start:
                if first:
                    bio[idx] = b_id
                    first = False
                else:
                    bio[idx] = i_id

    return bio, drop_count


def encode_passage(
    record: SpanRecord,
    tokenizer: Any,
    *,
    max_length: int = 4096,
    stride: int = 256,
) -> list[EncodedExample]:
    """Encode one SpanRecord into one or more EncodedExamples (windows).

    Uses `tokenizer(return_offsets_mapping=True, return_overflowing_tokens=True)`
    so long passages are automatically windowed with `stride`.

    Each span that straddles a window boundary is dropped from that window
    only and counted in `span_drop_count` (a debug metric; not an error).

    A span whose character width exceeds `max_length` characters (roughly)
    cannot fit in any window and raises `ValueError`.
    """
    if record.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"Record {record.passage_id!r} has schema_version "
            f"{record.schema_version}, expected {SCHEMA_VERSION}."
        )

    text = record.text
    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        max_length=max_length,
        truncation=True,
        stride=stride,
        return_overflowing_tokens=True,
        padding=False,
    )

    # When there is no overflow `overflow_to_sample_mapping` may be absent.
    num_windows = len(encoding["input_ids"])

    # Separate spans by layer
    spans_a: list[tuple[int, int, str]] = []
    spans_b: list[tuple[int, int, str]] = []
    for sp in record.spans:
        if sp.layer == "A":
            spans_a.append((sp.start, sp.end, sp.label))
        else:
            spans_b.append((sp.start, sp.end, sp.label))

    examples: list[EncodedExample] = []
    total_drop = 0

    for w in range(num_windows):
        input_ids: list[int] = encoding["input_ids"][w]
        attention_mask: list[int] = encoding["attention_mask"][w]
        offsets: list[tuple[int, int]] = encoding["offset_mapping"][w]

        # Real text length covered by this window
        real_offsets = [(ts, te) for ts, te in offsets if not (ts == 0 and te == 0)]
        win_text_len = (real_offsets[-1][1] - real_offsets[0][0]) if real_offsets else 0

        bio_a, drop_a = _project_spans(offsets, spans_a, LABEL2ID_A, win_text_len)
        bio_b, drop_b = _project_spans(offsets, spans_b, LABEL2ID_B, win_text_len)
        window_drop = drop_a + drop_b
        total_drop += window_drop

        if window_drop:
            log.info(
                "passage %r window %d: dropped %d span(s) straddling boundary",
                record.passage_id, w, window_drop,
            )

        examples.append(EncodedExample(
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels_layer_a=bio_a,
            labels_layer_b=bio_b,
            passage_id=record.passage_id,
            window_index=w,
            span_drop_count=window_drop,
        ))

    return examples


def encode_dataset(
    records: Iterable[SpanRecord],
    tokenizer: Any,
    **kwargs: Any,
) -> "datasets.Dataset":  # type: ignore[name-defined]
    """Encode an iterable of SpanRecords into a `datasets.Dataset`.

    The `datasets` library is imported lazily so that `import nlp.encode`
    works without it installed.
    """
    import datasets as _datasets  # lazy import

    rows: list[dict[str, Any]] = []
    for record in records:
        for ex in encode_passage(record, tokenizer, **kwargs):
            rows.append({
                "input_ids": ex.input_ids,
                "attention_mask": ex.attention_mask,
                "labels_layer_a": ex.labels_layer_a,
                "labels_layer_b": ex.labels_layer_b,
                "passage_id": ex.passage_id,
                "window_index": ex.window_index,
                "span_drop_count": ex.span_drop_count,
            })

    return _datasets.Dataset.from_list(rows)


__all__ = [
    "EncodedExample",
    "encode_passage",
    "encode_dataset",
    "LABEL2ID_A",
    "LABEL2ID_B",
    "ID2LABEL_A",
    "ID2LABEL_B",
]

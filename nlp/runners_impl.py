"""Real SpanRunner and SectionRunner implementations.

These replace the placeholder stubs in nlp/runners.py post-merge.
Both load from a checkpoint directory and run inference.

Import-safe: importing this module does NOT require torch or transformers
to be installed and does NOT require any checkpoint to exist. Errors are
deferred to `__init__` (FileNotFoundError if the checkpoint is missing)
or to `run` (if the model load failed for another reason).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import (
    LAYER_A_BIO,
    LAYER_B_BIO,
    SCHEMA_VERSION,
    SECTION_LABELS,
    ClassifySectionRequest,
    ClassifySectionResponse,
    ExtractRequest,
    ExtractResponse,
    ExtractResult,
    SectionClassification,
    SectionLabelScore,
    Span,
)


def _require_checkpoint(path: Path, name: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{name} checkpoint not found at {path!r}. "
            "Train the model first with nlp/train_span.py (or train_section.py) "
            "and point --version to a completed run."
        )


def _lazy_import_torch():
    try:
        import torch
        import torch.nn.functional as F
        return torch, F
    except ImportError as e:
        raise RuntimeError(
            "torch is not installed. Install it with: pip install -e '.[gpu]'"
        ) from e


def _lazy_import_transformers():
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        return AutoTokenizer, AutoModelForSequenceClassification
    except ImportError as e:
        raise RuntimeError(
            "transformers is not installed. Install it with: pip install -e '.[gpu]'"
        ) from e


# ---------------------------------------------------------------------------
# BIO collapse helper
# ---------------------------------------------------------------------------


def _collapse_bio_to_spans(
    token_tags: list[str],
    offsets: list[tuple[int, int]],
    scores: list[float],
    layer: str,
) -> list[Span]:
    """Convert per-token BIO tags + offset map into character-level Span objects.

    `offsets` is the tokenizer offset_mapping (may include (0,0) for special tokens).
    `scores` is per-token softmax-max probability.
    """
    spans: list[Span] = []
    in_span = False
    span_label = ""
    span_start = 0
    span_end = 0
    span_score_sum = 0.0
    span_token_count = 0

    for tag, (ts, te), score in zip(token_tags, offsets, scores):
        if ts == 0 and te == 0:
            # Special token — close any open span
            if in_span:
                spans.append(Span(
                    layer=layer,
                    label=span_label,
                    start=span_start,
                    end=span_end,
                    score=round(span_score_sum / max(span_token_count, 1), 4),
                ))
                in_span = False
            continue

        if tag.startswith("B-"):
            if in_span:
                spans.append(Span(
                    layer=layer,
                    label=span_label,
                    start=span_start,
                    end=span_end,
                    score=round(span_score_sum / max(span_token_count, 1), 4),
                ))
            span_label = tag[2:]
            span_start = ts
            span_end = te
            span_score_sum = score
            span_token_count = 1
            in_span = True
        elif tag.startswith("I-") and in_span and tag[2:] == span_label:
            span_end = te
            span_score_sum += score
            span_token_count += 1
        else:
            if in_span:
                spans.append(Span(
                    layer=layer,
                    label=span_label,
                    start=span_start,
                    end=span_end,
                    score=round(span_score_sum / max(span_token_count, 1), 4),
                ))
                in_span = False

    if in_span:
        spans.append(Span(
            layer=layer,
            label=span_label,
            start=span_start,
            end=span_end,
            score=round(span_score_sum / max(span_token_count, 1), 4),
        ))

    return spans


# ---------------------------------------------------------------------------
# SpanRunner
# ---------------------------------------------------------------------------


class SpanRunner:
    """Two-head token classifier runner for POST /extract.

    Loads from a checkpoint directory created by train_span.py.
    Raises FileNotFoundError on __init__ if the checkpoint is absent.
    Raises RuntimeError if torch/transformers are not installed.
    """

    def __init__(self, checkpoint_path: Path) -> None:
        _require_checkpoint(checkpoint_path, "span")
        torch, _ = _lazy_import_torch()
        AutoTokenizer, _ = _lazy_import_transformers()

        from .train_span import TwoHeadConfig, TwoHeadTokenClassifier

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_path))
        self.model = TwoHeadTokenClassifier.from_pretrained(str(checkpoint_path))
        self.model.to(self.device)
        self.model.eval()

        # Load label maps from checkpoint artifacts if present
        id2label_a_path = checkpoint_path / "id2label_a.json"
        id2label_b_path = checkpoint_path / "id2label_b.json"
        if id2label_a_path.exists():
            with id2label_a_path.open() as f:
                raw = json.load(f)
            self.id2label_a = {int(k): v for k, v in raw.items()}
        else:
            from .encode import ID2LABEL_A
            self.id2label_a = ID2LABEL_A

        if id2label_b_path.exists():
            with id2label_b_path.open() as f:
                raw = json.load(f)
            self.id2label_b = {int(k): v for k, v in raw.items()}
        else:
            from .encode import ID2LABEL_B
            self.id2label_b = ID2LABEL_B

        self._model_version = checkpoint_path.name

    def run(self, request: ExtractRequest) -> ExtractResponse:
        import torch
        import torch.nn.functional as F

        results: list[ExtractResult] = []

        for passage in request.passages:
            text = passage.text[: request.max_passage_chars]
            encoding = self.tokenizer(
                text,
                return_offsets_mapping=True,
                truncation=True,
                max_length=4096,
                stride=256,
                return_overflowing_tokens=True,
                padding=False,
                return_tensors=None,
            )
            num_windows = len(encoding["input_ids"])

            # Collect per-window predictions then merge (last-window-wins for overlapping tokens)
            # Map from char position → (tag_a, tag_b, score_a, score_b)
            char_a: dict[int, tuple[str, float]] = {}
            char_b: dict[int, tuple[str, float]] = {}

            for w in range(num_windows):
                input_ids = torch.tensor(
                    [encoding["input_ids"][w]], device=self.device
                )
                attn = torch.tensor(
                    [encoding["attention_mask"][w]], device=self.device
                )
                offsets: list[tuple[int, int]] = encoding["offset_mapping"][w]

                with torch.no_grad():
                    out = self.model(input_ids=input_ids, attention_mask=attn)

                logits_a, logits_b = out.logits
                probs_a = F.softmax(logits_a[0], dim=-1).cpu().numpy()
                probs_b = F.softmax(logits_b[0], dim=-1).cpu().numpy()

                for i, (ts, te) in enumerate(offsets):
                    if ts == 0 and te == 0:
                        continue
                    tag_a = self.id2label_a.get(int(probs_a[i].argmax()), "O")
                    tag_b = self.id2label_b.get(int(probs_b[i].argmax()), "O")
                    score_a = float(probs_a[i].max())
                    score_b = float(probs_b[i].max())
                    char_a[ts] = (tag_a, score_a)
                    char_b[ts] = (tag_b, score_b)

            # Reconstruct ordered sequences
            sorted_chars = sorted(char_a.keys())
            tags_a = [char_a[c][0] for c in sorted_chars]
            tags_b = [char_b.get(c, ("O", 1.0))[0] for c in sorted_chars]
            scores_a = [char_a[c][1] for c in sorted_chars]
            scores_b = [char_b.get(c, ("O", 1.0))[1] for c in sorted_chars]
            fake_offsets = [(c, c + 1) for c in sorted_chars]

            all_spans: list[Span] = []
            if request.include_layer_a:
                spans_a = _collapse_bio_to_spans(tags_a, fake_offsets, scores_a, "A")
                all_spans.extend(
                    s for s in spans_a if (s.score or 0) >= request.min_score
                )
            if request.include_layer_b:
                spans_b = _collapse_bio_to_spans(tags_b, fake_offsets, scores_b, "B")
                all_spans.extend(
                    s for s in spans_b if (s.score or 0) >= request.min_score
                )

            results.append(ExtractResult(
                passage_id=passage.passage_id,
                spans=all_spans,
                windows_used=num_windows,
            ))

        return ExtractResponse(
            model_version=self._model_version,
            schema_version=SCHEMA_VERSION,
            results=results,
        )


# ---------------------------------------------------------------------------
# SectionRunner
# ---------------------------------------------------------------------------


def _sigmoid_np(x):
    import numpy as np
    return 1.0 / (1.0 + np.exp(-x))


class SectionRunner:
    """Multi-label section classifier runner for POST /classify_section.

    Loads from a checkpoint directory created by train_section.py.
    Raises FileNotFoundError on __init__ if the checkpoint is absent.
    Raises RuntimeError if torch/transformers are not installed.
    """

    def __init__(self, checkpoint_path: Path) -> None:
        _require_checkpoint(checkpoint_path, "section")
        torch, _ = _lazy_import_torch()
        AutoTokenizer, AutoModelForSequenceClassification = _lazy_import_transformers()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_path))
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(checkpoint_path)
        )
        self.model.to(self.device)
        self.model.eval()

        id2label_path = checkpoint_path / "id2label.json"
        if id2label_path.exists():
            with id2label_path.open() as f:
                raw = json.load(f)
            self.id2label = {int(k): v for k, v in raw.items()}
        else:
            self.id2label = {i: lbl for i, lbl in enumerate(SECTION_LABELS)}

        self._model_version = checkpoint_path.name

    def run(self, request: ClassifySectionRequest) -> ClassifySectionResponse:
        import torch

        results: list[SectionClassification] = []

        for section in request.sections:
            encoding = self.tokenizer(
                section.text,
                max_length=min(4096, self.tokenizer.model_max_length),
                truncation=True,
                padding="max_length",
                return_tensors="pt",
            )
            input_ids = encoding["input_ids"].to(self.device)
            attn = encoding["attention_mask"].to(self.device)

            with torch.no_grad():
                logits = self.model(input_ids=input_ids, attention_mask=attn).logits

            probs = _sigmoid_np(logits[0].cpu().numpy())
            threshold = request.threshold

            labels: dict[str, SectionLabelScore] = {}
            for i, lbl in self.id2label.items():
                score = float(probs[i])
                labels[lbl] = SectionLabelScore(value=score >= threshold, score=score)

            results.append(SectionClassification(
                chapter_num=section.chapter_num,
                section_index=section.section_index,
                labels=labels,
            ))

        return ClassifySectionResponse(
            model_version=self._model_version,
            schema_version=SCHEMA_VERSION,
            results=results,
        )


__all__ = ["SpanRunner", "SectionRunner"]

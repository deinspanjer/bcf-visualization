"""Label catalogs and pydantic models for the BCF NLP package.

This module is the contract every other agent (bootstrap, TUI, training,
serving, client) imports from. It depends only on the standard library
and pydantic v2 — no torch, transformers, or fastapi — so it can be
imported on the iMac without a GPU stack.

See `docs/local_nlp_label_schema.md` for the authoritative label
definitions and JSONL schemas, and `docs/local_nlp_serving.md` for the
endpoint request/response shapes mirrored here.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: int = 2

# Layer A: event spans (mechanic-relevant moments). See label schema doc.
LAYER_A_LABELS: list[str] = [
    "ROLL_HIT",
    "ROLL_MISS",
]

# Layer B: entity / reference spans. See label schema doc.
# `PERK_REFERENCE` is listed first because it is expected to be the most
# frequently-fired layer-B label in pilot data.
LAYER_B_LABELS: list[str] = [
    "PERK_REFERENCE",
    # Sibling of PERK_REFERENCE for constellation names in narrative
    # prose. Mirrors the perk-reference rationale: constellation names
    # mentioned in body prose tag where Joe is consciously aware of
    # the constellation, and frequently co-occur with ROLL_MISS spans
    # (the canonical miss frame is "the <X> constellation passed by").
    # Out of scope: end-of-chapter catalog and structured summary blocks.
    "CONSTELLATION_REFERENCE",
    "PRESENCE_ACTION",
    "DATE_REF",
    "TIME_OF_DAY",
    "DURATION",
    "FLASHBACK_CUE",
    "DILATION_CUE",
    # Structural exclusion marker — used to flag prose regions that should
    # NOT count toward CP-eligible word totals. Author's notes are the
    # canonical case (e.g. "(Author's note: ... )" blocks embedded in a
    # chapter that's otherwise Joe-POV CP-eligible). Downstream consumers
    # like predict_rolls.py can filter spans by this label to subtract
    # the words from cumulative CP counts.
    "AUTHOR_NOTE",
]

# Multi-label section flags (independent sigmoids). See label schema doc.
SECTION_LABELS: list[str] = [
    "pov_joe",
    "joe_on_screen",
    "joe_mentioned_offscreen",
    "time_real",
    "time_flashback",
    "time_framing",
    "time_dilated",
    "counts_for_cp",
]


def bio_tags(labels: list[str]) -> list[str]:
    """Return the BIO tag set for the given label list.

    The output starts with ``"O"`` followed by ``"B-<label>"``,
    ``"I-<label>"`` pairs in the same order as the input. Used by both
    training heads and by the runner BIO-collapse logic.
    """
    out: list[str] = ["O"]
    for label in labels:
        out.append(f"B-{label}")
        out.append(f"I-{label}")
    return out


LAYER_A_BIO: list[str] = bio_tags(LAYER_A_LABELS)
LAYER_B_BIO: list[str] = bio_tags(LAYER_B_LABELS)


# Type aliases used inside pydantic models. Literal-typed fields give
# every consumer of these models free validation against the catalog.
LayerName = Literal["A", "B"]
LayerALabel = Literal[
    "ROLL_HIT",
    "ROLL_MISS",
]
LayerBLabel = Literal[
    "PERK_REFERENCE",
    "CONSTELLATION_REFERENCE",
    "PRESENCE_ACTION",
    "DATE_REF",
    "TIME_OF_DAY",
    "DURATION",
    "FLASHBACK_CUE",
    "DILATION_CUE",
    "AUTHOR_NOTE",
]
SectionLabelName = Literal[
    "pov_joe",
    "joe_on_screen",
    "joe_mentioned_offscreen",
    "time_real",
    "time_flashback",
    "time_framing",
    "time_dilated",
    "counts_for_cp",
]
SourceKind = Literal[
    "llm_proposal_reviewed",
    "llm_proposal_unreviewed",
    "manual",
    "corrected",
    "imported",
]


class _Base(BaseModel):
    """Common pydantic config: forbid unknown fields by default elsewhere
    we explicitly relax it. Allow population by alias / by name."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# --- /extract --------------------------------------------------------------


class Span(_Base):
    """A single labeled span within a passage.

    `start` / `end` are character offsets into the passage text, end
    exclusive (Python slice semantics).
    """

    layer: LayerName
    label: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    text: Optional[str] = None


class PassageInput(_Base):
    """One passage in an `/extract` request."""

    passage_id: str
    text: str = Field(min_length=1)


class ExtractRequest(_Base):
    passages: list[PassageInput] = Field(min_length=1)
    min_score: float = Field(default=0.5, ge=0.0, le=1.0)
    include_layer_a: bool = True
    include_layer_b: bool = True
    max_passage_chars: int = Field(default=16000, gt=0)


class ExtractResult(_Base):
    passage_id: str
    spans: list[Span] = Field(default_factory=list)
    windows_used: int = 1
    warnings: list[str] = Field(default_factory=list)


class ExtractResponse(_Base):
    model_version: str
    schema_version: int
    results: list[ExtractResult]


# --- /classify_section ----------------------------------------------------


class SectionInput(_Base):
    chapter_num: str
    section_index: int = Field(ge=0)
    header: Optional[str] = None
    text: str = Field(min_length=1)


class ClassifySectionRequest(_Base):
    sections: list[SectionInput] = Field(min_length=1)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class SectionLabelScore(_Base):
    value: bool
    score: float = Field(ge=0.0, le=1.0)


class SectionClassification(_Base):
    chapter_num: str
    section_index: int
    labels: dict[str, SectionLabelScore]


class ClassifySectionResponse(_Base):
    model_version: str
    schema_version: int
    results: list[SectionClassification]


# --- /health, /version ---------------------------------------------------


class ModelHealth(_Base):
    loaded: bool
    version: Optional[str] = None
    path: Optional[str] = None


class GpuHealth(_Base):
    available: bool
    name: Optional[str] = None
    vram_total_mb: Optional[int] = None
    vram_free_mb: Optional[int] = None


class HealthResponse(_Base):
    status: str
    models: dict[str, ModelHealth]
    gpu: GpuHealth


class ModelVersion(_Base):
    version: Optional[str] = None
    trained_at: Optional[str] = None
    metrics_path: Optional[str] = None


class VersionResponse(_Base):
    service_version: str
    git_commit: str
    schema_version: int
    started_at: str
    models: dict[str, ModelVersion]


# --- Dataset record schemas (data/labeled/*.jsonl) -----------------------


class SpanAnnotation(_Base):
    """A span as written to JSONL training data.

    Distinct from `Span` because training records use a stricter shape
    (no `score`, no `text`) per `docs/local_nlp_label_schema.md`.
    """

    layer: LayerName
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    label: str


class SpanRecord(_Base):
    """One line of `data/labeled/spans/*.jsonl`."""

    passage_id: str
    chapter_num: str
    section_index: int = Field(ge=0)
    epub_char_start: int = Field(ge=0)
    epub_char_end: int = Field(ge=0)
    text: str
    spans: list[SpanAnnotation] = Field(default_factory=list)
    source: SourceKind
    model_proposal_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    annotator: str
    annotated_at: str
    notes: str = ""
    schema_version: int = SCHEMA_VERSION


class SectionRecord(_Base):
    """One line of `data/labeled/sections/*.jsonl`."""

    chapter_num: str
    section_index: int = Field(ge=0)
    header: str
    first_chars: str
    word_count: int = Field(ge=0)
    labels: dict[str, bool]
    annotator: str
    annotated_at: str
    schema_version: int = SCHEMA_VERSION


__all__ = [
    "SCHEMA_VERSION",
    "LAYER_A_LABELS",
    "LAYER_B_LABELS",
    "SECTION_LABELS",
    "LAYER_A_BIO",
    "LAYER_B_BIO",
    "bio_tags",
    "Span",
    "PassageInput",
    "ExtractRequest",
    "ExtractResult",
    "ExtractResponse",
    "SectionInput",
    "ClassifySectionRequest",
    "SectionLabelScore",
    "SectionClassification",
    "ClassifySectionResponse",
    "ModelHealth",
    "GpuHealth",
    "HealthResponse",
    "ModelVersion",
    "VersionResponse",
    "SpanAnnotation",
    "SpanRecord",
    "SectionRecord",
]

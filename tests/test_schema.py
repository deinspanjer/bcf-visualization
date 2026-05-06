"""Pydantic-model and label-catalog tests for `nlp.schema`.

Exercises the request/response shapes from `docs/local_nlp_serving.md`
and the JSONL record schemas from `docs/local_nlp_label_schema.md`.
"""

from __future__ import annotations

from nlp import schema as S


# --- BIO catalogs ---------------------------------------------------------


def test_layer_a_bio_matches_doc():
    expected = [
        "O",
        "B-ROLL_HIT", "I-ROLL_HIT",
        "B-ROLL_MISS", "I-ROLL_MISS",
    ]
    assert S.LAYER_A_BIO == expected
    assert S.bio_tags(S.LAYER_A_LABELS) == expected


def test_layer_b_bio_matches_doc():
    expected = [
        "O",
        "B-PERK_REFERENCE", "I-PERK_REFERENCE",
        "B-CONSTELLATION_REFERENCE", "I-CONSTELLATION_REFERENCE",
        "B-PRESENCE_ACTION", "I-PRESENCE_ACTION",
        "B-DATE_REF", "I-DATE_REF",
        "B-TIME_OF_DAY", "I-TIME_OF_DAY",
        "B-DURATION", "I-DURATION",
        "B-FLASHBACK_CUE", "I-FLASHBACK_CUE",
        "B-DILATION_CUE", "I-DILATION_CUE",
        "B-AUTHOR_NOTE", "I-AUTHOR_NOTE",
    ]
    assert S.LAYER_B_BIO == expected
    assert S.bio_tags(S.LAYER_B_LABELS) == expected


def test_section_labels_catalog():
    assert S.SECTION_LABELS == [
        "pov_joe",
        "joe_on_screen",
        "joe_mentioned_offscreen",
        "time_real",
        "time_flashback",
        "time_framing",
        "time_dilated",
        "counts_for_cp",
    ]


def test_schema_version():
    assert S.SCHEMA_VERSION == 2


def test_layer_b_includes_perk_reference_first():
    """`PERK_REFERENCE` is the lead Layer-B label per the v3 doc bump."""
    assert S.LAYER_B_LABELS[0] == "PERK_REFERENCE"
    # All previously-shipped layer-B labels still present.
    for old in (
        "PRESENCE_ACTION",
        "DATE_REF",
        "TIME_OF_DAY",
        "DURATION",
        "FLASHBACK_CUE",
        "DILATION_CUE",
    ):
        assert old in S.LAYER_B_LABELS


def test_v1_record_loads_with_default_notes():
    """A SpanRecord written under schema v1 (no `notes` field) must still
    validate against the v3 model, with `notes` defaulting to ``""``."""
    v1_payload = {
        "passage_id": "ch16.1_p07",
        "chapter_num": "16.1",
        "section_index": 0,
        "epub_char_start": 482311,
        "epub_char_end": 482729,
        "text": "Brockton focused on the wheel...",
        "spans": [
            {"layer": "A", "start": 95, "end": 119, "label": "ROLL_HIT"},
        ],
        "source": "manual",
        "annotator": "deinspanjer",
        "annotated_at": "2026-05-04T15:32:11Z",
        "schema_version": 1,
    }
    rec = S.SpanRecord.model_validate(v1_payload)
    assert rec.notes == ""
    # The record's own schema_version is preserved as written; the model
    # default only applies when the field is absent. Backward-compat is
    # about adding the optional `notes` field, not rewriting old ones.
    assert rec.schema_version == 1


def test_v2_record_with_notes():
    """A v2 record carrying a `notes` value round-trips intact and a
    PERK_REFERENCE span is accepted on Layer B."""
    v2_payload = {
        "passage_id": "ch40_p03",
        "chapter_num": "40",
        "section_index": 0,
        "epub_char_start": 0,
        "epub_char_end": 200,
        "text": "the new power was called Mixing Mixtures and felt strange.",
        "spans": [
            {"layer": "B", "start": 25, "end": 40, "label": "PERK_REFERENCE"},
        ],
        "source": "manual",
        "annotator": "deinspanjer",
        "annotated_at": "2026-05-05T10:00:00Z",
        "notes": "boundary check: included full perk name without 'the'",
        "schema_version": 2,
    }
    rec = S.SpanRecord.model_validate(v2_payload)
    assert rec.notes.startswith("boundary check")
    assert rec.spans[0].label == "PERK_REFERENCE"
    dumped = rec.model_dump(mode="json")
    assert dumped["notes"] == v2_payload["notes"]
    assert dumped["schema_version"] == 2


# --- /extract request/response -------------------------------------------


def test_extract_request_accepts_doc_example():
    req = S.ExtractRequest.model_validate(
        {
            "passages": [
                {
                    "passage_id": "ch12_p07",
                    "text": "Brockton focused on the wheel...",
                }
            ],
            "min_score": 0.5,
            "include_layer_a": True,
            "include_layer_b": True,
            "max_passage_chars": 16000,
        }
    )
    assert req.passages[0].passage_id == "ch12_p07"
    assert req.min_score == 0.5


def test_extract_response_accepts_doc_example():
    resp = S.ExtractResponse.model_validate(
        {
            "model_version": "span/v1",
            "schema_version": 1,
            "results": [
                {
                    "passage_id": "ch12_p07",
                    "spans": [
                        {"layer": "A", "label": "ACQUISITION", "start": 95, "end": 119, "score": 0.93, "text": "gained Perfect Pitch"},
                        {"layer": "B", "label": "PERK_NAME", "start": 102, "end": 114, "score": 0.97, "text": "Perfect Pitch"},
                    ],
                    "windows_used": 1,
                    "warnings": [],
                }
            ],
        }
    )
    assert resp.results[0].spans[1].label == "PERK_NAME"
    assert resp.results[0].spans[0].layer == "A"


# --- /classify_section request/response ----------------------------------


def test_classify_section_request_accepts_doc_example():
    req = S.ClassifySectionRequest.model_validate(
        {
            "sections": [
                {
                    "chapter_num": "16.1",
                    "section_index": 0,
                    "header": "16.1 Interlude Weld",
                    "text": "Weld looked over the bay...",
                }
            ],
            "threshold": 0.5,
        }
    )
    assert req.sections[0].chapter_num == "16.1"


def test_classify_section_response_accepts_doc_example():
    resp = S.ClassifySectionResponse.model_validate(
        {
            "model_version": "section/v1",
            "schema_version": 1,
            "results": [
                {
                    "chapter_num": "16.1",
                    "section_index": 0,
                    "labels": {
                        "pov_joe": {"value": False, "score": 0.04},
                        "joe_on_screen": {"value": False, "score": 0.07},
                        "joe_mentioned_offscreen": {"value": True, "score": 0.81},
                        "time_real": {"value": True, "score": 0.93},
                        "time_flashback": {"value": False, "score": 0.02},
                        "time_framing": {"value": False, "score": 0.05},
                        "time_dilated": {"value": False, "score": 0.01},
                        "counts_for_cp": {"value": False, "score": 0.06},
                    },
                }
            ],
        }
    )
    labels = resp.results[0].labels
    assert labels["joe_mentioned_offscreen"].value is True
    assert labels["time_real"].score == 0.93


# --- health / version -----------------------------------------------------


def test_health_response_accepts_doc_example():
    resp = S.HealthResponse.model_validate(
        {
            "status": "ok",
            "models": {
                "span":    {"loaded": True,  "version": "span/v1",    "path": "checkpoints/span/v1/best"},
                "section": {"loaded": False, "version": None,         "path": "checkpoints/section/v1/best"},
                "embed":   {"loaded": False, "version": None,         "path": None},
            },
            "gpu": {"available": True, "name": "NVIDIA X", "vram_total_mb": 12288, "vram_free_mb": 10240},
        }
    )
    assert resp.models["span"].loaded is True
    assert resp.gpu.vram_total_mb == 12288


def test_version_response_accepts_doc_example():
    resp = S.VersionResponse.model_validate(
        {
            "service_version": "0.1.0",
            "git_commit": "abc1234",
            "schema_version": 1,
            "started_at": "2026-05-04T15:00:00Z",
            "models": {
                "span":    {"version": "span/v1",    "trained_at": "2026-05-04T13:30:00Z", "metrics_path": "checkpoints/span/v1/metrics_final.json"},
                "section": {"version": "section/v1", "trained_at": "2026-05-04T14:00:00Z", "metrics_path": "checkpoints/section/v1/metrics_final.json"},
            },
        }
    )
    assert resp.git_commit == "abc1234"
    assert resp.models["span"].trained_at.startswith("2026")


# --- JSONL records --------------------------------------------------------


def test_span_record_round_trip_doc_example():
    payload = {
        "passage_id": "ch16.1_p07",
        "chapter_num": "16.1",
        "section_index": 0,
        "epub_char_start": 482311,
        "epub_char_end": 482729,
        "text": "Brockton focused on the wheel...",
        "spans": [
            {"layer": "A", "start": 95, "end": 119, "label": "ACQUISITION"},
            {"layer": "B", "start": 102, "end": 114, "label": "PERK_NAME"},
        ],
        "source": "llm_proposal_reviewed",
        "model_proposal_score": 0.81,
        "annotator": "deinspanjer",
        "annotated_at": "2026-05-04T15:32:11Z",
        "schema_version": 1,
    }
    rec = S.SpanRecord.model_validate(payload)
    dumped = rec.model_dump(mode="json")
    # Round-trip preserves every doc-listed field.
    for key in payload:
        assert dumped[key] == payload[key], key


def test_section_record_accepts_doc_example():
    payload = {
        "chapter_num": "16.1",
        "section_index": 0,
        "header": "16.1 Interlude Weld",
        "first_chars": "Weld looked over the bay...",
        "word_count": 1843,
        "labels": {
            "pov_joe": False,
            "joe_on_screen": False,
            "joe_mentioned_offscreen": True,
            "time_real": True,
            "time_flashback": False,
            "time_framing": False,
            "time_dilated": False,
            "counts_for_cp": False,
        },
        "annotator": "deinspanjer",
        "annotated_at": "2026-05-04T15:32:11Z",
        "schema_version": 1,
    }
    rec = S.SectionRecord.model_validate(payload)
    assert rec.labels["joe_mentioned_offscreen"] is True

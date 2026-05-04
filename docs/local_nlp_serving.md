# Serving + integration

_The FastAPI server (Windows box), its endpoints, and how iMac-side
scripts consume them. Pair with `docs/local_nlp_setup.md`._

## Service shape

One FastAPI process, hosting both fine-tuned models behind two
endpoints. Optional embedding model on a third endpoint or a separate
TEI process.

```
:8000  POST /extract            span model
       POST /classify_section   section classifier
       POST /embed              embeddings (if loaded)
       GET  /health
       GET  /version
```

Single process keeps VRAM bookkeeping simple; both fine-tuned models
together are < 1.5 GB. If contention with llama.cpp's GGUF model
becomes an issue, split across processes or pin them to different
GPUs.

## Process model

- Synchronous request handling. Both models use a single inference
  worker; there is no batching across requests in v1. Per-request
  batching across passages within a single payload is supported.
- Models load lazily on the first request, not at process start
  (avoids slow boot when the operator is iterating on serving code).
  `/health` reports `loaded: bool` per model so callers can warm
  them with a no-op request.
- Graceful shutdown: SIGINT/SIGTERM finishes in-flight requests, then
  unloads.

## Endpoint specs

### `POST /extract`

Token classification over passage text. Returns a list of spans per
passage.

Request:

```json
{
  "passages": [
    {
      "passage_id": "ch12_p07",
      "text": "Brockton focused on the wheel..."
    }
  ],
  "min_score": 0.5,
  "include_layer_a": true,
  "include_layer_b": true,
  "max_passage_chars": 16000
}
```

- `passages` — required, length 1+. `passage_id` is echoed back.
- `min_score` — drop spans below this softmax probability. Default
  `0.5`.
- `include_layer_a`, `include_layer_b` — let callers ask for one
  layer only. Default both.
- `max_passage_chars` — guardrail; passages longer than this get
  windowed server-side with stride 512 tokens.

Response:

```json
{
  "model_version": "span/v1",
  "schema_version": 1,
  "results": [
    {
      "passage_id": "ch12_p07",
      "spans": [
        {"layer": "A", "label": "ACQUISITION", "start": 95,  "end": 119, "score": 0.93, "text": "gained Perfect Pitch"},
        {"layer": "B", "label": "PERK_NAME",   "start": 102, "end": 114, "score": 0.97, "text": "Perfect Pitch"}
      ],
      "windows_used": 1,
      "warnings": []
    }
  ]
}
```

Errors:

- `400` if a passage is missing `text` or has zero-length text.
- `503` with body `{"error":"span_model_not_loaded"}` if the
  checkpoint isn't available.

### `POST /classify_section`

Multi-label section classification.

Request:

```json
{
  "sections": [
    {
      "chapter_num": "16.1",
      "section_index": 0,
      "header": "16.1 Interlude Weld",
      "text": "Weld looked over the bay..."
    }
  ],
  "threshold": 0.5
}
```

Response:

```json
{
  "model_version": "section/v1",
  "schema_version": 1,
  "results": [
    {
      "chapter_num": "16.1",
      "section_index": 0,
      "labels": {
        "pov_joe":               {"value": false, "score": 0.04},
        "joe_on_screen":         {"value": false, "score": 0.07},
        "joe_mentioned_offscreen": {"value": true, "score": 0.81},
        "time_real":             {"value": true,  "score": 0.93},
        "time_flashback":        {"value": false, "score": 0.02},
        "time_framing":          {"value": false, "score": 0.05},
        "time_dilated":          {"value": false, "score": 0.01},
        "counts_for_cp":         {"value": false, "score": 0.06}
      }
    }
  ]
}
```

`value` is the boolean after thresholding; `score` is the raw
sigmoid output for downstream confidence work.

### `POST /embed` (optional)

Standard sentence-embedding API. Only present if an embedding model
is configured via `BCF_EMBED_MODEL`.

Request:

```json
{
  "texts": ["passage 1", "passage 2"],
  "normalize": true
}
```

Response:

```json
{
  "model_version": "BAAI/bge-base-en-v1.5",
  "dim": 768,
  "vectors": [[...], [...]]
}
```

### `GET /health`

```json
{
  "status": "ok",
  "models": {
    "span":    {"loaded": true,  "version": "span/v1",    "path": "checkpoints/span/v1/best"},
    "section": {"loaded": false, "version": null,         "path": "checkpoints/section/v1/best"},
    "embed":   {"loaded": false, "version": null,         "path": null}
  },
  "gpu": {"available": true, "name": "NVIDIA ...", "vram_total_mb": 12288, "vram_free_mb": 10240}
}
```

### `GET /version`

```json
{
  "service_version": "0.1.0",
  "git_commit": "abc1234",
  "schema_version": 1,
  "started_at": "2026-05-04T15:00:00Z",
  "models": {
    "span":    {"version": "span/v1",    "trained_at": "2026-05-04T13:30:00Z", "metrics_path": "checkpoints/span/v1/metrics_final.json"},
    "section": {"version": "section/v1", "trained_at": "2026-05-04T14:00:00Z", "metrics_path": "checkpoints/section/v1/metrics_final.json"}
  }
}
```

## Server implementation outline

`nlp/serve.py` skeleton (illustrative — actual implementation in a
later pass):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .schema import (
    ExtractRequest, ExtractResponse,
    ClassifySectionRequest, ClassifySectionResponse,
    SCHEMA_VERSION,
)
import os, torch, time
from transformers import AutoTokenizer

SPAN_PATH    = os.environ.get("BCF_SPAN_MODEL_PATH",    "checkpoints/span/v1/best")
SECTION_PATH = os.environ.get("BCF_SECTION_MODEL_PATH", "checkpoints/section/v1/best")
EMBED_MODEL  = os.environ.get("BCF_EMBED_MODEL")  # optional

state = {"span": None, "section": None, "embed": None, "started_at": None}

@asynccontextmanager
async def lifespan(app):
    state["started_at"] = time.time()
    yield

app = FastAPI(lifespan=lifespan)

def _load_span():
    if state["span"] is None:
        state["span"] = SpanRunner(SPAN_PATH)
    return state["span"]

@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest):
    runner = _load_span()
    return runner.run(req)

@app.post("/classify_section", response_model=ClassifySectionResponse)
def classify(req: ClassifySectionRequest):
    runner = _load_section()
    return runner.run(req)

@app.get("/health")
def health(): ...

@app.get("/version")
def version(): ...
```

`SpanRunner` and `SectionRunner` wrap the trained model; they handle
windowing, per-batch inference, score thresholding, and BIO-to-span
collapsing. They share a `_load_backbone_tokenizer` helper.

## Concurrency and batching

- v1: one inference worker per model. `uvicorn --workers 1`. Adding
  workers doubles VRAM cost; not worth it for this workload.
- Within one request, passages are batched up to a model-specific
  cap (default 16 for the span model; 32 for the section classifier).
- Long passages get split into windows and batched together; spans
  are merged at response time.

## Auth and network

LAN-only by default. No auth in v1. Document to operator that:

- The service must not be exposed beyond the LAN (no port forward).
- If a multi-user shared install becomes a need, add a fixed bearer
  token in `BCF_NLP_TOKEN` and require it on every endpoint. Do not
  invent a more sophisticated scheme.

The Windows Defender Firewall rule should restrict inbound TCP 8000
to the local subnet.

## Client library (`nlp/client.py`)

A thin wrapper used by iMac-side scripts. Not imported on the Windows
box.

```python
import os, httpx
from typing import Iterable, Sequence

class BcfNlpClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0):
        self.base_url = base_url or os.environ.get(
            "BCF_NLP_URL", "http://localhost:8000"
        )
        self._client = httpx.Client(timeout=timeout)

    def health(self) -> dict:
        return self._client.get(f"{self.base_url}/health").raise_for_status().json()

    def extract(self, passages: Sequence[dict], **kwargs) -> dict:
        body = {"passages": list(passages), **kwargs}
        r = self._client.post(f"{self.base_url}/extract", json=body)
        r.raise_for_status()
        return r.json()

    def classify_sections(self, sections: Sequence[dict], **kwargs) -> dict:
        body = {"sections": list(sections), **kwargs}
        r = self._client.post(f"{self.base_url}/classify_section", json=body)
        r.raise_for_status()
        return r.json()
```

Existing scripts adopt it in small steps; see "Integration plan"
below.

## Integration plan

The new pipeline scripts plug into the existing chain after
`extract_chapter_sections.py`. Order and hand-offs:

```
extract_chapter_sections.py        (existing, EPUB → sections JSON)
├─ build_section_classifications.py
│   ├─ existing rule-based pass     (still primary)
│   └─ NEW: optional ML refinement  (calls /classify_section)
│
├─ NEW: extract_chapter_events.py   (calls /extract over each section)
│       writes data/derived/extracted_events.json
│
├─ NEW: extract_chapter_dates.py    (consumes extracted_events.json)
│       writes data/derived/chapter_dates.json
│
build_perk_directory.py             (existing; gains an optional ML-link path)
predict_rolls.py                    (unchanged)
find_roll_locations.py              (becomes fallback only)
find_text_backed_rolls.py           (becomes fallback only)
validate_roll_locations.py          (unchanged; runs on either path's output)
build_chapter_facts.py              (existing; reads new derived files)
spot_check.py                       (existing; gains ML-vs-rule comparison)
```

### `extract_chapter_events.py` (new)

Reads `chapter_sections.json` + the EPUB. For each MC section (or
optionally every section), windows the prose into 1–3 paragraph
chunks, calls `/extract`, persists results.

Output: `data/derived/extracted_events.json` matching a schema in
`data/derived/_schemas/`. Roughly:

```json
{
  "model_version": "span/v1",
  "extracted_at": "...",
  "events": [
    {
      "chapter_num": "12",
      "section_index": 0,
      "passage_id": "ch12_p07",
      "epub_char_start": 482311,
      "epub_char_end": 482729,
      "spans": [{"layer": "A", "label": "ACQUISITION", "start": ..., "end": ..., "score": ..., "text": "..."}]
    }
  ]
}
```

### `extract_chapter_dates.py` (new)

Consumes `extracted_events.json`'s `DATE_REF` / `TIME_OF_DAY` /
`DURATION` / `FLASHBACK_CUE` / `DILATION_CUE` spans. Resolves them
against chapter ordering (using the timeline anchors in
`data/derived/timeline.json` for backstory and `chapters.json` for
chapter dates) and writes a per-chapter best-guess in-world date.

This is the "feed candidates into the LLM for reasoning" step from
the original conversation: the script can call llama.cpp on `:11434`
when a passage has multiple competing date cues, with a tightly
scoped prompt and the candidate spans pre-extracted.

Output: `data/derived/chapter_dates.json` plus a confidence field per
chapter. Resolves a long-standing TODO item.

### `build_section_classifications.py` (modified)

Add an optional ML pass after the existing rule pass:

- Run rules first (current code).
- For sections marked `medium` or `low` confidence, optionally call
  `/classify_section` and overlay its results.
- Disagreements between rules and ML are written to
  `data/manual/section_classifications_ml_diff.json` for manual
  review; the rule answer wins until the diff is reviewed.

The ML pass is gated by `--use-ml` (default off until the section
classifier hits acceptance).

### `build_perk_directory.py` (modified)

Currently does fuzzy matching against the curator's catalog. Add an
optional pass that uses ML-extracted `PERK_NAME` spans as additional
input — useful for the 31 perks acquired in rolls without a catalog
entry that `spot_check.py` flags.

### `spot_check.py` (modified)

Add ML-vs-rule comparison sections:

- ML acquisition counts per chapter vs `obtained_perks.json`.
- Sections where rules and ML classifier disagree.

## Failure modes and fallbacks

The pipeline should remain functional if the FastAPI server is down.

- `extract_chapter_events.py` retries with exponential backoff. After
  3 failures, exits with a clear error and does *not* overwrite the
  existing `extracted_events.json`.
- `build_section_classifications.py --use-ml` falls back to rule-only
  output if `/classify_section` is unreachable, with a logged
  warning.
- `build_chapter_facts.py` reads whichever of `roll_text_evidence.json`
  or `extracted_events.json` is present. Both available → ML wins.
  Only one available → use it. Neither → error.

## Versioning and provenance

Every record produced by an ML lane carries:

- The model version (`span/v1`, `section/v1`).
- The model checkpoint path.
- The schema version.
- The timestamp.

These live in the top-level metadata of each derived JSON file (not
on every span). Re-running with a new checkpoint produces a fresh file
with the new version stamp; the old one is overwritten unless the
operator manually copies it for diffing.

`spot_check.py` reads the metadata and warns if the `chapter_facts.json`
backbone was built from outputs of *different* model versions (which
would mean a partial regen).

## Out-of-scope for v1

- Streaming responses (SSE).
- WebSocket inference.
- Multi-tenant auth.
- Hot-swapping checkpoints without restart. Restart the service;
  uvicorn reload handles it.
- A web UI. The TUI plus the existing visualization is enough.

## Operational checklist

Before declaring v1 production:

- [ ] `uv run uvicorn nlp.serve:app` starts cleanly.
- [ ] `/health` returns `loaded: true` after a warm-up call.
- [ ] `/extract` round-trips a single passage matching a known
      labeled example.
- [ ] `/classify_section` round-trips a known section.
- [ ] `nlp/client.py` test from the iMac round-trips against the
      Windows box over LAN.
- [ ] `extract_chapter_events.py` regenerates `extracted_events.json`
      end-to-end without errors.
- [ ] `spot_check.py` shows ML vs rule diff under a reasonable
      threshold (≤ 5% chapter-level acquisition-count disagreement).
- [ ] `start-server.ps1` (or NSSM service) survives a reboot.

# Requirements: Autonomous Curation (workstream: curation)

**Defined:** 2026-07-25 (split from combined REQUIREMENTS.md on 2026-07-26)
**Core Value:** Agent-curated data must never silently degrade the hand-curated evidence corpus.

## v1 Requirements

Requirements for this workstream. Each maps to curation-workstream phases (renumbered from the original combined roadmap: old 5–8 → new 1–4).

### Epub Refresh (hard gate)

- [x] **EPUB-01**: Latest released chapters fetched via the existing private-source flow (`sync_private_source_repo.py` → `hydrate_source_epub.py`); chapter count and nav entries reflect the newest release
- [x] **EPUB-02**: Full pipeline re-run completes green on the refreshed epub: predicted rolls extend into new chapters, existing curated chapters still validate, and `visualization_facts.json` rebuilds (with one documented, deliberate exception: ch 104's alignment anchor is held pending Dre's manual curator-TUI review — see `01-02-SUMMARY.md`/`deferred-items.md`; `scripts/verify.py` does not fully exit 0 due to that plus pre-existing, unrelated Track B test debt, tracked as a known-accepted gap, not silently closed)

### Curation Infrastructure

- [x] **CINF-01**: Roll-override schema gains the `curated_by: "human" | "agent"` provenance marker (shape decided at the mobile-ux Phase 1 interview, D-04), with every in-repo consumer rewritten in the same change (derive_roll_facts, TUI, validators) — no shims
- [x] **CINF-02**: Exemplar corpus mined from the hand-curated chapters, tagged by CP regime, with retrieval constrained to same-regime chapters
- [x] **CINF-03**: Mechanical verifier validates agent output using existing primitives only (exact/whitespace-normalized quote match, pipeline tokenizer word positions, perk-name resolver ladder) and is baselined against known-good hand-curated chapters before any LLM output touches it
- [ ] **CINF-04**: Agent runs are idempotent (keyed by chapter + corpus fingerprint via the agent-run ledger) and never overwrite an existing hand-curated chapter entry

### Agent Curation

- [x] **ACUR-01**: Per-chapter curation runs as two sequenced passes. **Stage 1 (deterministic, zero LLM)** assembles candidate roll objects from the existing `roll_text_evidence.json` anchor/prose-window chain plus `obtained_perks.json`'s paid-then-free bundle ordering, including a liberal forward search for each free perk's name or substring; it reuses that machinery rather than reimplementing prose scanning. **Stage 2 (inference)** refines and grades Stage 1's candidates and recovers what heuristics cannot (`forward_ref` / `no_evidence` classes, retrospective phrasing, obliquely-named misses). Word positions and roll ordinals are always derived mechanically, never emitted by the LLM
- [ ] **ACUR-02**: Confidence gate combines mechanical verification signals (Phase 2's verifier) with model self-report (tiebreaker only) and is tuned empirically against held-out hand-curated chapters, with a regime-boundary sensitivity check. Stage 1 is separately baselined against the hand-curated corpus before Stage 2 is built — that measurement is the gate for spending on inference
- [ ] **ACUR-03**: High-confidence curations write into `chapter_roll_overrides.json` with provenance; low-confidence curations write to a proposals sidecar in the same roll-object schema
- [ ] **ACUR-04**: Forge Curator TUI surfaces agent proposals for hand-curation of low-confidence chapters
- [ ] **ACUR-05**: Batch run over all remaining uncurated chapters completes with a per-chapter summary report (accepted / proposed / failed) and green pipeline validation afterward

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

- **CUR2-01**: Confidence/error dashboard across curation runs
- **CUR2-02**: Automated re-curation triggers when new epub versions revise old chapters

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-model ensemble voting / inter-annotator agreement metrics | Single ground-truth curator; no second annotator population |
| Dedicated annotation platform | Forge Curator TUI + proposals file covers review flow |
| Automated curation of low-confidence chapters | By design, Dre hand-curates those |
| New epub download path | Existing private-source sync flow is the only source |
| Fuzzy/similarity-scored quote acceptance | Exact-or-reject is the trust bar; word-level drift never fuzzy-accepted |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EPUB-01 | Phase 1 | Complete |
| EPUB-02 | Phase 1 | Complete (with documented gap — see 01-02-SUMMARY.md) |
| CINF-02 | Phase 1 | Complete |
| CINF-03 | Phase 2 | Complete |
| CINF-01 | Phase 3 | Complete |
| CINF-04 | Phase 4 | Pending |
| ACUR-01 | Phase 3 (Stage 1) + Phase 4 (Stage 2) | Stage 1 complete (03-02/03-03); Stage 2 pending |
| ACUR-02 | Phase 4 | Pending |
| ACUR-03 | Phase 4 | Pending |
| ACUR-04 | Phase 5 | Pending |
| ACUR-05 | Phase 5 | Pending |

**Coverage:**

- v1 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-25*
*Last updated: 2026-07-26 after workstream split*

# Phase 3: Provenance Schema & Deterministic Candidate Assembly - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Two deliverables, both zero-LLM:

1. **CINF-01 — provenance.** Every roll-override entry carries `curated_by: "human" | "agent"`, with every in-repo consumer rewritten in the same change. No shims, no aliases, no deprecation path.
2. **ACUR-01 Stage 1 — deterministic candidate assembly.** A pass that proposes candidate roll objects from machinery that already exists (`roll_text_evidence.json`'s anchors and prose windows, plus `obtained_perks.json`'s paid-then-free bundle ordering), and whose accuracy against the hand-curated corpus is **measured and recorded per evidence class**.

**Explicitly NOT in this phase** (Phase 4): any LLM call, the confidence gate, routing to overrides vs. proposals, and the agent-run ledger. Stage 1 emits candidates; it never writes to `chapter_roll_overrides.json`.

The measurement is the point. Phase 3's recorded accuracy is the evidence that sizes Phase 4's inference spend — building Stage 2 without it means guessing how much inference is worth buying.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked — do not re-litigate)

- **Provenance shape** (Workstream Gate 2, decided by Dre 2026-07-25): minimal marker, a single `curated_by` string per override entry, following the existing `curator_added` precedent. Run bookkeeping lives in a separate agent-run ledger — **that ledger is Phase 4's**, not this phase's.
- **`CURATION-CONVENTIONS.md`** is the domain contract for Stage 1. Read it in full before designing anything. It encodes bundle vs. multi-grab grouping, the four-beat hit-evidence shape, roll placement, miss handling, partial-evidence acceptability, and search posture.
- **Phase 2 D-13 search posture:** Stage 1 is deliberately liberal (over-produce, match variants and substrings); the mechanical verifier is exact-or-reject with no fuzzy path in existence. Never conflate the two tunings.
- **No parallel implementations:** Stage 1 consumes the existing anchor/prose-window chain. A second regex-anchor or prose-window implementation is a phase failure (success criterion 2).
- **Curation authority:** hand-curated data is authoritative and is never edited to make a metric look better.

### Provenance rollout (auto-resolved 2026-08-01)

- **D-01:** All 118 existing override entries are stamped `curated_by: "human"` as part of this change. The field is **required** on every entry, not optional-with-default — an absent value is a validation error, so a future agent-written entry cannot be mistaken for hand-curated by omission. This is the whole point of the marker.
- **D-02:** `curated_by` lives at the **chapter-entry** level, matching the decided shape and the existing `_fingerprint` / `model_validation_resolution` siblings — not per-roll. Phase 4 may need per-roll granularity when a chapter mixes hand and agent rolls; if so that is a *further* schema change under the same no-shims rule, and it is Phase 4's problem, not a speculative generalization now. — **Reversibility:** costly — widening to per-roll later means another full consumer rewrite (already flagged in Workstream Gate 2).
- **D-03:** Consumers to rewrite in the same change: `scripts/derive_roll_facts.py`, `scripts/build_chapter_facts.py`, the Forge Curator TUI (`scripts/forge_curator/`), and any validator/test asserting the override schema. The planner must enumerate them from the codebase rather than trusting this list — it is a starting point, not a contract.

### Stage 1 scope and output (auto-resolved 2026-08-01)

- **D-04:** Stage 1 writes a **candidates artifact** under `data/derived/`, built by a new `scripts/` script following the `build_*`/`derive_*` convention. It is a proposal surface, not trusted data. It does NOT write `chapter_roll_overrides.json` — that routing is Phase 4's, gated on confidence.
- **D-05:** Candidates use the **existing roll-object schema** (perks / outcome / constellation / word_position / mention_* / display_position_policy / evidence_quotes) so that Phase 4's routing and the Phase 5 TUI review need no translation layer. Each candidate additionally carries the provenance of its own derivation: which evidence class it came from, which anchors matched, and which fields were left unfilled.
- **D-06 (partial evidence is a first-class outcome):** Per `CURATION-CONVENTIONS.md` §5, a candidate Stage 1 cannot fully support is emitted **with the parts it is confident about and the rest explicitly marked evidence-not-found** — never guessed, never dropped, and never a failure. Ch 104's eight-perk Entrance Hall multi-grab is the worked example: capturing only the connection quote is a correct Stage 1 result.
- **D-07 (what Stage 1 is expected to actually do well):** measured over 718 predicted rolls — `forward_ref` 485 (68%), `direct` 132 (18%), `no_evidence` 74 (10%), `general_only` 27 (4%). Stage 1 should be expected to perform on the `direct` class and to *usefully narrow* the others, not to solve them. Do not tune Stage 1 toward the `forward_ref` majority by loosening its binding rules — that is precisely the work Phase 4's inference exists to do, and loosening here would manufacture false candidates that the verifier then has to reject.

### Measurement (auto-resolved 2026-08-01)

- **D-08:** Accuracy is measured against the hand-curated corpus **per evidence class**, not as a single headline number — a global figure would be dominated by `forward_ref` and would hide that Stage 1 works well where it should. Report, per class: how many curated rolls Stage 1 proposed a matching candidate for, how many candidates had no curated counterpart, and how many were partial (D-06).
- **D-09:** Compare against curated chapters only, and exclude the 11 stub chapters (`35.1, 55.1, 97, 100, 103, 104, 106, 109, 112, 114, 116.2`) from the accuracy denominator — they carry rolls with no evidence quotes and were not hand-curated, so scoring against them measures agreement with a generated stub rather than with Dre's judgment. Note ch 104 is now genuinely curated (2026-08-01) and may be included; the planner should re-derive the stub list from the data rather than hardcoding this one.
- **D-10:** The measurement is a committed artifact (a report, as in Phase 1's `corpus-analysis-report.md`), not just console output — Phase 4 reads it to size its own scope.

### Claude's Discretion

- Script and artifact names; whether assembly and measurement are one script or two
- The candidate object's exact extra fields for derivation provenance (beyond D-05's requirement that they exist)
- Matching methodology for "did Stage 1 propose a candidate for this curated roll" (position proximity, perk overlap, or both) — must be deterministic and documented
- Whether the candidates artifact is pipeline-wired and manifest-registered, or standalone like Phase 2's verifier report. Lean standalone: it is a proposal surface, and coupling it into the DAG drags candidate generation into every data regen.

### Known-accepted baseline (do NOT chase)

Full pytest has exactly 5 pre-existing failures — 4 in `tests/test_forge_curator.py`, 1 in `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`. `scripts/verify.py` exits 1 for that reason. Judge by "no NEW failures".

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain contract (read first)
- `.planning/workstreams/curation/CURATION-CONVENTIONS.md` — Dre's hand-curation practice; the behaviour Stage 1 must reproduce. §1 bundles, §2 evidence shape, §3 roll placement, §4 misses, §5 partial evidence, §6 search posture, §7 authority.
- `.planning/workstreams/curation/WOG-NOTES.md` — author word-of-god; the quote-less-roll convention.

### Workstream planning
- `.planning/workstreams/curation/ROADMAP.md` — Phase 3 goal and success criteria; the Stage-1/Stage-2 split rationale.
- `.planning/workstreams/curation/REQUIREMENTS.md` — CINF-01, ACUR-01 (Stage 1 half).
- `.planning/workstreams/curation/phases/02-mechanical-verifier/02-CONTEXT.md` — D-06(c) paid/free perk resolution, D-12 evidence spread, D-13 search posture. All three bind Stage 1.
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` — measured corpus shape: 57.6% of hit rolls are multi-grab, evidence-quote patterns, position-policy distribution.

### Code (primary sources)
- `scripts/find_roll_locations.py` — the Stage-1 regex anchor catalog. Its docstring states the two-stage design outright. Reuse; never reimplement.
- `scripts/find_text_backed_rolls.py` — produces `data/derived/roll_text_evidence.json`: per predicted roll, prose window, matching anchors, and `evidence_kind`. Stage 1's primary input.
- `scripts/mechanical_verifier.py` (Phase 2) — `verify_roll()` / `verify_chapter()`; the exact-or-reject bar candidates must eventually clear. Stage 1 may use it to self-check a candidate's quotes, but must not loosen it.
- `scripts/cp_word_index.py` (Phase 2) — the CP-earning-word tokenizer and prose loader.
- `scripts/perk_name_resolver.py` — the perk ladder; paid names only (cost-0 ride-alongs resolve via `obtained_perks.json`, per 02-CONTEXT D-06c).
- `data/derived/obtained_perks.json` — the acquired list, paid-perk-first bundle ordering; Stage 1's grouping signal.
- `data/manual/chapter_roll_overrides.json` (`_purpose` header) — the roll-object schema candidates must match, and the corpus accuracy is measured against.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `roll_text_evidence.json` (718 rows): `evidence_kind`, `prose_window`, `matching_events`, `matching_anchor_kinds`, `predicted_word_in_chapter`, `predicted_char_offset`. This is the candidate substrate — Stage 1 is largely a *binder* over it, not a new scanner.
- Phase 2's verifier and tokenizer give Stage 1 a way to self-check any quote it proposes before emitting it.
- Phase 1's `exemplar_index.json` + `query_exemplars.py` supply same-regime exemplars — relevant to Phase 4's prompting, and possibly to Stage 1 for deriving expected roll shape per regime.

### Established Patterns
- `build_*`/`derive_*` scripts: argparse + pure-function core + `SCHEMA_VERSION` + stdout summary; hard `raise` on shape violations. Tests import pure functions directly with synthetic fixtures.
- Derived artifacts land in `data/derived/`; manifest registration via `data_release.py` auto-discovery when pipeline-wired (Phase 1 D-03) — but Phase 2 deliberately kept its QA instrument out of the DAG (02-CONTEXT D-09). Choose per D-04's discretion note.

### Integration Points
- Phase 4 consumes the candidates artifact and the accuracy report.
- The Phase 5 TUI review flow consumes whatever schema the candidates/proposals use — D-05's reuse of the roll-object schema is what keeps that free.
- `curated_by` touches every override consumer; the TUI is the one with a human-visible surface.

</code_context>

<specifics>
## Specific Ideas

- Stage 1's honest job is to make Phase 4 cheap: every roll it binds correctly is a roll inference doesn't have to reason about, and every candidate it marks evidence-not-found is a precise question rather than an open-ended one.
- The 68% `forward_ref` share is the single most important planning number in this phase. It says Stage 1 cannot be judged by raw coverage, and it is why D-08 demands per-class measurement.
- Ch 104 is the worked example for nearly every convention here — a multi-grab bundle, a constellation named in prose, a second roll in a different constellation, evidence spread across 1,600 words, and character names that defeat naive perk-name search.

</specifics>

<deferred>
## Deferred Ideas

- Stage 2 inference, confidence gate, overrides/proposals routing, agent-run ledger idempotency — Phase 4 (CINF-04, ACUR-01 Stage 2, ACUR-02, ACUR-03).
- TUI proposal review and the full batch run — Phase 5 (ACUR-04, ACUR-05).
- Per-roll `curated_by` granularity — only if Phase 4 proves a chapter can mix hand and agent rolls (D-02).
- The 11 stub chapters' real curation — Dre's, out of scope here; they are excluded from the accuracy denominator (D-09) rather than curated by this phase.
- The remaining Phase 1 deferred items (`scripts/realign_chapters.py` ensure_ascii churn, the `_split_sections` duplication between `find_roll_locations.py` and `extract_chapter_sections.py`) — the latter is worth noting since Stage 1 works adjacent to it, but consolidating it is not this phase's job.

</deferred>

---

*Phase: 3-Provenance Schema & Deterministic Candidate Assembly*
*Context gathered: 2026-08-01*

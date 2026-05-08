# Forge Curator TUI

**Status:** active design, pre-implementation
**Purpose:** an interactive terminal tool for walking the story chapter-by-chapter, reading prose with live derived-data stats, and committing curated facts (rolls, multi-grabs, regime transitions, eligibility transitions, AN markings) that override or extend the simulator's automatic derivations.
**Audience:** the project owner, doing forensic data curation.
**Out of scope:** NLP labeling (the existing `nlp/` TUI handles that), web visualization, automated detection of facts the user must verify by eye.

## Why this exists

The validator currently surfaces 7 infeasible chapters and 76 curator/solver divergences. Each represents a place where derived data conflicts with the source narrative. Resolving each one requires reading the prose, identifying the actual rolls (hits, misses, multi-grabs, free-perk attachments) at their actual word offsets, and committing that knowledge as a curated override. This is not amenable to scripted automation — it requires reading and judgment. The TUI exists to make that human pass efficient.

It also serves as a forward-looking tool: as the story continues to update, new chapters need the same forensic pass.

## Decisions encoded

- **Q-A — Persistence: minimal number of files.** Three persistence files total:
  - `data/manual/chapter_roll_overrides.json` (renamed from `multi_grab_overrides.json`, extended schema) — single source for all per-roll curated metadata: roll structure, hit/miss, constellation, perks, word_position, narrative_evidence.
  - `data/manual/regime_transitions.json` (existing) — regime change events. Pre-curated outside the TUI; no in-TUI editing action.
  - `data/manual/author_notes.json` (existing) — AN spans.
  - `data/manual/header_corrections.json` (new, only if needed for the header-correction action) — corrects markup/header word miscounts.
  - **Dropped:** `word_eligibility.json` — mid-section eligibility transitions deferred until a real case requires them.
- **Q-B — Save: auto-save after every action, with a session journal for rollback.**
  Each action writes the canonical override file *and* appends to a per-session journal at `data/manual/.session_journals/YYYY-MM-DDTHH-MM-SS.jsonl`. Each journal entry: timestamp, action type, target file path, before-state, after-state. A `:rollback N` command undoes the last N actions by replaying the journal in reverse. Journals are gitignored.
- **Q-C — Re-derivation: per-chapter in-memory recompute on every action.**
  Linear walkthrough model: data through the *previous* chapter is treated as checkpointed and stable; the current chapter is the only thing recomputing. So per-action recompute is local to the current chapter only — it doesn't restart the whole pipeline, and downstream chapters are *not* refreshed on each action (they refresh when navigated to).
  Phase 0 prerequisite: factor `predict_rolls.py`, `derive_roll_outcomes.py`, `derive_roll_facts.py`, `roll_scheduler.py` to expose chapter-scoped functions.
- **Q-D — Sibling tool, not an extension of the `nlp/` TUI.**
  New module path: `scripts/forge_curator/` (decided). Shares prose rendering, vim motions, and panel layout with `nlp/` TUI by extracting common pieces into a new shared module.

## Layout

Three columns plus a status bar:

```
+----------------+-----------------------------------------+--+----------------+
| Stats          | Prose                                  |G | Actions        |
| (left, narrow) | (center, dominant)                     |u | (right, narrow)|
|                |                                        |t |                |
| chapter:sec    |  ... prose with cursor ...             |t |  curation      |
| eligibility    |                                        |e |  buttons,      |
| CP totals      |                                        |r |  each labeled  |
| word counts    |                                        |  |  with keybind  |
| roll context   |                                        |  |                |
|                |                                        |  |                |
+----------------+-----------------------------------------+--+----------------+
| /regex1: ___   /regex2: ___   /regex3: ___                                  |
+------------------------------------------------------------------------------+
| MODIFIED  ch 97 §1 word 4544 (CP-w 4544) | NORMAL | ?: help  :w save  :q quit|
+------------------------------------------------------------------------------+
```

### Left panel — stats (driven by cursor position)

- chapter / section
- chapter validation status: feasible / infeasible (with diagnostic) / ambiguous
- override status: which override files have entries for this chapter
- is the entire current section CP-eligible: yes/no
- is the cursor's current word CP-eligible: yes/no (differs from above when there's a mid-section eligibility transition)
- total predicted CP earned by cursor position
- current banked CP (post-debit of any rolls before cursor)
- total chapter word count (raw)
- total chapter CP-earning word count (excluding non-eligible sections, AN, headers/markup)
- total predicted rolls in chapter
- words-till-next-roll (CP-earning words)
- perks acquired this chapter, listed in canonical roll order (override-aware)
- last roll: hit/miss, constellation, perk(s) and cost(s)
- pending unsaved curations counter

### Center panel — prose

- Renders the chapter's prose as one continuous flow with section breaks indicated as horizontal rules.
- Cursor is a visible block (vim-style).
- Vim motions: `h j k l w b e gg G 0 $ /` etc. Ported from existing labeling TUI.
- Cursor word index increments on every word, but the *CP-earning* index only increments when the current word is eligible — so the stats panel can show both.
- Visual mode (`v`) selects spans; used for span-mark-as-evidence action.

### Bottom — regex strip

Three independent regex inputs. Each maintains a list of matches for the current chapter; gutter shows their positions. Skip-to-next-match actions on right panel.

### Right gutter — color-coded indicators

Single-character indicators in the gutter, each tied to a row in the prose panel. **Legend toggleable with `?`.**

| Color/glyph | Meaning |
|---|---|
| `═` | section break / header |
| `R` | predicted roll position (from simulator) |
| `H` | curated/derived hit (override or curator) |
| `M` | curated/derived miss |
| `E` | in-section eligibility change |
| `A` | author note span |
| `1`/`2`/`3` | regex 1 / 2 / 3 match |
| cursor row highlighted | current cursor position |

Multiple indicators on the same row stack as a small badge.

### Right panel — actions

Each action labeled with its keybind. Vim-discoverable. Routed to the right persistence file. Auto-save fires after each action.

**Eligibility:**
- `e` Toggle chapter eligibility (entire chapter on/off)
- `E` Toggle in-section eligibility from cursor word forward (Joe-POV transitions). *Deferred — only wire up if a real case demands it.*
- `n` Mark AN start at cursor; `N` Mark AN end at cursor
- `h` Mark current header span at cursor (correct a header that's being miscounted as prose words)

**Roll metadata (operates on "current" roll = most recent roll at or before cursor):**
- `H` Set last roll to hit
- `M` Set last roll to miss
- `c` Set last roll constellation (opens picker)
- `p` Set last roll perks (multi-select picker over chapter's obtained_perks)
- `s` Mark selected span (visual mode) as last roll's narrative_evidence

**Roll structure (lower priority — keep available):**
- `i` Insert new roll at cursor (for missing rolls like ch 97 Alchemy). Available but expected rare; with continuous CP curation, missing rolls should diminish.
- `d` Delete current roll (for spurious predictions). Same expectation.

**Navigation:**
- `]r` Next roll marker; `[r` Previous roll marker
- `]s` Next section; `[s` Previous section
- `]c` Next chapter; `[c` Previous chapter
- `]1` / `]2` / `]3` Next regex 1/2/3 match (and `[1/2/3` for previous)

**Dropped from MVP:** jump-to-chapter modal, next-infeasible-chapter, next-divergence, regime-transition mark, inline feasibility preview. Linear chapter walkthrough is the workflow; cross-chapter validation indicators add noise without changing what you'd do next.

**CLI launch arg:** `--chapter X[.Y]` opens the TUI at that chapter for resumption.

## Persistence — file shapes

### `data/manual/chapter_roll_overrides.json` (renamed from `multi_grab_overrides.json`)

Extends the existing schema. Each override roll can now carry full metadata:

```json
{
  "_purpose": "Hand-curated per-chapter roll structure and metadata. Beats curator log when present.",
  "chapter_roll_overrides": {
    "97": {
      "rolls": [
        {
          "perks": [],
          "outcome": "miss",
          "constellation": "Alchemy",
          "word_position": 31,
          "narrative_evidence": "I quickly noted a failed connection to the largest mote in the Alchemy constellation"
        },
        {
          "perks": ["Additional Space - Starting Area", "Additional Space – Lofty Loft"],
          "outcome": "hit",
          "constellation": "Personal Reality",
          "word_position": 4544,
          "narrative_evidence": "secured two connections (PR multi-grab)"
        },
        {
          "perks": ["Nano-Forge"],
          "outcome": "hit",
          "constellation": "Size",
          "word_position": 6664,
          "narrative_evidence": "..."
        }
      ],
      "narrative_evidence": "chapter-level note (optional)"
    }
  }
}
```

Multi-grab is a degenerate case: one roll entry with multiple perks. Single-perk hits are one entry with one perk. Misses have empty `perks` array. All fields except `perks` and `outcome` are optional.

### `data/manual/regime_transitions.json` (existing)

Unchanged from current schema. TUI's `r` action writes here.

### `data/manual/author_notes.json` (existing)

Unchanged. TUI's `n` / `N` actions write here.

### `data/manual/header_corrections.json` (new, only if needed)

When a markup or header is being miscounted as prose words, this file records the correction. Skeleton:

```json
{
  "_purpose": "Per-chapter header span corrections. Words inside listed spans are excluded from CP-earning word counts.",
  "corrections": [
    {
      "chapter_num": "97",
      "section_index": 0,
      "word_offset_start": 0,
      "word_offset_end": 12,
      "narrative_evidence": "..."
    }
  ]
}
```

### Dropped: `word_eligibility.json`

Mid-section eligibility transitions are deferred until a real case requires them.

## Stats panel data sources

- chapter / section structure: `data/derived/chapter_sections.json`
- prose: parsed EPUB sources (need to confirm exact path during scaffolding)
- per-chapter facts: `data/derived/chapter_facts.json`
- roll table (current chapter slice): `data/derived/roll_facts.json`
- predicted rolls: `data/derived/predicted_rolls.json`
- perks (chapter slice): `data/derived/obtained_perks.json` + `data/derived/perks_catalog.json` for cost lookup
- validation status per chapter: `data/derived/roll_validation.json`
- override entries for chapter: union of the four manual override files

## Re-derivation strategy

- After every action: auto-save to canonical override file + journal entry, then per-chapter in-memory recompute (regime simulator + scheduler + roll-fact assembly for current chapter only). Stats panel refreshes.
- Per-chapter recompute uses the *previous* chapter's `banked_cp_at_end` from `chapter_facts.json` as the starting state — that data is treated as checkpointed/stable. Downstream chapters are not re-touched on this action; they refresh when navigated to.
- Full pipeline run (writing every derived JSON file from scratch) is still the canonical "publish" step. The TUI does not run it on every action; the user runs it explicitly when ready to update derived data on disk for the rest of the project.
- On chapter change: previous chapter's curated state is flushed; next chapter's per-chapter recompute fires on load.

Phase 0 prerequisite: refactor each derive script to expose a `derive_chapter(chapter_num, ...)` function plus the existing whole-pipeline entry point.

## Validation feedback

- Stats panel shows the current chapter's feasibility / diagnostic.
- No cross-chapter validation indicators or inline preview in MVP — they were dropped per user direction. Linear walkthrough naturally surfaces issues as you reach each chapter.

## Implementation phases

**Phase 0 — Scaffolding & derive-script refactor.**
- Extract shared TUI infrastructure (vim motions, panel layout, prose renderer) into `nlp/tui_common/` (or similar).
- New entry point `scripts/forge_curator/` (or `tools/forge_curator/`).
- Refactor `predict_rolls.py`, `derive_roll_outcomes.py`, `derive_roll_facts.py`, `roll_scheduler.py` to expose chapter-scoped functions.
- Plumb prose source loading (parsed EPUB).

**Phase 1 — Read-only viewer.**
- Three-panel layout, status bar, prose with cursor, vim navigation.
- Stats panel populated from derived files.
- Gutter indicators (R/H/M/E/A/1/2/3 + section break).
- Regex inputs and skip-to-next-match.
- Navigation actions (next/prev section, chapter, roll, infeasible, divergence; jump-to-chapter modal).
- Legend overlay (`?`).
- Ships as a useful "browse the story with stats" tool. No editing.

**Phase 2 — Curation editing with auto-save + journal.**
- Action panel.
- Auto-save after every action; session journal at `data/manual/.session_journals/`.
- `:rollback N` command.
- Routing each action to its persistence file (extend chapter_roll_overrides schema; add header_corrections.json only if header-correction action is exercised).
- Span-mark-as-evidence action (visual mode `v` then `s`).

**Phase 3 — Re-derivation integration.**
- Per-chapter in-memory recompute on every action.
- Live stats refresh.

**Phase 4 — Polish.**
- Help/cheatsheet overlay (legend + keybinds).
- Action panel keybind hints inline.
- Conflict detection between override files (warn if two files disagree about same roll).

## Files to create/modify

**New:**
- `scripts/forge_curator/__main__.py` (entry)
- `scripts/forge_curator/app.py` (Textual app or curses-equivalent)
- `scripts/forge_curator/state.py` (in-memory model)
- `scripts/forge_curator/persistence.py` (route writes to override files)
- `scripts/forge_curator/rederive.py` (per-chapter recompute)
- `nlp/tui_common/` (shared panels, vim motions, prose renderer) — or a similar shared path
- `data/manual/word_eligibility.json` (stub)

**Modify:**
- `scripts/predict_rolls.py`, `scripts/derive_roll_outcomes.py`, `scripts/derive_roll_facts.py`, `scripts/roll_scheduler.py` — extract per-chapter functions
- `data/manual/multi_grab_overrides.json` → renamed to `data/manual/chapter_roll_overrides.json` with extended schema (carry over existing entries)
- All consumers of `multi_grab_overrides.json` — update path and schema parsing
- `nlp/tui/` (existing labeling TUI) — extract reusable parts into `nlp/tui_common/`

## Verification

- Phase 1 ships as standalone tool; user can browse without risk of data corruption.
- Phase 2 edits round-trip cleanly: save → reload → identical state.
- Phase 3 re-derive matches full pipeline output (regression test: run TUI's per-chapter recompute and full pipeline on the same change set; assert byte-identical output for affected chapter).
- After Phase 3, walking through the 7 infeasible chapters and curating each one should reduce the infeasible count toward zero.

## Pre-TUI prerequisites

- **Regime 1 → regime 2 transition: verified.** Clean chapter boundary at ch 91→92 (curator-log roll thresholds shift from 100 CP to 200 CP exactly at the start of ch 92). No mid-chapter transition; no `regime_transitions.json` entry needed for this transition. The current `regime_simulator.py` `>=92 → regime 2` hardcoding is correct. The regime-mark TUI action can stay dropped.
- **Migrate `multi_grab_overrides.json` to `chapter_roll_overrides.json`** with the extended schema. Existing 3 entries (ch 65, 67, 97) carry over; convert their inline arrays into the richer per-roll metadata shape (per-roll `outcome`/`constellation`/`word_position`/`narrative_evidence` fields). Update all consumers. Done as part of Phase 0.

## Open questions

- Are the existing `nlp/tui/` vim motions usable as-is, or do you want to revise the keybinds for the curator (different audience, different mental model)?

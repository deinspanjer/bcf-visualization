# Curation Conventions

Dre's hand-curation practice, captured from working sessions. This is the domain knowledge an
autonomous curation pipeline has to reproduce. Phase 3's Stage 1 (deterministic assembly) and
Stage 2 (inference refinement) both read this.

Companion docs: `WOG-NOTES.md` (author word-of-god), the Phase 1
`corpus-analysis-report.md` (measured corpus statistics), Phase 2 `02-CONTEXT.md` (the
verifier's rules, D-01..D-13).

---

## 1. A roll is a bundle

A hit roll's `perks` array is **one paid perk followed by its cost-0 ride-alongs**.
`obtained_perks.json` lists them in exactly that order, and that ordering is a reliable
deterministic grouping signal.

Example — ch 92: `Cybertronian Forge` (600) then six cost-0 Transformers items; the curated
roll groups all seven.

A **multi-grab** is different: several *paid* motes taken in one roll (the Personal Reality /
Additional Space mechanic). Ch 104 roll 0 is eight paid 50-CP Entrance Hall motes in a single
roll — and the prose names it as such: *"connect to a **cluster** of motes."* Prose wording
("cluster", "several", counts) is corroborating evidence for multi-grab grouping.

**Resolution:** paid names (cost > 0) resolve through `perk_name_resolver.py` against
`perk_directory.json`. Cost-0 ride-alongs are absent from that rollable roster **by design** and
resolve against `obtained_perks.json` instead. Never add ride-alongs to the directory.

---

## 2. The shape of hit evidence

The connection passage runs, in order:

1. **The mote is reached** — "I felt the Forge move again", "I felt my power connect/shift"
2. **The constellation is named**, usually right there
3. **The paid perk is named**, often a little later
4. **Free perks are mentioned loosely** — "it also gave me a gun and laser sword"

Then the author has the MC *dwell on the acquisition*, so **individual perk names frequently
appear verbatim several paragraphs further on**. Practice is to search the chapter for each
perk's name or a substring and attach the **first** real mention as an additional quote.

Consequences, all measured:

- A roll's quotes can span most of a chapter: mean 1.46 quotes/roll, **max 22**; intra-roll span
  median 128 words, p90 1,232, **max 7,392**. Ch 92's hit roll spans 1,617 words across five
  quotes. **Never bound a quote's distance from the roll's `word_position`.**
- Only ~half of cost-0 perks are named verbatim in their roll's quotes; others appear in variant
  form (`Altmode` → prose "alt-mode") or only descriptively. A rule requiring per-perk name
  evidence would systematically fail correct curations.

---

## 3. Roll placement

Place the roll's `word_position` **immediately before and close to its connection quote**. Unless
the narrative signals a delayed mention, the author calculated the roll shortly before starting to
describe its results. Ch 104: roll 0 at 2860 (quote @2861), roll 1 at 8439 (quote @8440).

When a quote genuinely belongs to a different chapter than the roll, that is expressed per-quote
via `mention_chapter_num` — 8% of corpus quotes do this. It is not a reason to move the roll.

---

## 4. Misses

Misses are not in the acquired list, so there is no perk to anchor them. In chapters with no other
source evidence, consume predicted rolls against a quote describing the Forge reaching and
**failing** to connect — "failed to latch", "spun away", "constellation passed", "not enough
reach". **When the constellation is actually named, update the roll to carry it.**

---

## 5. Partial evidence is an acceptable outcome

**This is the key rule for autonomous curation.** When only some of a roll's evidence can be found
confidently, capture what is solid and **flag the remainder as evidence-not-found** for later hand
editing. Do not guess, and do not fail the whole roll.

Concretely, for ch 104's eight-perk Entrance Hall multi-grab, capturing only the main connection
quote would have been an acceptable autonomous result — the rest raised for a curator.

The reason this matters is a real precision trap: that perk's wording invites the author to
customise it, so the chapter names characters (`Aisha`, `Tetra`, `Tybalt`, `Fleet`, `Survey`) who
each received their own Entrance Hall. Those names appear **from word 8 onward**, thousands of
words before the roll at 2861, as ordinary narrative. A naive first-mention search attaches
nonsense. Recognising that these mentions are *consequences being described* rather than
perk-name evidence takes an inference read of the following paragraphs — a Stage 2 job, not a
Stage 1 one.

Done well (what a human curation captures here), the evidence is:

- the connection quote naming the constellation and the cluster;
- *"Everyone had received their own Entrance Hall, and a key to go with it. Five-meter cubic rooms
  had appeared across the Workshop, one for every resident."* — establishes the per-character
  distribution;
- *"There were actually two entrances that had been provided for the Kerbals, one in the Space
  Center and one in the embassy. It seemed that the pilots and engineering staff were counted
  separately by my power."* — explains why the count exceeds the headcount.

Stage 1 should be expected to find the first. Stage 2 may find the second and third. Neither
failing is a curation failure — it is a flag.

---

## 6. Search posture

Candidate **discovery** and candidate **validation** are tuned in opposite directions and must not
be conflated (Phase 2 D-13):

- **Stage 1 / discovery is deliberately liberal** — over-produce, match variants and substrings,
  accept false positives. `find_roll_locations.py` is explicitly built this way.
- **The mechanical verifier is exact-or-reject** — Tier 1 byte-exact, Tier 2 after
  confusable/whitespace/case folding only, and no fuzzy path exists in the code at all.

Loosening the verifier to accommodate discovery, or tightening discovery to the verifier's bar,
are both regressions.

---

## 7. Authority

Hand-curated overrides beat everything. If the verifier disagrees with the corpus, the verifier is
wrong until a human says otherwise. If the predicted-roll simulation disagrees with well-evidenced
curation, the simulation is the suspect — corrections go through `data/manual/roll_overrides.json`
(applied after the solver, before validation), never by bending the curation to fit.

# Stage 2 agent-curation trial — quotes found (2026-08)

> **This is a reference record, not curation data. Never load it as a corpus.**
> It is not registered in any schema, not read by the pipeline, and not an input to anything.
> The trusted corpus is `data/manual/chapter_roll_overrides.json` and was byte-unchanged by this run.


## What this is

On 2026-08-03 a single Stage 2 inference run was executed against 5 **already hand-curated**
chapters, as the deciding trial for automating curation. Dre reviewed the output and stopped the
effort. This file preserves the one durable result: **52 evidence quotes proposed by the model,
every one located in real prose and confirmed by the mechanical verifier at Tier 1** (exact
substring match), with zero hallucinations and zero rolls left without evidence.

The working file those quotes lived in (`data/derived/agent_proposals.json`) is gitignored and
will not survive. This document is the record.

### Why it was stopped anyway

**Quote finding worked. Roll structure did not.** The model reliably located the right *passages*
but was unreliable at assigning *outcome* (hit vs miss) and *constellation*. Chapter 81 is the
clearest case: five `hit / Personal Reality` rolls proposed where the corpus curates misses.

That split is the single most useful thing here for a future attempt: the retrieval-plus-verify
half is sound and does not need re-deriving; the structural-inference half is the unsolved
problem, and it is a prompt-and-exemplar problem rather than a plumbing one.

### Where the code went

Parked on the long-lived branch **`parked/stage2-inference`** (on `origin`), deliberately kept off
`main` so it is not mistaken for a foundation. That branch is also the full archive of the curation
workstream's planning history, which `main` does not carry.

The archived branch retains the measured transport findings — including that a stdio MCP server
loses a startup race to `claude -p`, and that subprocess exit 0 does not mean success — alongside
the implementation summary explaining what was built and why it stopped.

**Also retired with it:** the Stage 1 deterministic candidate assembler
(`build_candidate_rolls.py`), its accuracy measurement, and the exemplar mining
(`build_exemplar_index.py` / `query_exemplars.py`) that existed to feed agent prompts. All are on the
parked branch. `mechanical_verifier.py` was **kept on `main`** — it checks hand-curation with no LLM
involved, which is useful independent of any automation.

---

## Summary

| Chapter | Rolls | Quotes | Tier 1 | Unlocated | Agreement with the hand-curated corpus |
|---|---|---|---|---|---|
| 92 | 2 | 5 | 5 | 0 | Reproduced cleanly. |
| 104 | 3 | 6 | 6 | 0 | Strongest agreement. |
| 81 | 8 | 13 | 13 | 0 | **The genuine failure.** |
| 88 | 12 | 17 | 17 | 0 | Right evidence, wrong structure. |
| 36 | 8 | 11 | 11 | 0 | Unscoreable. |
| **Total** | **33** | **52** | **52** | **0** | |

Model: `opus`. Run id `2026-08-03T03:14:18Z-46e05c4c`. Tool surface `stage2-tools-v1`.

Exact position matches against the corpus were 12/52 — but that gap is almost entirely **boundary
width**, not wrong location. The model tends to open a quote one clause earlier than Dre does
(*"As Tetra was pondering the possibilities I felt the Forge move again…"* vs the curated
*"I felt the Forge move again…"*). That is trimming, and is a different and much smaller problem
than chapter 81's structural misread.

---

## Chapter 92

**Reproduced cleanly.** 2 rolls, all 5 quotes Tier 1. Correctly declined the CURATION-CONVENTIONS §5 trap: post-roll alt-mode/Functionism discussion is Transformer lore, not a clean perk-name mention, so it was left unattached rather than grabbed.

### Roll 1 — `hit` / Size @ word 1094

Perks: `Cybertronian Forge`, `Altmode`, `Decepticon Terrorize!`, `Energon`, `Energon Battle Pistol`, `Energon Melee Weapon`, `ROBOTS IN DISGUISE! - Medium Chassis`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@8238** — "As Tetra was pondering the possibilities I felt the Forge move again. The slowed rotation had allowed even more reach to amass, leading to the largest amount I had ever assembled. As the Size constellation drifted towards me one of the remaining large motes was easily secured and pulled towards me."
- **@8512** — "the Cybertronian Forge granted by my power fully installed with the full context of what it meant burning in my mind"
- **@8867** — ""No, not really military grade." I explained. "Battle Pistol and Energon Melee Weapon."
- **@10428** — "despite the daily free energon it generated and the limitless supplies of a metal I had struggled to obtain"

> Model note: Post-roll alt-mode/Functionism discussion is Transformer lore/consequence, not a clean Altmode perk-name mention, so it was not attached.

> Flagged unfilled: evidence for free perks Altmode, Decepticon Terrorize!, ROBOTS IN DISGUISE! - Medium Chassis

### Roll 2 — `miss` / Knowledge @ word 5094

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `low` *(metadata only — never a routing input, per D-13)*

- **@3493** — "I took it in as I felt the Forge fail to connect to a massive mote from the Knowledge constellation."

> Model note: Slot 2 was undetermined at predicted word 5094; the nearest and only failed-connection event in the chapter is the Knowledge miss at 3493.

> Flagged unfilled: perks

---

## Chapter 104

**Strongest agreement.** Reproduced both curated rolls at byte-identical word positions (2861, 2986, 8440, 8613). Also submitted a third roll — a Knowledge miss at word 92 — present in neither Stage 1 nor the corpus. Stage 1 is known to under-predict this chapter (it is the chapter whose alignment anchor is deliberately stale pending manual review), so this may be a real find or an over-read; never adjudicated.

### Roll 1 — `miss` / Knowledge @ word None

evidence class `direct` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@92** — "I missed a large mote from the Knowledge constellation early in the process"

> Model note: No Stage 1 candidate slot supplied for this miss; added as an extra slot_index. No perk acquired, nothing further to fill.

> Flagged unfilled: per-unit evidence for Entrance Hall - Espirit de Kerbal

> Flagged unfilled: per-unit evidence for Entrance Hall - Some Old Friends

### Roll 2 — `hit` / Personal Reality @ word 0

Perks: `Entrance Hall - Espirit de Kerbal`, `Entrance Hall - Fleet`, `Entrance Hall - Some Old Friends`, `Entrance Hall - The Matrix`, `Entrance Hall – Aisha`, `Entrance Hall – Survey`, `Entrance Hall – Tetra`, `Entrance Hall – Tybalt`

constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@2861** — "I paused as I felt my power connect to a cluster of motes from the Personal Reality Constellation. One I had received before, but not on this scale."
- **@2986** — "Everyone had received their own Entrance Hall, and a key to go with it. Five-meter cubic rooms had appeared across the Workshop, one for every resident."
- **@3164** — "By 'we' I meant myself Garment, Tetra, Fleet, Survey's hologram, and armored avatar of the Matrix"

> Model note: Perk registry lists these Entrance Hall units under Toolkits, but the prose explicitly names the Personal Reality Constellation at the moment of acquisition. Individual recipient names (Aisha, Tybalt, Tetra, Fleet, Survey, the Matrix) appear in the surrounding paragraphs; 'Espirit de Kerbal' and 'Some Old Friends' recipients are not separately named in the retrieved prose.

### Roll 3 — `hit` / Resources and Durability @ word None

Perks: `Firestorm`

- **@8440** — "I felt my power shift again, bringing forth a massive mote from the Resources and Durability constellation, which was also the final mote from the Resources and Durability constellation."
- **@8613** — "The power was called Firestorm."

> Model note: No Stage 1 candidate slot was supplied for this roll; added as an extra slot_index since Firestorm is listed as acquired in this chapter and is directly evidenced. Constellation clearing also slows rotation ('The clearing of the Resources and Durability constellation had caused the rotational energy to drop').

---

## Chapter 81

****The genuine failure.**** Proposed five `hit / Personal Reality` rolls where the corpus curates misses (Magitech, Knowledge, Vehicles, Quality). Quote overlap drops to 7/13. This is a structural misread — the quotes are real prose, verified Tier 1, but the outcome and constellation assignment is wrong. This chapter is the sharpest single example of what Stage 2 could not do.

### Roll 1 — `hit` / Personal Reality @ word 0

Perks: `Entertainment Room`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9110** — "And then the Workshop shook under our feet."
- **@9181** — "Well, technically the cluster secured from the Personal Reality constellation was called the Entertainment Room, despite being a complex of six rooms."
- **@9359** — "The facilities were all top notch and the cluster had been bundled with four additional items."

> Model note: Slots 1-5 are one Personal Reality multi-grab: Entertainment Room plus four additional motes bundled with the cluster, all described in the same passage.

### Roll 2 — `hit` / Personal Reality @ word 1296

Perks: `Auditorium`

evidence class `forward_ref` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9424** — "Another minor mote called Auditorium added exactly what you'd assume."
- **@9359** — "The facilities were all top notch and the cluster had been bundled with four additional items."

### Roll 3 — `hit` / Personal Reality @ word 3296

Perks: `Costume Closet`

evidence class `forward_ref` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9463** — "An additional mote called Costume Closet provided any costume that might be needed on request"
- **@9359** — "The facilities were all top notch and the cluster had been bundled with four additional items."

### Roll 4 — `hit` / Personal Reality @ word 5296

Perks: `Kit and Kaboodle`

evidence class `forward_ref` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9375** — "One called Kit and Kaboodle added a recording booth, professional mixing board, and a limitless supply of instruments."
- **@9359** — "The facilities were all top notch and the cluster had been bundled with four additional items."

### Roll 5 — `hit` / Personal Reality @ word 7296

Perks: `Music Collection`

evidence class `forward_ref` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9580** — "Music Collection was paired with the music room and provided five hundred albums."

### Roll 6 — `miss` / Quality @ word 9296

evidence class `direct` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@10723** — "briefly noting a failed connection from the Quality constellation"

> Model note: Chapter also narrates earlier misses (Magitech ~w2023, Knowledge ~w4509, Vehicles ~w6361) with no Stage 1 slot; the three miss slots were matched to the three latest misses by position.

> Flagged unfilled: perks

### Roll 7 — `miss` / Knowledge @ word 11296

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@12882** — "I closed off my evaluation of the spiritron core as I noted the Forge failing to connect to a mote from the Knowledge constellation."

> Flagged unfilled: perks

### Roll 8 — `miss` / Vehicles @ word 13296

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@14851** — "The fact that the Forge missed a connection to the Vehicles constellation really didn't help."

> Flagged unfilled: perks

---

## Chapter 88

**Right evidence, wrong structure.** 16 of 17 proposed quotes overlap curated passages, but it called 5 hits where the corpus curates 2, and assigned constellations differently per roll. Passage-finding succeeded; roll grouping did not.

### Roll 1 — `hit` / Magic @ word 0

Perks: `Synchronicity Event`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@14448** — "This time the Magic constellation was swinging towards me and I felt my power expend all its accumulated reach to secure the smallest of the remaining motes."
- **@14570** — "The power was called Synchronicity Event."

> Model note: CONSTELLATION CONFLICT: Stage 1 predicted Knowledge, but the prose names the Magic constellation at this reach event. Carried the prose-named constellation; needs human adjudication.

### Roll 2 — `hit` / Capstone @ word 1163

Perks: `Monstrous Strength`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@21808** — "I felt the Forge shift again as it secured a small mote from the Capstone constellation."
- **@21969** — "I could recognize the change that had been brought about by Monstrous Strength."

### Roll 3 — `hit` / Personal Reality @ word 3163

Perks: `Free Portal`

evidence class `forward_ref` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9052** — "A mid-sized and a small mote were pulled free and secured as the constellation spun off again."
- **@9233** — "The second mote was called Free Portal."

> Model note: Same roll as slot 4: one Personal Reality cluster yielded two paid motes (mid-sized = Portal, small = Free Portal). Split across the two Stage 1 slots.

### Roll 4 — `hit` / Personal Reality @ word 5163

Perks: `Portal`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9037** — "The Personal Reality constellation approached and my assembled reach latched on to a large cluster."
- **@9114** — "It was called Portal. With it I could open up a gateway to my workshop at any time."

> Model note: Same roll as slot 3 (multi-grab of two paid motes from one cluster).

### Roll 5 — `hit` / Vehicles @ word 7163

Perks: `Mechanical Genius`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@2852** — "The Vehicles constellation swung towards me and my excessive amount of reach easily latched onto one of the massive motes that had yet to be secured."
- **@2899** — "That was the core principle behind my latest technical power, Mechanical Genius."

### Roll 6 — `miss` / Alchemy @ word 9163

evidence class `direct` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@1716** — "a failure to connect to an oversized mote from the Alchemy constellation"

> Model note: Misses are assigned to slots 6-12 in chapter order; this is the earliest miss in the chapter.

> Flagged unfilled: perks

### Roll 7 — `miss` / Magic @ word 11163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@4611** — "the Magic constellation missed a connection"

> Flagged unfilled: perks

### Roll 8 — `miss` / Knowledge @ word 13163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@6472** — "feeling the Knowledge constellation pass by without a connection"

> Flagged unfilled: perks

### Roll 9 — `miss` / Knowledge @ word 15163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@9858** — "My power missed a connection to the Knowledge constellation"

> Flagged unfilled: perks

### Roll 10 — `miss` / Knowledge @ word 17163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@11602** — "as the Knowledge constellation missed another connection"

> Flagged unfilled: perks

### Roll 11 — `miss` / Vehicles @ word 19163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@16485** — "as the Vehicles constellation missed a connection"

> Flagged unfilled: perks

### Roll 12 — `miss` / Time @ word 21163

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@18178** — "The Time constellation passed by as I considered the other powers that had been impacted."

> Model note: OVERFLOW: the chapter contains an eighth miss with no remaining Stage 1 slot - Size, at approx word 19543: "my power failed to connect to a mote from the Size constellation" (verified tier 1). Needs a slot added by hand.

> Flagged unfilled: perks

> Flagged unfilled: extra Size-constellation miss has no candidate slot

---

## Chapter 36

**Unscoreable.** The corpus leaves `outcome` and `constellation` null on 7 of 8 rolls, so there is no ground truth to compare against. Stage 2 filled them in. Whether it was right is unknown — recorded here precisely because it is unknown.

### Roll 1 — `hit` / Resources and Durability @ word 57

Perks: `Waste Not`, `Weapon & Item Storage Chest`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@14260** — "As I turned a corner the Forge made a connection to the Resources and Durability constellation. It was a mid-sized mote that came with a smaller mote."
- **@14287** — "The smaller mote was called Weapon &     Item Storage Chest."
- **@14408** — "The larger mote was called Waste Not. It was a massive game changer."

### Roll 2 — `hit` / Quality @ word 2057

Perks: `Minor Blessing Athena - Craftsmanship`

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@4246** — "Before I could answer the Celestial Forge moved, bringing the Quality constellation within reach. My power connected to a couple of motes from one of the clusters."
- **@4282** — "The first mote, the small one, was called Minor Blessing Athena - Craftsmanship."

> Model note: Prose describes slots 2 and 3 as one connection to 'a couple of motes' from the same cluster; may warrant multi_grab grouping across slots 2-3.

### Roll 3 — `hit` / Quality @ word 4057

Perks: `Fate Finds You Interesting`

evidence class `direct` · constellation `model_only` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@4361** — "The second mote was called Fate Finds You Interesting. It changed everything."

### Roll 4 — `miss` / Time @ word 6057

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@6707** — "The Time constellation passed by as Taylor picked up her own watch with considerable apprehension."

> Flagged unfilled: perks

### Roll 5 — `miss` / Vehicles @ word 8057

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@8555** — "The Vehicles constellation passed as I smiled at the idea."

> Flagged unfilled: perks

### Roll 6 — `miss` / Magitech @ word 10057

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@10458** — "The Magitech constellation passed by as she responded."

> Flagged unfilled: perks

### Roll 7 — `miss` / Knowledge @ word 12057

evidence class `forward_ref` · constellation `mechanical_agrees` · verify `pass` · model self-report `high` *(metadata only — never a routing input, per D-13)*

- **@12612** — "The Knowledge constellation passed by as I considered my response."

> Flagged unfilled: perks

### Roll 8 — `miss` / Alchemy @ word 14057

evidence class `direct` · constellation `mechanical_agrees` · verify `pass` · model self-report `low` *(metadata only — never a routing input, per D-13)*

- **@474** — "The Alchemy constellation passed by without a connection as I replied."

> Model note: Position mismatch: this slot predicts ~14057 but the only unassigned Forge event is the Alchemy pass at ~474. Slot-to-event mapping here is uncertain; the Alchemy miss itself is unambiguous prose.

> Flagged unfilled: perks

> Flagged unfilled: slot-to-event alignment

---

*Generated from the 2026-08-03 Stage 2 trial run at the point the effort was stopped.*

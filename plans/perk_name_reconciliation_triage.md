# Perk-name reconciliation triage

Generated: 2026-05-21
Total unique paid-perk strings: 321
Exact matches: 252
Class A (typo): 6
Class B (sub-instance): 54
Class C (unresolved): 9

Row coverage: exact=264, A=6, B=56, C=9, total=335

## Class A - typos to fix at source

| raw_name | proposed_parent | rows_affected | source_file(s) | notes |
| --- | --- | --- | --- | --- |
| `Dig it` | `Dig It` | 1 | obtained_perks.json | case-only |
| `Most Holy Order of the Stocket Wrench` | `Most Holy Order of the Socket Wrench` | 1 | rolls.json | levenshtein=1 |
| `Nano-Forge` | `Nano-forge` | 1 | obtained_perks.json, chapter_roll_overrides.json | case-only |
| `Not a Stupid Grunt` | `Not A Stupid Grunt` | 1 | rolls.json | case-only |
| `POWER OVERWHELMING` | `POWER OVERHELMING` | 1 | rolls.json, obtained_perks.json | levenshtein=1 |
| `Seeds and Seedlings` | `Seed and Seedlings` | 1 | obtained_perks.json | levenshtein=1 |

## Class B - sub-instances to resolve in derive_roll_facts.py

| raw_name | parent | instance_extracted | rows_affected | sample roll_number |
| --- | --- | --- | --- | --- |
| `Additional Space - Starting Area` | `Additional Space` | `Starting Area` | 2 | 579 |
| `Additional Space – Lofty Loft` | `Additional Space` | `Lofty Loft` | 2 | 580 |
| `Divine Child - Hephaestus` | `Divine Child` | `Hephaestus` | 1 | 165 |
| `Entrance Hall - Espirit de Kerbal` | `Entrance Hall` | `Espirit de Kerbal` | 1 | 656 |
| `Entrance Hall - Fleet` | `Entrance Hall` | `Fleet` | 1 | 656 |
| `Entrance Hall - Garment` | `Entrance Hall` | `Garment` | 1 | 571 |
| `Entrance Hall - Some Old Friends` | `Entrance Hall` | `Some Old Friends` | 1 | 656 |
| `Entrance Hall - The Matrix` | `Entrance Hall` | `The Matrix` | 1 | 656 |
| `Entrance Hall – Aisha` | `Entrance Hall` | `Aisha` | 1 | 656 |
| `Entrance Hall – Survey` | `Entrance Hall` | `Survey` | 1 | 656 |
| `Entrance Hall – Tetra` | `Entrance Hall` | `Tetra` | 1 | 656 |
| `Entrance Hall – Tybalt` | `Entrance Hall` | `Tybalt` | 1 | 656 |
| `Esoteric Collection - Magic` | `Esoteric Collection` | `Magic` | 1 | 676 |
| `Expanded Collection - Mysticism` | `Expanded Collection` | `Mysticism` | 1 | 676 |
| `Innate Talent: Alchemist` | `Alchemist` | `Innate Talent` | 1 | 61 |
| `Minor Blessing Aphrodite - Beauty` | `Minor Blessing` | `aphrodite beauty` | 1 | 370 |
| `Minor Blessing Apollo - Medicine` | `Minor Blessing` | `apollo medicine` | 1 | 660 |
| `Minor Blessing Ares – Armaments` | `Minor Blessing` | `ares armaments` | 1 | interpolated:0618 |
| `Minor Blessing Artemis - Bowmanship` | `Minor Blessing` | `artemis bowmanship` | 1 | 330 |
| `Minor Blessing Athena - Craftsmanship` | `Minor Blessing` | `athena craftsmanship` | 1 | 209 |
| `Minor Blessing Demeter - Cultivation` | `Minor Blessing` | `demeter cultivation` | 1 | 655 |
| `Minor Blessing Dionysus - Libations` | `Minor Blessing` | `dionysus libations` | 1 | 582 |
| `Minor Blessing Hades - Ferrokinesis` | `Minor Blessing` | `hades ferrokinesis` | 1 | 421 |
| `Minor Blessing Hera - Administration` | `Minor Blessing` | `hera administration` | 1 | 338 |
| `Minor Blessing Hermes - Invention` | `Minor Blessing` | `hermes invention` | 1 | 673 |
| `Minor Blessing Hestia - Hearthfire` | `Minor Blessing` | `hestia hearthfire` | 1 | 275 |
| `Minor Blessing Poseidon – Water` | `Minor Blessing` | `poseidon water` | 1 | 631 |
| `Minor Blessing Zeus – Lightning` | `Minor Blessing` | `zeus lightning` | 1 | 623 |
| `Parahuman - Tinker - Miniaturization and Efficiency` | `Miniaturization and Efficiency` | `Parahuman - Tinker` | 1 | 415 |
| `Thaumaturgical Focus: Alchemy` | `Alchemy` | `Thaumaturgical Focus` | 1 | 359 |
| `Thaumaturgical Focus: Transmutation` | `Transmutation` | `Thaumaturgical Focus` | 1 | 290 |
| `The Pond-Expansion` | `The Pond` | `expansion` | 1 | 474 |
| `Unnatural Skill: Curses` | `Unnatural Skill` | `Curses` | 1 | 624 |
| `Unnatural Skill: Firecraft` | `Unnatural Skill` | `Firecraft` | 1 | 583 |
| `Unnatural Skill: Healing` | `Unnatural Skill` | `Healing` | 1 | 660 |
| `Unnatural Skill: Music` | `Unnatural Skill` | `Music` | 1 | 421 |
| `Unnatural Skill: Naturecraft` | `Unnatural Skill` | `Naturecraft` | 1 | 655 |
| `Unnatural Skill: Ritual` | `Unnatural Skill` | `Ritual` | 1 | 619 |
| `Unnatural Skill: Runes` | `Unnatural Skill` | `Runes` | 1 | 370 |
| `Unnatural Skill: Smith` | `Unnatural Skill` | `Smith` | 1 | 78 |
| `Unnatural Skill: Stoneworking` | `Unnatural Skill` | `Stoneworking` | 1 | 632 |
| `Unnatural Skill: Transmutation` | `Unnatural Skill` | `Transmutation` | 1 | 338 |
| `Unnatural Skill: Weaving` | `Unnatural Skill` | `Weaving` | 1 | 673 |
| `Unnatural Skill:Alchemy` | `Unnatural Skill` | `alchemy` | 1 | 275 |
| `Unnatural Skill:Enchanting` | `Unnatural Skill` | `enchanting` | 1 | 330 |
| `Valuable Memories -the creation of chimeras` | `Valuable Memories` | `the creation of chimeras` | 1 | 234 |
| `Valuable Memories: Bigs` | `Valuable Memories` | `Bigs` | 1 | 254 |
| `Valuable Memories: the nature of memories` | `Valuable Memories` | `the nature of memories` | 1 | 86 |
| `Valuable Memories:the construction of Megadei` | `Valuable Memories` | `the construction of megadei` | 1 | 127 |
| `Workshop: Clothing` | `Workshop` | `Clothing` | 1 | 358 |
| `Workshop: Electronics` | `Workshop` | `Electronics` | 1 | 448 |
| `Workshop: Robotics` | `Workshop` | `Robotics` | 1 | 535 |
| `Workshop: Science` | `Workshop` | `Science` | 1 | 328 |
| `Workshop: Woodworking` | `Workshop` | `Woodworking` | 1 | 261 |

## Class C - unresolved (needs human decision)

| raw_name | rows_affected | sample roll_number | nearest candidates (top 3 with distance) | notes |
| --- | --- | --- | --- | --- |
| `Accelerator Equipment (Zoids: Legacy) (3 Customization Points)` | 1 | 381 | `Cyber-doctor Equipment Package` (d=40); `Class and Specialization` (d=41); `Democracy Under the Companions` (d=41) | matches obtained_supplemental directory entry `Accelerator Equipment` (no Unabridged parent / no wireframe star) |
| `Civilian Equipment Package` | 1 | 98 | `Cyber-doctor Equipment Package` (d=11); `Equivalent Exchange` (d=16); `Workshop Equipment` (d=16) | matches obtained_supplemental directory entry `Civilian Equipment Package` (no Unabridged parent / no wireframe star) |
| `Class Jumper` | 1 | 375 | `Classroom` (d=6); `Access Key` (d=8); `Armourer` (d=8) | matches obtained_supplemental directory entry `Class Jumper` (no Unabridged parent / no wireframe star) |
| `Doppler Field Generator (Zoids: Legacy) (5 Customization Points)` | 1 | 381 | `Democracy Under the Companions` (d=43); `Simple Scientific Solution` (d=43); `Most Holy Order of the Socket Wrench` (d=44) | matches obtained_supplemental directory entry `Doppler Field Generator` (no Unabridged parent / no wireframe star) |
| `Electron Shield Generators (Zoids: Legacy) (2 Customization Points)` | 1 | 381 | `Automated Weapons Security System` (d=45); `Aerospace Engineering Makes Things Go Fast` (d=46); `Democracy Under the Companions` (d=46) | matches obtained_supplemental directory entry `Electron Shield Generators` (no Unabridged parent / no wireframe star) |
| `Feel Feel It Out` | 1 | 395 | `Feel It Out` (d=5); `Certified Tech` (d=11); `Fueling Station` (d=11) |  |
| `Natural Puppy` | 1 | 303 | `Unnatural Skill` (d=7); `Natural Lighting` (d=8); `Medical Bay` (d=9) | matches obtained_supplemental directory entry `Natural Puppy` (no Unabridged parent / no wireframe star) |
| `Sky Machinist` | 1 | 385 | `Machinist` (d=4); `Mechanist` (d=6); `Alchemist` (d=8) | matches obtained_supplemental directory entry `Sky Machinist` (no Unabridged parent / no wireframe star) |
| `Talisman Trained` | 1 | 276 | `Talisman Adept` (d=6); `Maliwan Intern` (d=9); `Crimson Saint` (d=10) | matches obtained_supplemental directory entry `Talisman Trained` (no Unabridged parent / no wireframe star) |

## Directory parent-link audit

**1. Does `perk_directory.json` already encode a parent->child relationship for sub-instances?**

No explicit field. The directory has no `parent_id`, `parent_name`, `canonical_id`, or `instance_of` field on any row. Every row's keys are: `acquired_chapter_num, acquired_epub_sequence, acquired_instances, constellation, cost, cost_text, description, first_acquired_at_word_offset, free, id, jump, matched_to_obtained, name, repeatable, source, status`.

**2. What `build_perk_directory.py` does today.**

It folds sub-instances IN-PLACE into the canonical parent row, not as sibling rows:

- The Unabridged List defines the parent row (one row per canonical perk; multi-perk rows in column B are split). These become `source="unabridged"`.
- `obtained_perks.json` (the curator's chapter-by-chapter acquisitions) is indexed under multiple keys per entry: exact `(name, jump)`, normalized `(name, jump)`, separator-split prefix AND suffix variants (`_name_prefix_variants`, splits on `:`, ` - `, ` - `, ` - `), and normalized word-prefix variants (`_normalized_word_prefixes`, drops trailing words). Plus `JUMP_ALIASES` for jump-name drift and `PERK_ALIASES` for typos.
- For each Unabridged parent, the script calls `_obtained_lookup` and collects every matching obtained row. Those rows are listed in the parent's `acquired_instances` array (preserving the curator-typed instance name), and the parent's `acquired_chapter_num` is set to the earliest paid match.
- Obtained rows that do NOT match any Unabridged parent (after all the variant matching) become supplemental directory entries with `source="obtained_supplemental"`. There are 9 of those today.
- Free ride-along acquisitions (a free perk bundled with a paid parent) never get their own directory row; they only appear in `acquired_instances`.

Worked example - `Workshop` in the Toolkits constellation, `Personal Reality Supplement` jump:

```json
{
  "id": "Personal Reality__Personal Reality__workshop",
  "name": "Workshop",
  "jump": "Personal Reality",
  "constellation": "Personal Reality",
  "repeatable": true,
  "acquired_chapter_num": "1",
  "acquired_instances": [
    {
      "name": "Workshop: Metalworking",
      "chapter_num": "1",
      "epub_sequence": 1,
      "free": false
    },
    {
      "name": "Workshop: Woodworking",
      "chapter_num": "41",
      "epub_sequence": 48,
      "free": false
    },
    {
      "name": "Workshop: Clothing",
      "chapter_num": "52",
      "epub_sequence": 67,
      "free": false
    },
    {
      "name": "Workshop: Electronics",
      "chapter_num": "65",
      "epub_sequence": 85,
      "free": false
    },
    {
      "name": "Workshop: Robotics",
      "chapter_num": "78",
      "epub_sequence": 109,
      "free": false
    }
  ]
}
```

Note the curator-typed sub-instance strings (`Workshop: Metalworking`, `Workshop: Electronics`, ...) live inside `acquired_instances[*].name`. The parent row's own `name` stays canonical (`Workshop`).

**3. Minimum-change resolver shape for `derive_roll_facts.py`.**

`derive_roll_facts.build_directory_lookup` currently keys the directory by `(name.lower(), jump.lower())` and `name.lower()`. `lookup_perk` tries exact `(name, jump)`, then name-only with constellation filter. It does NOT replicate the prefix/suffix/word-prefix variants that `build_perk_directory.py` already runs to fold obtained rows into parents - which is exactly why curator-typed sub-instances like `Workshop: Electronics` slip through unresolved.

Recommended minimum change: lift the helpers from `build_perk_directory.py` (`_normalize`, `_name_prefix_variants`, `_normalized_word_prefixes`, and the `JUMP_ALIASES` / `PERK_ALIASES` tables) into a shared module and have `derive_roll_facts.py` use the same multi-key index. Concretely:

1. Extend `build_directory_lookup` to register each parent under its name AND every prefix/suffix/word-prefix variant (the same set the directory builder already uses).
2. In `perk_meta` / `lookup_perk`, after the exact and normalized-name lookups, fall back to those variants scoped by constellation (and by jump when the curator supplied one).
3. For Class A typos that the variants can't bridge (e.g. single-letter swaps with no separator), extend `PERK_ALIASES` with the new pairs that come out of this audit. Apply them at the same place the directory builder applies them - upstream of the lookup - so both pipelines stay in sync.
4. For Class B sub-instances, the resolver should return the PARENT's id and canonical name into `purchased_perks[*]`, while preserving the curator-typed `instance_extracted` string in a new field (e.g. `instance`) so the UI can still render the specific flavor. The wireframe star id is the parent's.

Adding an explicit `parent_id` column to `perk_directory.json` is tempting but unnecessary: the directory already holds the parent row and the sub-instances inside it. A shared variant-index utility is the minimum-change fix.

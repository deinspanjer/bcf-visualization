# Word-of-God (author) notes — curation evidence

Authoritative statements from LordRoustabout relayed by Dre. These bind curation for the
named chapters. Convention: WoG-backed roll facts with no narrative quote evidence get
**no `evidence_quotes` attributed** — the WoG entry here is the provenance, and the
`curator_note` on the roll should reference this file.

## Chapter 121.1 (Interlude Slaughterhouse Nine - Addendum Apeiron)

Relayed by Dre 2026-07-26:

> The bank was empty after the combination of environmental Personal Reality perks. I
> considered adding a cooldown since the combined cost of the two perks was 600, but that
> didn't seem in line with the spirit of the system. In this chapter points were only
> earned during Jack and Joe's sections, mostly Jack's since it was longer. There were
> missed rolls to the Capstone and Knowledge Constellations (with 200 and 400 points
> respectively), meaning there will be a 600 point roll coming up next chapter, just in
> time for Joe to meet with the Protectorate representatives outside the containment dome.

Curation implications:

1. **CP-earning sections:** Only `121.1@2` (Interlude Jack Slash, 19,737 words) and
   `121.1@9` (Addendum Apeiron = Joe, 4,185 words) earn CP. The other Slaughterhouse Nine
   interlude sections (@3–@8: Shatterbird, Mannequin, Bonesaw, Siberian, Cherish,
   Burnscar) do not. The 2026-07-26 rule-based regeneration classified @2 and @9 as
   `non_mc_other_pov` (non-earning) — @9 at low confidence with the content signal
   already disagreeing (first-person dominant). Both need curator toggles
   (`counts_for_cp: true`, `reason: "curator toggle: …"`).
2. **Bank state:** Banked CP was 0 entering 121.1 — emptied by the combined 600-CP
   purchase of the two environmental Personal Reality perks. Author considered but
   rejected a cooldown.
3. **Rolls in 121.1:** Two missed rolls — Capstone Constellation (200 CP) and Knowledge
   Constellation (400 CP). **No narrative quote evidence exists for either miss** (Dre,
   2026-07-26) — when 121.1 is curated into `chapter_roll_overrides.json`, these two
   rolls carry no `evidence_quotes`; provenance is this WoG.
4. **Look-ahead:** A 600-point roll is expected in the next chapter (Joe meeting the
   Protectorate representatives outside the containment dome).

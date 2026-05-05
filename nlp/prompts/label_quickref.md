# BCF Label Quick Reference

## Layer A — Events (span smallest clause carrying the event)
ACQUISITION — protagonist gains a perk now (ex: "gained Perfect Pitch"; NOT recall or counterfactual)
MISS — roll produces no perk (ex: "wheel stopped on nothing"; NOT counterfactuals)
ROLL_ATTEMPT — roll cue without outcome in same span; if result present use ACQUISITION/MISS instead
CONSTELLATION_REVEAL — new constellation first activation (NOT passing mention of existing)

## Layer B — Entities (span exactly named substring; no articles or punctuation)
PERK_NAME — literal perk name (ex: "Perfect Pitch", "[Workshop]"; NOT descriptive paraphrase)
CONSTELLATION_NAME — constellation name (ex: "Toolkit", "Personal Reality")
JOE_NAME — protagonist personal name (ex: "Joe", "Joe Murphy"; NOT pronouns)
JOE_CAPE_NAME — protagonist cape epithet (ex: "Celestial Forge"; NOT lowercase descriptive)
OTHER_CAPE_NAME — other characters' cape names (ex: "Bakuda"; NOT civilian names in non-cape context)
DATE_REF — explicit calendar reference (ex: "April 14th", "2011"; NOT "the next day")
TIME_OF_DAY — diurnal reference (ex: "after sunset", "around noon"; NOT "morning person")
DURATION — passage of time (ex: "two hours later", "the next day"; NOT distance metaphors)
FLASHBACK_CUE — recollection marker in text (ex: "he remembered"; NOT chapter-break-only signals)
DILATION_CUE — in-story time differs from real time via power/device (ex: "a heartbeat that lasted minutes")

"""Build 2D star-pattern wireframes for the 14 cluster-constellations
and every per-jump sub-constellation.

Two-level model:

  1. Cluster constellation — themed by the constellation's NAME
     (Toolkits → wrench outline, Knowledge → open book, …). Geometry
     is hand-authored: each constellation has a curated SVG at
     data/constellations/NN-<slug>/current.svg from which the Phase 4
     extractor reads marker_positions (star anchors in unit-square
     coords) and silhouette (polyline strokes for the constellation
     outline). Lifecycle fields (revealed/completed/pool) come from
     data/derived/constellation_lifecycle.json.

  2. Per-jump mini-constellation — themed by the jump's source media,
     as an abstract star pattern, NOT a literal logo. Stars are
     EVERY perk in the jump (acquired or not); star size encodes
     cost (100 CP → small, 800+ CP → ~1.0, null cost → smallest).
     Each star carries its directory id, status, and acquired chapter
     so the renderer can fog/unfog as the scrubber moves through the
     timeline.

Coordinates for jump constellations are normalized to roughly
[-1, 1] x [-1, 1]; for cluster constellations they are normalized to
[0, 1] (extractor divides SVG pixel coords by the 320 viewBox). The
renderer applies 3D positioning. Reads perk_directory.json so this
includes unacquired perks ("Available", "Partial", etc.) as fog-able
stars in the sky alongside the acquired ones.

Run:

    python3 scripts/build_constellation_wireframes.py

Output: data/derived/constellation_wireframes.json (validated against
data/derived/_schemas/constellation_wireframes.schema.json).
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from _common import write_validated_json
from extract_constellation_svgs import extract as extract_constellation_svgs

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "data" / "derived" / "perk_directory.json"
LIFECYCLE = ROOT / "data" / "derived" / "constellation_lifecycle.json"
CONSTELLATIONS_DIR = ROOT / "data" / "constellations"
OUT = ROOT / "data" / "derived" / "constellation_wireframes.json"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def norm_jump(s: str | None) -> str | None:
    """Strip cosmetic typography variants so 'Asura's Wrath' and
    'Asura’s Wrath' (curly apostrophe), or 'Star Trek - TNG+DS9' and
    'Star Trek – TNG+DS9' (en-dash), collapse to a single jump name.
    Mirrors the spot-check's tolerance for curator typography drift."""
    if not s:
        return s
    return s.replace("–", "-").replace("—", "-").replace("’", "'").strip()




# ---------------------------------------------------------------------------
# Per-jump star-pattern shapes (hand-designed for prominent jumps)
# ---------------------------------------------------------------------------
#
# Each entry is a list of (x, y) star positions in normalized [-1, 1].
# Slots are filled in order; if a jump has more perks than slots, the
# extras tile around an outer micro-spiral. If fewer, leftover slots
# are skipped.
#
# Designs are abstract star patterns inspired by silhouettes from each
# jump's source media — never literal logos. shape_concept documents
# what the constellation traces.

# Helper builders for shapes that recur (saucer ship, generic wedge…)

def _starship_saucer() -> list[tuple[float, float]]:
    """Federation-style saucer: round disc on top, neck, twin nacelles."""
    return [
        (-0.55,  0.55),   # disc rim left
        ( 0.55,  0.55),   # disc rim right
        ( 0.00,  0.80),   # disc top
        ( 0.00,  0.30),   # disc bottom (neck top)
        ( 0.00, -0.10),   # neck bottom
        (-0.65, -0.50),   # left nacelle front
        ( 0.65, -0.50),   # right nacelle front
        (-0.85, -0.80),   # left nacelle rear
        ( 0.85, -0.80),   # right nacelle rear
        (-0.30, -0.40),   # engineering hull left
        ( 0.30, -0.40),   # engineering hull right
        ( 0.00,  0.55),   # disc center
    ]


JUMP_SHAPES: dict[tuple[str, str], dict] = {
    # ----- Personal Reality (the workshop itself) ---------------------
    ("Personal Reality", "Personal Reality"): {
        "shape_concept": "Joe's workshop: floor plan with workbench, forge, tool wall and two doors",
        "stars": [
            # outer footprint
            (-0.95,  0.85), ( 0.95,  0.85), ( 0.95, -0.85), (-0.95, -0.85),
            # workbench (long horizontal in the upper third)
            (-0.50,  0.45), ( 0.50,  0.45),
            # forge (square in upper-right)
            ( 0.55,  0.20), ( 0.85,  0.20), ( 0.55,  0.55), ( 0.85,  0.55),
            # tool wall (vertical line on left)
            (-0.85,  0.30), (-0.85,  0.00), (-0.85, -0.30),
            # central anvil
            ( 0.00, -0.10),
            # access door (bottom edge)
            (-0.20, -0.85), ( 0.20, -0.85),
            # warehouse door (right edge)
            ( 0.95,  0.30), ( 0.95, -0.30),
            # storage shelves on the back wall
            (-0.40,  0.85), ( 0.10,  0.85), ( 0.40,  0.85),
            # raw-material crates
            (-0.55, -0.55), (-0.20, -0.55), ( 0.20, -0.55), ( 0.55, -0.55),
            # ceiling lights
            (-0.30,  0.60), ( 0.30,  0.60),
            # second workbench
            (-0.20,  0.10), ( 0.20,  0.10),
            # hub center
            ( 0.00,  0.00),
        ],
    },
    ("Toolkits", "Personal Reality"): {
        "shape_concept": "open toolbox: tray with rows of slots seen from above",
        "stars": [
            (-0.85,  0.50), ( 0.85,  0.50),  # tray ends top
            (-0.85, -0.50), ( 0.85, -0.50),  # tray ends bottom
            (-0.85,  0.00), ( 0.85,  0.00),  # tray midpoints
            # tool slots, evenly spaced inside
            (-0.55,  0.30), (-0.20,  0.30), ( 0.20,  0.30), ( 0.55,  0.30),
            (-0.55,  0.00), (-0.20,  0.00), ( 0.20,  0.00), ( 0.55,  0.00),
            (-0.55, -0.30), (-0.20, -0.30), ( 0.20, -0.30), ( 0.55, -0.30),
        ],
    },

    # ----- Greek myth / Percy Jackson ---------------------------------
    ("Quality", "Percy Jackson"): {
        "shape_concept": "Olympian pantheon ring: twelve points around a center for the council, with a trident at the rim",
        "stars": [
            # 12-point ring (gods of Olympus)
            *[ (math.cos(i * math.pi / 6) * 0.85, math.sin(i * math.pi / 6) * 0.85)
               for i in range(12) ],
            # central altar
            ( 0.00, 0.00),
            # trident (sea-god accent at right edge)
            ( 0.95,  0.20), ( 0.75,  0.05), ( 0.95, -0.20),
            # lightning accent (sky-god at top edge)
            ( 0.10,  0.95), (-0.10,  0.75), ( 0.05,  0.55),
            # laurel wreath inner ring fragment
            (-0.50,  0.30), ( 0.50,  0.30), (-0.50, -0.30), ( 0.50, -0.30),
            # extra slots for the very large perk count
            (-0.30,  0.00), ( 0.30,  0.00), ( 0.00,  0.30), ( 0.00, -0.30),
            (-0.65,  0.65), ( 0.65,  0.65), (-0.65, -0.65), ( 0.65, -0.65),
        ],
    },

    # ----- Star Trek (saucer + nacelles) ------------------------------
    ("Knowledge", "Star Trek - TNG+DS9"): {
        "shape_concept": "Federation starship from above: saucer section, neck, twin warp nacelles",
        "stars": _starship_saucer(),
    },

    # ----- Transformers (robot mask) ----------------------------------
    ("Size", "Transformers"): {
        "shape_concept": "abstract Cybertronian visage: forehead crest, visor band, jaw and antennae",
        "stars": [
            (-0.50,  0.85), ( 0.50,  0.85),    # antennae tips
            (-0.30,  0.55), ( 0.30,  0.55),    # forehead crest corners
            ( 0.00,  0.65),                    # crest center
            (-0.75,  0.20), ( 0.75,  0.20),    # visor outer edges
            (-0.30,  0.20), ( 0.30,  0.20),    # visor inner glints
            (-0.55, -0.20), ( 0.55, -0.20),    # cheek points
            ( 0.00,  0.20),                    # nose ridge
            (-0.30, -0.55), ( 0.30, -0.55),    # jaw corners
            ( 0.00, -0.85),                    # chin point
        ],
    },

    # ----- Gears of War (chainsaw rifle silhouette) -------------------
    ("Knowledge", "Gears of War"): {
        "shape_concept": "Lancer-style rifle: rectangular receiver with chainsaw teeth jutting underneath",
        "stars": [
            (-0.85,  0.20), ( 0.55,  0.20),    # receiver top
            (-0.85, -0.10), ( 0.55, -0.10),    # receiver bottom
            (-0.40, -0.45), ( 0.10, -0.45), ( 0.55, -0.45),   # chainsaw teeth row
            (-0.10, -0.10),                    # trigger guard
            ( 0.85,  0.10),                    # muzzle
            ( 0.30,  0.55),                    # iron sight
        ],
    },

    # ----- Kenichi (martial arts dojo: training-floor cross) ----------
    ("Quality", "History's Strongest Disciple: Kenichi"): {
        "shape_concept": "dojo training ring: square mat with a central practitioner and four cardinal stances",
        "stars": [
            ( 0.00,  0.85), ( 0.85,  0.00),    # cardinal points
            ( 0.00, -0.85), (-0.85,  0.00),
            ( 0.00,  0.00),                    # center
            ( 0.55,  0.55), (-0.55,  0.55),    # diagonal stances
            ( 0.55, -0.55), (-0.55, -0.55),
        ],
    },

    # ----- Bloodborne (trick weapon abstract) -------------------------
    ("Magic", "Bloodborne"): {
        "shape_concept": "saw cleaver: serrated blade folded over a haft, abstracted as parallel star arcs",
        "stars": [
            ( 0.85,  0.55), ( 0.55,  0.40), ( 0.20,  0.35),    # blade upper edge
            ( 0.85,  0.20), ( 0.55,  0.10), ( 0.20,  0.05),    # blade lower edge / teeth
            (-0.20, -0.05), (-0.55, -0.30), (-0.85, -0.55),    # haft trailing down-left
            (-0.30,  0.10),                                    # pommel guard
        ],
    },
    ("Crafting", "Bloodborne"): {
        "shape_concept": "hunter's workshop bench: anvil silhouette with three tool stars above",
        "stars": [
            (-0.55, -0.20), ( 0.55, -0.20), ( 0.00, -0.55),    # anvil outline
            (-0.30,  0.55), ( 0.00,  0.75), ( 0.30,  0.55),    # tools hanging above
        ],
    },
    ("Toolkits", "Bloodborne"): {
        "shape_concept": "lantern silhouette: post and hanging flame",
        "stars": [
            ( 0.00,  0.85), (-0.20,  0.55), ( 0.20,  0.55), ( 0.00, -0.85),
        ],
    },
    ("Capstone", "Bloodborne"): {
        "shape_concept": "moon over the spires: crescent arc",
        "stars": [
            (-0.55,  0.30), ( 0.00,  0.55), ( 0.55,  0.30),
        ],
    },

    # ----- Kerbal Space Program (rocket on the pad) -------------------
    ("Vehicles", "Kerbal Space Program"): {
        "shape_concept": "rocket on the pad: nose cone, capsule, fuel stages, fins, exhaust plume",
        "stars": [
            ( 0.00,  0.95),    # nose cone tip
            (-0.20,  0.65), ( 0.20,  0.65),  # capsule shoulders
            (-0.20,  0.30), ( 0.20,  0.30),  # upper stage
            (-0.20,  0.00), ( 0.20,  0.00),  # mid stage
            (-0.20, -0.30), ( 0.20, -0.30),  # lower stage
            (-0.55, -0.55), ( 0.55, -0.55),  # fin tips
            ( 0.00, -0.85),                  # exhaust
        ],
    },
    ("Size", "Kerbal Space Program"): {
        "shape_concept": "stacked booster cluster: central core with two strap-on boosters",
        "stars": [
            ( 0.00,  0.85), ( 0.00,  0.30), ( 0.00, -0.30), ( 0.00, -0.85),
            (-0.55,  0.30), (-0.55, -0.30),
            ( 0.55,  0.30), ( 0.55, -0.30),
        ],
    },

    # ----- GUNNM / Battle Angel Alita (cybernetic body) ---------------
    ("Toolkits", "GUNNM/Battle Angel Alita"): {
        "shape_concept": "cybernetic frame: head, chest plate, articulated arms",
        "stars": [
            ( 0.00,  0.85),    # head
            (-0.30,  0.55), ( 0.30,  0.55),  # shoulders
            (-0.65,  0.20), ( 0.65,  0.20),  # elbows
            (-0.85, -0.20), ( 0.85, -0.20),  # hands
            ( 0.00,  0.20), ( 0.00, -0.20),  # spine
            (-0.30, -0.55), ( 0.30, -0.55),  # hips
        ],
    },

    # ----- Halo (UNSC) - Master Chief helmet abstract ---------------
    ("Knowledge", "Halo UNSC"): {
        "shape_concept": "Spartan helmet abstract: visor sweep, crown, jaw line",
        "stars": [
            (-0.55,  0.55), ( 0.55,  0.55),    # crown corners
            ( 0.00,  0.75),                    # crown apex
            (-0.75,  0.20), ( 0.75,  0.20),    # visor outer edges
            (-0.30,  0.10), ( 0.30,  0.10),    # visor inner highlights
            (-0.55, -0.30), ( 0.55, -0.30),    # jaw outer
            ( 0.00, -0.60),                    # chin
        ],
    },
    ("Knowledge", "Halo"): {
        "shape_concept": "Halo ring on edge: long thin arc of stars",
        "stars": [
            (-0.85,  0.10), (-0.55,  0.30), (-0.20,  0.40), ( 0.20,  0.40),
            ( 0.55,  0.30), ( 0.85,  0.10),
        ],
    },
    ("Vehicles", "Halo"): {
        "shape_concept": "Warthog jeep: chassis bar with two wheel circles",
        "stars": [
            (-0.85,  0.10), ( 0.85,  0.10),    # chassis bar
            (-0.55, -0.40), ( 0.55, -0.40),    # wheels
            ( 0.00,  0.40),                    # mounted gun
        ],
    },

    # ----- Ace Combat (jet fighter) -----------------------------------
    ("Toolkits", "Ace Combat"): {
        "shape_concept": "delta-wing fighter from above: nose, swept wings, twin tails",
        "stars": [
            ( 0.00,  0.95),    # nose
            (-0.20,  0.20), ( 0.20,  0.20),  # cockpit
            (-0.85, -0.30), ( 0.85, -0.30),  # wingtips
            (-0.30, -0.10), ( 0.30, -0.10),  # wing roots
            (-0.30, -0.85), ( 0.30, -0.85),  # twin tail fins
            ( 0.00, -0.55),                  # exhaust
        ],
    },
    ("Vehicles", "Ace Combat"): {
        "shape_concept": "single-seat fighter side profile: nose, canopy, single tail",
        "stars": [
            (-0.85,  0.10), (-0.30,  0.20), ( 0.30,  0.30), ( 0.85,  0.10),
            ( 0.55, -0.30),
        ],
    },
    ("Time", "Ace Combat"): {
        "shape_concept": "vapor trail across the sky: long curved arc",
        "stars": [
            (-0.85,  0.55), (-0.30,  0.20), ( 0.20, -0.10), ( 0.85, -0.55),
        ],
    },

    # ----- Devil May Cry (twin pistols + sword) -----------------------
    ("Crafting", "Devil May Cry"): {
        "shape_concept": "Ebony & Ivory crossed over Rebellion: twin pistols flanking a long sword",
        "stars": [
            # central sword (vertical)
            ( 0.00,  0.95), ( 0.00,  0.55), ( 0.00,  0.10), ( 0.00, -0.55),
            # crossguard
            (-0.30,  0.55), ( 0.30,  0.55),
            # twin pistol barrels (lower flanks)
            (-0.85, -0.30), (-0.55, -0.10),
            ( 0.85, -0.30), ( 0.55, -0.10),
        ],
    },

    # ----- Asura's Wrath (six-armed warrior + halo) -------------------
    ("Capstone", "Asura's Wrath"): {
        "shape_concept": "six-armed wrathful warrior: head with halo, six radiating arms",
        "stars": [
            ( 0.00,  0.85),                    # head
            ( 0.30,  0.95), (-0.30,  0.95),    # halo points
            (-0.85,  0.30), ( 0.85,  0.30),    # outer arms (top pair)
            (-0.85, -0.10), ( 0.85, -0.10),    # mid arms
            (-0.55, -0.55), ( 0.55, -0.55),    # lower arms
            ( 0.00, -0.85),                    # standing base
        ],
    },
    ("Knowledge", "Asura's Wrath"): {
        "shape_concept": "celestial scripture: three glyph-stars in a row",
        "stars": [(-0.55, 0.0), (0.0, 0.0), (0.55, 0.0)],
    },

    # ----- Zoids: Legacy ----------------------------------------------
    ("Size", "Zoids: Legacy"): {
        "shape_concept": "quadrupedal mecha-beast: four legs, low body, raised tail",
        "stars": [
            (-0.85, -0.55), (-0.30, -0.85),    # left legs
            ( 0.30, -0.85), ( 0.85, -0.55),    # right legs
            (-0.55,  0.10), ( 0.55,  0.10),    # body
            ( 0.85,  0.45),                    # raised tail/head
        ],
    },

    # ----- RWBY (crossed weapons) -------------------------------------
    ("Size", "RWBY"): {
        "shape_concept": "crossed scythe and dust crystal: long blade-arc with a faceted shard",
        "stars": [
            (-0.85,  0.55), (-0.30,  0.10), ( 0.30, -0.30), ( 0.85, -0.55),  # scythe arc
            ( 0.30,  0.55), ( 0.55,  0.30), ( 0.55,  0.85),                  # dust shard
        ],
    },
    ("Capstone", "RWBY"): {
        "shape_concept": "huntress emblem: four-petal rose abstract",
        "stars": [( 0.0,  0.55), ( 0.55, 0.0), ( 0.0, -0.55), (-0.55, 0.0), (0.0, 0.0)],
    },

    # ----- Macross (Veritech transforming jet) ------------------------
    ("Toolkits", "Macross"): {
        "shape_concept": "Veritech jet/battloid hybrid: wings folded with humanoid head and arms",
        "stars": [
            ( 0.00,  0.85),                    # head/sensor
            (-0.30,  0.55), ( 0.30,  0.55),    # shoulder wings
            (-0.85,  0.20), ( 0.85,  0.20),    # wing tips
            (-0.30, -0.10), ( 0.30, -0.10),    # arms/missiles
            (-0.20, -0.55), ( 0.20, -0.55),    # legs / engines
            ( 0.00, -0.85),                    # exhaust
        ],
    },
    ("Quality", "Macross"): {
        "shape_concept": "stage spotlight: idol mic with sound-wave arcs",
        "stars": [(0.0, 0.85), (0.0, 0.30), (-0.55, 0.0), (0.55, 0.0)],
    },
    ("Vehicles", "Macross"): {
        "shape_concept": "guardian-mode fighter mid-transform: low silhouette",
        "stars": [(-0.55, 0.0), (0.0, 0.30), (0.55, 0.0)],
    },
    ("Capstone", "Macross"): {
        "shape_concept": "love-and-music heart of the Galaxy: single bright star",
        "stars": [(0.0, 0.0)],
    },
    ("Time", "Macross"): {
        "shape_concept": "fold-jump streak across space",
        "stars": [(-0.55, 0.30), (0.55, -0.30)],
    },

    # ----- The World Ends With You (pin badges) -----------------------
    ("Quality", "The World Ends With You"): {
        "shape_concept": "cluster of psych pins arranged on a player's pin board",
        "stars": [
            (-0.55,  0.55), ( 0.55,  0.55), (-0.55, -0.55), ( 0.55, -0.55),
            ( 0.00,  0.00),
        ],
    },
    ("Clothing", "The World Ends With You"): {
        "shape_concept": "Shibuya-fashion outfit: layered tee + cap silhouette",
        "stars": [(0.0, 0.85), (-0.55, 0.0), (0.55, 0.0)],
    },

    # ----- Monster Hunter (great-sword silhouette) --------------------
    ("Magic", "Monster Hunter"): {
        "shape_concept": "great sword silhouette: massive blade tapering from wide tip to narrow grip",
        "stars": [
            ( 0.00,  0.95),                    # tip
            (-0.30,  0.30), ( 0.30,  0.30),    # blade upper edges
            (-0.20, -0.30), ( 0.20, -0.30),    # blade lower edges
            ( 0.00, -0.55),                    # grip
        ],
    },
    ("Resources and Durability", "Monster Hunter"): {
        "shape_concept": "armor pauldron: two-tier curved shoulder guard",
        "stars": [(-0.55, 0.30), (0.55, 0.30), (-0.30, -0.30), (0.30, -0.30)],
    },

    # ----- Fate Servant Supplement (heroic spirit class triangle) -----
    ("Crafting", "Fate Servant Supplement"): {
        "shape_concept": "command seal triskelion: three radiating spurs around a center",
        "stars": [
            ( 0.00,  0.85), ( 0.75, -0.45), (-0.75, -0.45),    # three spurs
            ( 0.00,  0.30), ( 0.30, -0.15), (-0.30, -0.15),    # inner echo
        ],
    },
    ("Alchemy", "Fate"): {
        "shape_concept": "summoning circle fragment: three points of a magical seal",
        "stars": [(-0.55, -0.30), (0.55, -0.30), (0.0, 0.55)],
    },
    ("Alchemy", "Fate/"): {
        "shape_concept": "extension of the Fate summoning sigil: paired arcs",
        "stars": [(-0.55, 0.0), (0.55, 0.0)],
    },

    # ----- Robot Unicorn Attack (rainbow + horn) ---------------------
    ("Crafting", "Robot Unicorn Attack"): {
        "shape_concept": "rainbow arc with a unicorn horn poking through the apex",
        "stars": [
            (-0.85,  0.20), (-0.55,  0.55), ( 0.00,  0.75), ( 0.55,  0.55), ( 0.85,  0.20),  # arc
            ( 0.00,  0.95),                                                                   # horn tip
        ],
    },

    # ----- Titanfall (titan stomp + pilot) ----------------------------
    ("Vehicles", "Titanfall"): {
        "shape_concept": "Titan mech standing tall: blocky head, broad chest, two stride-legs",
        "stars": [
            ( 0.00,  0.85),                    # head
            (-0.55,  0.45), ( 0.55,  0.45),    # shoulders
            (-0.30,  0.10), ( 0.30,  0.10),    # hip joints
            (-0.30, -0.55), ( 0.30, -0.55),    # legs
            ( 0.00, -0.85),                    # ground impact
        ],
    },

    # ----- Akame ga Kill (long blade) ---------------------------------
    ("Quality", "Akame ga Kill"): {
        "shape_concept": "Murasame-style long sword: thin straight blade with single hilt and pommel",
        "stars": [
            ( 0.85,  0.85), ( 0.55,  0.55), ( 0.00,  0.00), (-0.55, -0.55), (-0.85, -0.85),
        ],
    },

    # ----- Lord of Light (chakra wheel) -------------------------------
    ("Quality", "Lord of Light"): {
        "shape_concept": "chakra wheel: hub with five spokes radiating outward",
        "stars": [
            ( 0.00,  0.00),                    # hub
            ( 0.00,  0.85),
            ( 0.80,  0.30), ( 0.55, -0.65),
            (-0.55, -0.65), (-0.80,  0.30),
        ],
    },
    ("Knowledge", "Lord of Light"): {
        "shape_concept": "scripture columns: two parallel verticals",
        "stars": [(-0.30, 0.55), (-0.30, -0.55), (0.30, 0.55), (0.30, -0.55)],
    },
    ("Personal Reality", "Lord of Light"): {
        "shape_concept": "hermit's cell: single bright star at center",
        "stars": [(0.0, 0.0)],
    },
    ("Resources and Durability", "Lord of Light"): {
        "shape_concept": "deva's shield: small inverted triangle",
        "stars": [(-0.45, 0.30), (0.45, 0.30), (0.0, -0.40)],
    },

    # ----- God of War (chained blade) ---------------------------------
    ("Quality", "God of War"): {
        "shape_concept": "Blade of Chaos: short blade with chain trailing back",
        "stars": [
            ( 0.85,  0.55), ( 0.55,  0.20),                # blade
            ( 0.20,  0.00), (-0.20, -0.20),                # chain links
            (-0.55, -0.40), (-0.85, -0.55),                # haft / handle
        ],
    },
    ("Toolkits", "God of War"): {
        "shape_concept": "smith's chain hook",
        "stars": [( 0.0, 0.55), (-0.30, 0.0), (0.30, 0.0), (0.0, -0.55)],
    },
    ("Resources and Durability", "God of War"): {
        "shape_concept": "Spartan circular shield",
        "stars": [(0.0, 0.55), (0.55, 0.0), (0.0, -0.55), (-0.55, 0.0)],
    },
    ("Capstone", "God of War"): {
        "shape_concept": "throne of Olympus: tall single peak",
        "stars": [(0.0, 0.85)],
    },

    # ----- Big O (giant mecha) ----------------------------------------
    ("Vehicles", "Big O"): {
        "shape_concept": "Big-Bot-style megadeus: blocky head + two enormous fists at sides",
        "stars": [
            ( 0.00,  0.85),                    # head
            (-0.55,  0.30), ( 0.55,  0.30),    # shoulders
            (-0.85, -0.30), ( 0.85, -0.30),    # massive fists
            ( 0.00,  0.00),                    # chest core
        ],
    },

    # ----- Fullmetal Alchemist (transmutation circle) -----------------
    ("Alchemy", "Fullmetal Alchemist"): {
        "shape_concept": "transmutation circle: outer ring with inscribed triangle",
        "stars": [
            ( 0.00,  0.85), ( 0.74, -0.42), (-0.74, -0.42),    # triangle vertices
            ( 0.00,  0.00),                                    # center
        ],
    },
    ("Alchemy", "Full Metal Alchemist"): {
        "shape_concept": "alternate spelling — same transmutation circle",
        "stars": [
            ( 0.00,  0.85), ( 0.74, -0.42), (-0.74, -0.42), ( 0.00,  0.00),
        ],
    },

    # ----- Fallen London (umbrella + lamppost) ------------------------
    ("Toolkits", "Fallen London"): {
        "shape_concept": "Neath umbrella + lamppost: parasol arc with a bright lamp atop a pole",
        "stars": [
            (-0.55,  0.30), ( 0.00,  0.55), ( 0.55,  0.30),    # umbrella ribs
            ( 0.00,  0.20), ( 0.00, -0.55),                    # umbrella shaft
        ],
    },
    ("Clothing", "Fallen London"): {
        "shape_concept": "Victorian top hat and cane",
        "stars": [
            (-0.30,  0.55), ( 0.30,  0.55), (-0.30,  0.10), ( 0.30,  0.10),    # hat
            ( 0.00,  0.85),                                                    # crown
            ( 0.55, -0.85),                                                    # cane tip
        ],
    },

    # ----- Stargate SG-1 (the ring) -----------------------------------
    ("Knowledge", "Stargate SG-1"): {
        "shape_concept": "ring of chevrons: seven evenly spaced glyphs on a circle",
        "stars": [
            *[ (math.cos(i * 2 * math.pi / 7) * 0.85, math.sin(i * 2 * math.pi / 7) * 0.85)
               for i in range(7) ],
        ],
    },

    # ----- Red Faction (mining drill) ---------------------------------
    ("Size", "Red Faction"): {
        "shape_concept": "diamond drill bit: triangular point with bolted base",
        "stars": [
            ( 0.00,  0.85), (-0.30,  0.30), ( 0.30,  0.30),    # bit point
            (-0.55, -0.20), ( 0.55, -0.20),                    # mid
            (-0.85, -0.55), ( 0.85, -0.55),                    # base flange
        ],
    },

    # ----- Worm (mask outline) ----------------------------------------
    ("Size", "Worm"): {
        "shape_concept": "cape mask: insectile faceplate, eye-lens slits, mandible chevron",
        "stars": [
            (-0.55,  0.55), ( 0.55,  0.55),    # mask top corners
            (-0.65,  0.10), ( 0.65,  0.10),    # outer mandibles
            (-0.30,  0.20), ( 0.30,  0.20),    # eye lenses
            ( 0.00, -0.55),                    # chin point
        ],
    },

    # ----- Strike Witches (twin propellers) ---------------------------
    ("Toolkits", "Strike Witches"): {
        "shape_concept": "striker unit: twin leg-mounted propellers, each a 3-blade arrangement",
        "stars": [
            (-0.55,  0.55), (-0.85,  0.10), (-0.55, -0.30),    # left prop
            ( 0.55,  0.55), ( 0.85,  0.10), ( 0.55, -0.30),    # right prop
        ],
    },
    ("Knowledge", "Strike Witches"): {
        "shape_concept": "single propeller hub seen edge-on",
        "stars": [(0.0, 0.55), (0.0, 0.0), (0.0, -0.55)],
    },

    # ----- Bayonetta (gun-heels + glasses) ----------------------------
    ("Quality", "Bayonetta"): {
        "shape_concept": "stiletto with gun-barrel heel: high heel silhouette with muzzle accent",
        "stars": [(-0.55, 0.55), (0.0, 0.30), (0.55, 0.10), (0.30, -0.55)],
    },

    # ----- Gundam (mobile suit head + shoulders) ----------------------
    ("Vehicles", "Gundam UC"): {
        "shape_concept": "mobile-suit head: V-fin antenna + dual eye lenses",
        "stars": [(0.0, 0.85), (-0.30, 0.55), (0.30, 0.55), (-0.30, 0.30), (0.30, 0.30)],
    },
    ("Quality", "Gundam: After Colony"): {
        "shape_concept": "Gundanium wings: paired flaring V on either side",
        "stars": [(-0.85, 0.55), (-0.30, 0.30), (0.30, 0.30), (0.85, 0.55)],
    },

    # ----- Bloody Roar (claw rake) ------------------------------------
    ("Toolkits", "Bloody Roar"): {
        "shape_concept": "beast claw rake: three parallel slash marks",
        "stars": [(-0.55, 0.55), (-0.55, -0.55), (0.0, 0.55), (0.0, -0.55), (0.55, 0.55), (0.55, -0.55)],
    },

    # ----- Tales of Symphonia (summon spirit star) --------------------
    ("Magic", "Tales of Symphonia"): {
        "shape_concept": "summon spirit pentacle: five-point star",
        "stars": [
            *[ (math.cos((i * 4 * math.pi / 5) + math.pi/2) * 0.85,
                math.sin((i * 4 * math.pi / 5) + math.pi/2) * 0.85)
               for i in range(5) ],
        ],
    },

    # ----- No More Heroes (beam katana) -------------------------------
    ("Toolkits", "No More Heroes"): {
        "shape_concept": "beam katana: long luminous diagonal with hilt knot",
        "stars": [(-0.85, -0.85), (-0.20, -0.20), (0.55, 0.55), (0.85, 0.85)],
    },

    # ----- Sabaton (the toolkit drum + mic) ---------------------------
    ("Resources and Durability", "Sabaton"): {
        "shape_concept": "stage-rig: drum kit dot pattern with overhead mic",
        "stars": [(0.0, 0.85), (-0.30, 0.0), (0.30, 0.0), (0.0, -0.55)],
    },
    ("Toolkits", "Sabaton"): {
        "shape_concept": "the toolkit itself: small clustered tools",
        "stars": [(0.0, 0.0)],
    },

    # ----- Skies of Arcadia (airship + crow's nest) -------------------
    ("Knowledge", "Skies of Arcadia"): {
        "shape_concept": "airship hull: long pointed prow with sail and crow's nest",
        "stars": [(0.85, 0.0), (0.30, 0.10), (-0.30, 0.10), (-0.85, 0.10), (0.0, 0.55), (0.0, 0.85)],
    },

    # ----- Borderlands (loot crate explosion) -------------------------
    ("Quality", "Borderlands"): {
        "shape_concept": "open loot box with three loot beams shooting up",
        "stars": [(-0.55, -0.55), (0.55, -0.55), (-0.30, 0.55), (0.0, 0.85), (0.30, 0.55)],
    },
    ("Magic", "Borderlands"): {
        "shape_concept": "elemental shot: streak with impact splash",
        "stars": [(-0.55, -0.55), (0.0, 0.0), (0.55, 0.55)],
    },
    ("Crafting", "Borderlands"): {
        "shape_concept": "weapon-mod chip: small square",
        "stars": [(-0.30, 0.30), (0.30, 0.30), (-0.30, -0.30), (0.30, -0.30)],
    },

    # ----- Megaman Zero (saber arc) -----------------------------------
    ("Resources and Durability", "Megaman Zero"): {
        "shape_concept": "Z-saber arc: curved energy slash",
        "stars": [(-0.85, -0.30), (-0.30, 0.30), (0.30, 0.55), (0.85, 0.30)],
    },

    # ----- Light of Terra (Imperial battleship) -----------------------
    ("Crafting", "Light of Terra DLC 5 A Sky Filled With Steel - Warhammer 40,000"): {
        "shape_concept": "Imperial battleship prow: long dagger profile",
        "stars": [(-0.85, 0.0), (-0.30, 0.10), (0.30, 0.0), (0.85, -0.10)],
    },

    # ----- Endless Legend (faction banner) ----------------------------
    ("Toolkits", "Endless Legend"): {
        "shape_concept": "civilization banner: rectangular sigil with corner studs",
        "stars": [(-0.55, 0.55), (0.55, 0.55), (-0.55, -0.55), (0.55, -0.55), (0.0, 0.0)],
    },

    # ----- Atelier: Arland Trilogy (cauldron + ingredients) -----------
    ("Toolkits", "Atelier: Arland Trilogy"): {
        "shape_concept": "alchemist's cauldron with ingredient stars circling above",
        "stars": [
            (-0.55, -0.30), (0.55, -0.30), (0.0, -0.85),    # cauldron
            (-0.55, 0.55), (0.0, 0.85), (0.55, 0.55),       # ingredients overhead
        ],
    },

    # ----- Final Fantasy XIV (crystal of light) -----------------------
    ("Magitech", "Final Fantasy XIV"): {
        "shape_concept": "elemental crystal cluster: hex-prism arrangement",
        "stars": [
            (0.0, 0.85), (0.55, 0.30), (0.55, -0.30), (0.0, -0.85), (-0.55, -0.30), (-0.55, 0.30),
            (0.0, 0.0),
        ],
    },
    ("Resources and Durability", "Final Fantasy XIV"): {
        "shape_concept": "tank shield: round disc with quartered cross",
        "stars": [(0.0, 0.55), (0.55, 0.0), (0.0, -0.55), (-0.55, 0.0), (0.0, 0.0)],
    },

    # ----- Worm/Fast and Furious / Cars -------------------------------
    ("Toolkits", "Fast and Furious"): {
        "shape_concept": "muscle-car profile: low roofline, hood, four wheels",
        "stars": [(-0.85, -0.55), (-0.30, -0.55), (0.30, -0.55), (0.85, -0.55), (-0.30, 0.30), (0.30, 0.30)],
    },
    ("Vehicles", "Fast and Furious"): {
        "shape_concept": "drag-strip silhouette: chassis with rear spoiler",
        "stars": [(-0.85, -0.30), (0.85, -0.30), (0.55, 0.30)],
    },
    ("Time", "Fast and Furious"): {
        "shape_concept": "stopwatch: single bright tick",
        "stars": [(0.0, 0.0)],
    },

    # ----- Mass Effect (Normandy frigate) -----------------------------
    ("Knowledge", "Mass Effect"): {
        "shape_concept": "Normandy frigate: pointed prow, swept wings, twin engines",
        "stars": [(0.0, 0.85), (-0.55, 0.0), (0.55, 0.0), (-0.30, -0.55), (0.30, -0.55), (0.0, -0.85)],
    },
    ("Toolkits", "Mass Effect"): {
        "shape_concept": "omni-tool flare: tight bright cluster",
        "stars": [(-0.20, 0.20), (0.20, 0.20), (0.0, -0.20)],
    },

    # ----- Splatoon (paint splat) -------------------------------------
    ("Clothing", "Splatoon"): {
        "shape_concept": "paint splat: irregular blob with droplet outliers",
        "stars": [(-0.55, 0.30), (0.30, 0.55), (0.55, -0.30), (-0.30, -0.55), (0.85, 0.85)],
    },

    # ----- Kill la Kill (life-fiber thread) ---------------------------
    ("Clothing", "Kill la Kill"): {
        "shape_concept": "life-fiber thread woven into a single eye-emblem",
        "stars": [(0.0, 0.55), (0.55, 0.0), (0.0, -0.55), (-0.55, 0.0), (0.0, 0.0)],
    },

    # ----- Skyrim (dragon shout) --------------------------------------
    ("Toolkits", "The Elder Scrolls: Skyrim"): {
        "shape_concept": "dragon's roar wave: chevron of three diverging stars",
        "stars": [(-0.55, 0.30), (0.0, 0.0), (0.55, 0.30), (0.0, -0.55)],
    },

    # ----- XCOM ------------------------------------------------------
    ("Knowledge", "XCOM 2"): {
        "shape_concept": "tactical squad: four troopers in a line",
        "stars": [(-0.85, 0.0), (-0.30, 0.0), (0.30, 0.0), (0.85, 0.0)],
    },
    ("Magic", "XCOM 2"): {
        "shape_concept": "psi-amp pulse",
        "stars": [(0.0, 0.55), (0.0, -0.55)],
    },
    ("Resources and Durability", "XCOM"): {
        "shape_concept": "kevlar plate: small horizontal rectangle",
        "stars": [(-0.55, 0.10), (0.55, 0.10), (-0.55, -0.10), (0.55, -0.10)],
    },
    ("Time", "XCOM"): {
        "shape_concept": "geoscape rotation: arc of two ticks",
        "stars": [(-0.30, 0.30), (0.30, -0.30)],
    },
    ("Crafting", "XCOM"): {
        "shape_concept": "engineering bench: single workbench star",
        "stars": [(0.0, 0.0)],
    },

    # ----- Lord of the Rings -----------------------------------------
    ("Crafting", "Lord of the Rings"): {
        "shape_concept": "elven smithing: ring with inscription mark",
        "stars": [(0.0, 0.55), (0.55, 0.0), (0.0, -0.55), (-0.55, 0.0)],
    },
    ("Magic", "Lord of the Rings"): {
        "shape_concept": "wizard's staff",
        "stars": [(0.0, 0.85), (0.0, -0.85)],
    },

    # ----- Star Wars Clone Wars --------------------------------------
    ("Vehicles", "Star Wars - Clone Wars"): {
        "shape_concept": "starfighter: stubby wings, central cockpit",
        "stars": [(-0.55, 0.30), (0.55, 0.30), (0.0, 0.0), (-0.55, -0.30), (0.55, -0.30)],
    },

    # ----- Marvel Cinematic Universe ----------------------------------
    ("Knowledge", "Marvel Cinematic Universe"): {
        "shape_concept": "infinity stones cluster: six bright stars in a hex",
        "stars": [
            (0.0, 0.85), (0.74, 0.42), (0.74, -0.42),
            (0.0, -0.85), (-0.74, -0.42), (-0.74, 0.42),
        ],
    },

    # ----- Castlevania (whip arc) -------------------------------------
    ("Alchemy", "Castlevania"): {
        "shape_concept": "Vampire Killer whip: lashing arc",
        "stars": [(-0.85, 0.55), (-0.30, 0.30), (0.30, -0.30), (0.85, -0.55)],
    },

    # ----- Firefly (cargo hauler) -------------------------------------
    ("Knowledge", "Firefly"): {
        "shape_concept": "Serenity-class hauler: bulbous head, twin engine pods",
        "stars": [(0.0, 0.55), (-0.55, -0.30), (0.55, -0.30), (0.0, -0.10)],
    },

    # ----- Gurren Lagann (drill spiral) -------------------------------
    ("Vehicles", "Gurren Lagann"): {
        "shape_concept": "spiral drill: tight inner-to-outer arc",
        "stars": [(0.0, 0.0), (0.30, 0.0), (0.30, -0.30), (-0.30, -0.30), (-0.55, 0.30), (0.55, 0.55)],
    },
    ("Quality", "Gurren Lagann"): {
        "shape_concept": "fightin' shades: paired triangle lenses",
        "stars": [(-0.55, 0.0), (-0.20, 0.30), (0.20, 0.30), (0.55, 0.0)],
    },

    # ----- Generator Rex (nanite swarm) -------------------------------
    ("Size", "Generator Rex"): {
        "shape_concept": "nanite cluster: tight loose-knot of three points",
        "stars": [(-0.30, 0.30), (0.30, 0.30), (0.0, -0.40)],
    },

    # ----- Banjo-Kazooie (jiggy) --------------------------------------
    ("Alchemy", "Banjo-Kazooie"): {
        "shape_concept": "jigsaw piece (jiggy): four-tab puzzle outline",
        "stars": [(0.0, 0.85), (-0.85, 0.0), (0.85, 0.0), (0.0, -0.85)],
    },

    # ----- Senki Zesshou Symphogear (sound waves) ---------------------
    ("Magic", "Senki Zesshou Symphogear"): {
        "shape_concept": "battle-song wave: paired arcs",
        "stars": [(-0.55, 0.30), (0.55, 0.30)],
    },

    # ----- Harry Potter (wand spark) ----------------------------------
    ("Magitech", "Harry Potter"): {
        "shape_concept": "wand with spell spark: line plus radiating mini-stars",
        "stars": [(-0.55, -0.55), (0.30, 0.30), (0.55, 0.55), (0.85, 0.85)],
    },

    # ----- Sonic the Hedgehog (loop-de-loop) --------------------------
    ("Time", "Sonic The Hedgehog"): {
        "shape_concept": "loop-de-loop track: vertical oval",
        "stars": [(0.0, 0.55), (0.30, 0.0), (0.0, -0.55), (-0.30, 0.0)],
    },

    # ----- Dune (sandworm trail) --------------------------------------
    ("Quality", "Dune"): {
        "shape_concept": "sandworm trail: undulating ridge",
        "stars": [(-0.85, -0.30), (-0.30, 0.30), (0.30, -0.30), (0.85, 0.30)],
    },
    ("Resources and Durability", "Dune"): {
        "shape_concept": "spice cache: single dune-peak",
        "stars": [(0.0, 0.0)],
    },
}


# ---------------------------------------------------------------------------
# Procedural fallback shape generators (long-tail jumps)
# ---------------------------------------------------------------------------

def procedural_shape(perk_count: int, seed: int) -> tuple[list[tuple[float, float]], str]:
    """Pick a generic shape based on perk count.

    1 perk    → single bright dot at center
    2 perks   → short line
    3 perks   → triangle
    4 perks   → rhombus / kite
    5+ perks  → small pseudo-random cluster around a circle, deterministic per seed
    """
    if perk_count <= 1:
        return [(0.0, 0.0)], "generic / unspecified: single anchor star"
    if perk_count == 2:
        return [(-0.55, 0.0), (0.55, 0.0)], "generic / unspecified: short line"
    if perk_count == 3:
        return [(0.0, 0.65), (-0.55, -0.40), (0.55, -0.40)], "generic / unspecified: triangle"
    if perk_count == 4:
        return [(0.0, 0.65), (0.65, 0.0), (0.0, -0.65), (-0.65, 0.0)], "generic / unspecified: rhombus"
    # 5+ perks: even circle with a deterministic tiny perturbation per slot
    pts: list[tuple[float, float]] = []
    rng = _DeterministicJitter(seed)
    for i in range(perk_count):
        a = i * 2 * math.pi / perk_count
        r = 0.7 + rng.next() * 0.15
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts, "generic / unspecified: irregular ring cluster"


class _DeterministicJitter:
    """Tiny self-contained linear-congruential generator so we don't
    depend on Python's random global state and the output stays
    byte-stable across runs and Python versions."""

    def __init__(self, seed: int) -> None:
        # constants from Numerical Recipes; perfectly fine for visual jitter
        self.state = (seed * 1664525 + 1013904223) & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (self.state * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


# ---------------------------------------------------------------------------
# Cost → star size mapping
# ---------------------------------------------------------------------------

def cost_to_size(cost: int | None) -> float:
    """100 → small, 800+ → ~1.0. Free / null perks treated as smallest.
    Uses a smooth log-ish ramp so 100 and 200 stay visually distinct
    but 600 vs 800 don't crowd the top."""
    if cost is None or cost <= 0:
        return 0.20
    # clamp to [50, 900] then sqrt scale
    c = max(50, min(900, cost))
    # 100 → ~0.32, 200 → ~0.46, 400 → ~0.66, 600 → ~0.80, 800 → ~0.94
    return round(math.sqrt(c / 900.0), 4)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def assign_to_slots(
    items: list,
    slots: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Place items onto the slot list in given order.

    If items > slots, extras tile around an outer micro-spiral so
    nothing is dropped. If items < slots, extra slots are simply
    unused (we don't pad with phantom items)."""
    placed = list(slots[: len(items)])
    extras = len(items) - len(slots)
    if extras > 0:
        # spiral outward from radius 1.05 in 25-degree steps
        for k in range(extras):
            angle = math.radians(15 + 25 * k)
            radius = 1.05 + 0.04 * k
            placed.append((radius * math.cos(angle), radius * math.sin(angle)))
    return placed


def build_jump_constellation(
    constellation: str,
    jump: str,
    perks: list[dict],
) -> dict:
    """Construct one per-jump entry. Each perk is the directory entry
    dict (we read its name/cost/status/acquired_*/instances). Sort by
    descending cost so the biggest stars land on the most-defining
    anchor points of the hand-designed shape; ties broken by name."""
    perks_sorted = sorted(
        perks,
        key=lambda p: (-(p.get("cost") or 0), p.get("name", "")),
    )
    key = (constellation, jump)
    if key in JUMP_SHAPES:
        spec = JUMP_SHAPES[key]
        slots = spec["stars"]
        concept = spec["shape_concept"]
    else:
        seed = sum(ord(c) for c in f"{constellation}|{jump}") + len(perks_sorted)
        slots, concept = procedural_shape(len(perks_sorted), seed)

    coords = assign_to_slots(perks_sorted, slots)
    stars = [
        {
            "id": p["id"],
            "perk_name": p["name"],
            "cost": p.get("cost"),
            "size": cost_to_size(p.get("cost")),
            "x": round(x, 4),
            "y": round(y, 4),
            "status": p["status"],
            "acquired_chapter_num": p.get("acquired_chapter_num"),
            "acquired_epub_sequence": p.get("acquired_epub_sequence"),
            "instances_count": max(1, len(p.get("acquired_instances", []))),
        }
        for p, (x, y) in zip(perks_sorted, coords)
    ]
    return {
        "constellation": constellation,
        "jump": jump,
        "shape_concept": concept,
        "stars": stars,
    }


# ---------------------------------------------------------------------------
# Cluster constellation assembly
# ---------------------------------------------------------------------------

CLUSTER_ORDER = [
    "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
    "Clothing", "Magic", "Quality", "Size",
    "Resources and Durability", "Magitech", "Alchemy",
    "Capstone", "Personal Reality",
]


def build_cluster_constellation(
    name: str,
    extracted: dict,
    lifecycle: dict,
) -> dict:
    """Assemble one cluster_constellations[] entry from the hand-authored
    SVG geometry (via extract_constellation_svgs) and the lifecycle facts."""
    return {
        "name": name,
        "slug": extracted["slug"],
        "slot_position": lifecycle["slot_position"],
        "shape_concept": extracted["intended_image"],
        "vertex_source": extracted["vertex_source"],
        "revealed_at_chapter":     lifecycle.get("revealed_at_chapter"),
        "completed_at_chapter":    lifecycle.get("completed_at_chapter"),
        "entered_pool_at_chapter": lifecycle.get("entered_pool_at_chapter"),
        "marker_positions": extracted["marker_positions"],
        "silhouette":       extracted["silhouette"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    directory = json.loads(DIRECTORY.read_text())["perks"]

    # (constellation, normalized jump) -> list of directory entries
    by_jump: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in directory:
        if not p["constellation"] or not p["jump"]:
            continue
        # Felyne Perks isn't in the 14-cluster enum — skip; the schema's
        # cluster constellation enum doesn't include it.
        if p["constellation"] == "Felyne Perks":
            continue
        key = (p["constellation"], norm_jump(p["jump"]))
        by_jump[key].append(p)

    # Build per-jump entries (unchanged from the prior hand-designed/procedural
    # mini-constellation pipeline).
    jump_entries = [
        build_jump_constellation(c, j, perks)
        for (c, j), perks in sorted(by_jump.items())
    ]

    # ------------------------------------------------------------------
    # Build cluster entries from hand-curated SVGs + lifecycle facts.
    # ------------------------------------------------------------------
    extracted = extract_constellation_svgs(CONSTELLATIONS_DIR)
    lifecycle_doc = json.loads(LIFECYCLE.read_text())
    lifecycle_by_name = {c["name"]: c for c in lifecycle_doc["constellations"]}

    missing_extracted = [n for n in CLUSTER_ORDER if n not in extracted]
    missing_lifecycle = [n for n in CLUSTER_ORDER if n not in lifecycle_by_name]
    if missing_extracted or missing_lifecycle:
        print(
            "ERROR: build_constellation_wireframes: missing constellations\n"
            f"  not in extractor:  {missing_extracted}\n"
            f"  not in lifecycle:  {missing_lifecycle}",
            file=sys.stderr,
        )
        sys.exit(1)

    cluster_entries = [
        build_cluster_constellation(
            name,
            extracted[name],
            lifecycle_by_name[name],
        )
        for name in CLUSTER_ORDER
    ]

    payload = {
        "schema_version": 2,
        "_source": (
            "data/constellations/NN-<slug>/current.svg + metadata.json "
            "(hand-curated geometry); data/derived/constellation_lifecycle.json "
            "(reveal/completion/pool); data/derived/perk_directory.json "
            "(per-jump star patterns)"
        ),
        "_count": len(cluster_entries),
        "_jumps_count": len(jump_entries),
        "_note": (
            "Two-level wireframe model. cluster_constellations[i] is one "
            "of the 14 named constellations: geometry (marker_positions + "
            "silhouette polylines) comes from the hand-authored SVG at "
            "data/constellations/NN-<slug>/current.svg, normalized to the "
            "[0,1] unit square via the 320-px viewBox. shape_concept is "
            "the constellation's intended_image string from its "
            "metadata.json sidecar. vertex_source records whether the "
            "marker count was hand-aligned against jumps or perks. "
            "Lifecycle fields (revealed/completed/pool) are carried over "
            "from constellation_lifecycle.json so the renderer can fog/"
            "unfog the constellation as the scrubber moves through time. "
            "jump_constellations is a per-jump star pattern themed by the "
            "source media (abstract, never a literal logo); stars are "
            "EVERY perk in the jump (acquired or not), size encodes cost "
            "on a sqrt ramp (100=>~0.33, 800=>~0.94, null/free=>0.20). "
            "Each star carries its directory id, status, and "
            "acquired_chapter_num so the renderer can fog/unfog as the "
            "scrubber moves through time."
        ),
        "cluster_constellations": cluster_entries,
        "jump_constellations": jump_entries,
    }

    write_validated_json(OUT, payload, "constellation_wireframes")

    # Summary stats
    handcrafted = sum(
        1 for entry in jump_entries
        if (entry["constellation"], entry["jump"]) in JUMP_SHAPES
    )
    procedural = len(jump_entries) - handcrafted
    total_stars = sum(len(e["stars"]) for e in jump_entries)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  clusters:           {len(cluster_entries)}")
    print(f"  jumps total:        {len(jump_entries)}")
    print(f"  jumps hand-designed: {handcrafted}")
    print(f"  jumps procedural:    {procedural}")
    print(f"  total stars:        {total_stars}")


if __name__ == "__main__":
    main()

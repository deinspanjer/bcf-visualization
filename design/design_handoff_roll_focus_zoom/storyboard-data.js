/* eslint-disable */
// Storyboard scene data and scenario configurations.
// World space is 1600 x 1000 (matches the 16:10 frame aspect).
// Cluster silhouette + markers (which arrive in [0,1] from constellation_wireframes.json)
// are scaled into a 600x600 region centered at world (800, 500).
//
// CLUSTER_SCALE / CLUSTER_OFFSET map [0,1] cluster-local coords -> world.
// For a marker at cluster-local (mx, my):
//   world_x = CLUSTER_OFFSET_X + mx * CLUSTER_SCALE
//   world_y = CLUSTER_OFFSET_Y + my * CLUSTER_SCALE
//
// Jump-interior perks (which arrive in [-1, 1] for x, y from jump_constellations)
// are mapped around their cluster anchor with JUMP_RADIUS world-units.

const CLUSTER_SCALE = 620;
const CLUSTER_OFFSET_X = 800 - CLUSTER_SCALE / 2;   // 490
const CLUSTER_OFFSET_Y = 500 - CLUSTER_SCALE / 2;   // 190
const JUMP_RADIUS = 70;

function clusterToWorld([mx, my]) {
  return [CLUSTER_OFFSET_X + mx * CLUSTER_SCALE, CLUSTER_OFFSET_Y + my * CLUSTER_SCALE];
}
function jumpPerkToWorld(anchor, star, radius = JUMP_RADIUS) {
  return [anchor[0] + (star.x || 0) * radius, anchor[1] - (star.y || 0) * radius];
}

// --- shape data, extracted from data/derived/constellation_wireframes.json -----

const SHAPES = {
  Knowledge: {
    hue: 268,
    label: "Knowledge",
    vertex_source: "jumps",
    silhouette: [[[0.219,0.125],[0.219,0.906]],[[0.219,0.906],[0.5,0.969]],[[0.5,0.969],[0.781,0.906]],[[0.781,0.906],[0.781,0.125]],[[0.219,0.219],[0.125,0.188]],[[0.125,0.188],[0.125,0.281]],[[0.125,0.281],[0.031,0.25]],[[0.031,0.25],[0.031,0.906]],[[0.125,0.906],[0.125,0.281]],[[0.031,0.906],[0.5,0.969]],[[0.125,0.906],[0.5,0.969]],[[0.5,0.969],[0.875,0.906]],[[0.5,0.969],[0.969,0.906]],[[0.969,0.906],[0.969,0.25]],[[0.969,0.25],[0.875,0.281]],[[0.875,0.281],[0.875,0.188]],[[0.875,0.188],[0.781,0.219]],[[0.875,0.281],[0.875,0.906]],[[0.5,0.188],[0.5,0.969]],[[0.281,0.281],[0.438,0.313]],[[0.281,0.656],[0.438,0.688]],[[0.563,0.688],[0.719,0.656]],[[0.563,0.313],[0.719,0.281]],[[0.219,0.125],[0.5,0.188]],[[0.5,0.188],[0.781,0.125]],[[0.563,0.5],[0.719,0.469]],[[0.438,0.5],[0.281,0.469]]],
    markers: [[0.5,0.969],[0.5,0.188],[0.219,0.125],[0.781,0.125],[0.219,0.906],[0.781,0.906],[0.219,0.219],[0.781,0.219],[0.875,0.188],[0.125,0.188],[0.125,0.906],[0.875,0.906],[0.875,0.281],[0.969,0.25],[0.969,0.906],[0.125,0.281],[0.031,0.25],[0.031,0.906],[0.281,0.281],[0.438,0.313],[0.281,0.656],[0.438,0.688],[0.719,0.281],[0.563,0.313],[0.719,0.656],[0.563,0.688],[0.281,0.469],[0.438,0.5],[0.563,0.5],[0.719,0.469],[0.5,0.375],[0.5,0.625]],
  },
  Alchemy: {
    hue: 170,
    label: "Alchemy",
    vertex_source: "jumps",
    silhouette: [[[0.375,0.178],[0.625,0.178]],[[0.625,0.178],[0.6,0.228]],[[0.6,0.228],[0.6,0.478]],[[0.6,0.478],[0.725,0.628]],[[0.725,0.628],[0.825,0.878]],[[0.825,0.878],[0.5,0.878]],[[0.5,0.878],[0.175,0.878]],[[0.175,0.878],[0.275,0.628]],[[0.275,0.628],[0.4,0.478]],[[0.4,0.478],[0.4,0.228]],[[0.4,0.228],[0.375,0.178]]],
    markers: [[0.375,0.178],[0.5,0.878],[0.4,0.228],[0.625,0.178],[0.4,0.478],[0.6,0.228],[0.275,0.628],[0.725,0.628],[0.175,0.878],[0.825,0.878],[0.6,0.478]],
  },
  Clothing: {
    hue: 320,
    label: "Clothing",
    vertex_source: "perks",
    silhouette: [[[0.375,0.125],[0.625,0.125]],[[0.625,0.125],[0.688,0.219]],[[0.781,0.188],[0.688,0.219]],[[0.781,0.188],[0.781,0.5]],[[0.781,0.188],[0.906,0.438]],[[0.906,0.438],[0.781,0.5]],[[0.781,0.5],[0.781,0.875]],[[0.781,0.875],[0.188,0.875]],[[0.188,0.875],[0.188,0.5]],[[0.188,0.5],[0.094,0.438]],[[0.094,0.438],[0.188,0.219]],[[0.188,0.219],[0.188,0.5]],[[0.188,0.219],[0.313,0.219]],[[0.313,0.219],[0.5,0.313]],[[0.5,0.313],[0.688,0.219]],[[0.375,0.125],[0.313,0.219]]],
    markers: [[0.5,0.313],[0.313,0.219],[0.688,0.219],[0.188,0.219],[0.781,0.188],[0.094,0.438],[0.906,0.438],[0.188,0.5],[0.781,0.5],[0.375,0.125],[0.781,0.875],[0.188,0.875],[0.625,0.125]],
  },
  Size: {
    hue: 100,
    label: "Size",
    vertex_source: "perks",
    silhouette: [[[0.5,0.087],[0.198,0.334],[0.253,0.472],[0.308,0.609],[0.363,0.719],[0.418,0.829]],[[0.5,0.747],[0.5,0.619],[0.5,0.472],[0.5,0.307],[0.5,0.087]],[[0.5,0.747],[0.418,0.829]],[[0.5,0.747],[0.583,0.829]],[[0.583,0.829],[0.638,0.719]],[[0.638,0.719],[0.5,0.619]],[[0.5,0.619],[0.363,0.719]],[[0.308,0.609],[0.5,0.472]],[[0.5,0.307],[0.253,0.472]],[[0.5,0.087],[0.803,0.334]],[[0.803,0.334],[0.747,0.472]],[[0.747,0.472],[0.693,0.609]],[[0.693,0.609],[0.5,0.472]],[[0.747,0.472],[0.5,0.307]],[[0.693,0.609],[0.638,0.719]],[[0.5,0.087],[0.418,0.252]],[[0.5,0.087],[0.583,0.252]]],
    markers: [[0.5,0.087],[0.198,0.334],[0.253,0.472],[0.308,0.609],[0.363,0.719],[0.418,0.829],[0.5,0.747],[0.5,0.619],[0.5,0.472],[0.5,0.307],[0.583,0.829],[0.638,0.719],[0.803,0.334],[0.747,0.472],[0.693,0.609],[0.418,0.252],[0.583,0.252]],
  },
  Vehicles: {
    hue: 30,
    label: "Vehicles",
    vertex_source: "jumps",
    silhouette: [[[0.035,0.712],[0.035,0.567],[0.326,0.508],[0.384,0.392]],[[0.384,0.712],[0.646,0.712]],[[0.965,0.567],[0.965,0.712]],[[0.152,0.712],[0.035,0.712]],[[0.384,0.392],[0.733,0.392]],[[0.733,0.392],[0.965,0.567]],[[0.878,0.712],[0.965,0.712]]],
    markers: [[0.035,0.712],[0.035,0.567],[0.326,0.508],[0.384,0.392],[0.384,0.712],[0.646,0.712],[0.733,0.392],[0.965,0.567],[0.965,0.712],[0.268,0.683],[0.762,0.683],[0.152,0.712],[0.878,0.712]],
  },
};

// --- jump interior perks --------------------------------------------------

// Knowledge / Star Trek: TNG. The actual wireframe data has these 12 perks arranged on
// a perfect circle (it's the show's career-skills wheel) — for the storyboard we use
// scattered, organic positions so the cluster doesn't read as its own little
// constellation. When the real app pulls from constellation_wireframes.json it will use
// the data's positions; that's a design conversation for later.
const TNG_PERKS = [
  { name: "Skills: Combat",            x: 0.22, y:-0.18, cost: 100 },
  { name: "Skills: Communications",    x:-0.15, y: 0.32, cost: 100 },
  { name: "Skills: Engineering",       x: 0.00, y: 0.00, cost: 100 },   // <- focal (lives at the anchor point)
  { name: "Skills: Espionage",         x:-0.55, y: 0.62, cost: 100 },
  { name: "Skills: Medicine",          x: 0.48, y: 0.55, cost: 100 },
  { name: "Skills: Navigation",        x:-0.72, y:-0.15, cost: 100 },
  { name: "Skills: Physical Sciences", x: 0.62, y: 0.08, cost: 100 },
  { name: "Skills: Physics",           x:-0.32, y:-0.55, cost: 100 },
  { name: "Skills: Piloting",          x: 0.35, y:-0.62, cost: 100 },
  { name: "Skills: Robotics",          x:-0.85, y: 0.42, cost: 100 },
  { name: "Skills: Tactics",           x: 0.78, y:-0.42, cost: 100 },
  { name: "Skills: Survival",          x:-0.18, y:-0.82, cost: 100 },
];

// Size / Transformers — multi-grab scenario (Science! Mechanics + Science! Engineering bought together)
const TRANSFORMERS_PERKS = [
  { name: "Cybertronian Forge",   x:-0.50, y: 0.85, cost: 600 },
  { name: "Master Builder",       x: 0.50, y: 0.85, cost: 400 },
  { name: "Science! Engineering", x:-0.30, y: 0.55, cost: 100 },   // <- grabbed
  { name: "Science! Mechanics",   x: 0.30, y: 0.55, cost: 100 },   // <- grabbed
];

// Alchemy / Banjo-Kazooie — single-perk hit on a jump-vertex constellation (2 perks but only one was rolled this time)
const BANJO_PERKS = [
  { name: "Mixing Mixtures", x: 0.00, y: 0.85, cost: 200 },   // <- focal
  { name: "Alchemy",         x:-0.85, y: 0.00, cost: 100 },
];

// --- scenarios -----------------------------------------------------------

// Each scenario specifies:
//  - shape:   key into SHAPES
//  - anchor:  index into shape.markers — which jump-marker is the focal jump's anchor
//  - jumpPerks: optional list of jump-interior perks
//  - focalPerkIndex: which entry in jumpPerks is the rolled perk (or null for the "the anchor itself is the perk" case)
//  - approach: which zoom approach (A1: pan only, A2: pan + spotlight, A3: pan + spotlight + forge reach beam)
//  - outcome: "hit" | "miss" | "multi-grab"
//  - rollMeta: { roll_number, jump_name, perk_name, cost_label, ... }
//  - sceneDetails: per-frame overrides (HUD state, caption etc.)

const SCENARIOS = [
  // ===== Section A — approaches =====
  {
    id: "approach-a1",
    section: "approaches",
    title: "A1 · Pan & scale only",
    description: "The cleanest read: camera pans + scales, focal perk slides to center, rest of sky drifts off-frame. No darkening, no beam. The geometry alone tells you what's being focused on.",
    tech: ["pan & scale", "no spotlight", "1.4s total · ease-in-out-cubic"],
    shape: "Knowledge",
    anchorMarker: 22,                 // marker[22] = (0.719, 0.281) — upper-right page
    jumpPerks: TNG_PERKS,
    focalPerkIndex: 2,                // Skills: Engineering
    spotlight: false,
    beam: false,
    outcome: "hit",
    rollMeta: { roll: 327, jump: "Star Trek: TNG", perk: "Skills: Engineering", cost: 100, hue: 268, color_text: "Knowledge · TNG · 100 CP" },
  },
  {
    id: "approach-a2",
    section: "approaches",
    title: "A2 · Pan & scale + spotlight  ◇ lead",
    description: "Same camera path. Once the camera locks on the jump cluster, a soft spotlight darkens everything outside the focal perk. The jump-vertex motion-blurs at the end of approach, then splits into its perk stars on the reveal frame. Strong lead-in to the future grab-process animation.",
    tech: ["pan & scale", "motion blur on F3 → split on F4", "spotlight (radial mask, F4 onward)", "1.4s total"],
    shape: "Knowledge",
    anchorMarker: 22,
    jumpPerks: TNG_PERKS,
    focalPerkIndex: 2,
    spotlight: true,
    beam: false,
    outcome: "hit",
    rollMeta: { roll: 327, jump: "Star Trek: TNG", perk: "Skills: Engineering", cost: 100, hue: 268, color_text: "Knowledge · TNG · 100 CP" },
  },
  {
    id: "approach-a3",
    section: "approaches",
    title: "A3 · Pan, scale + forge reach beam from below",
    description: "Approach A2 plus a beam of light rising from the bottom of the sky view (where the scrubber sits) up to the focal perk — telegraphing the Forge reaching from the timeline below. With the new layout, the beam reads as continuity between the scrubber and the locked star.",
    tech: ["pan & scale", "spotlight + motion blur", "upward beam from below the viewport (F4 onward)", "1.4s total"],
    shape: "Knowledge",
    anchorMarker: 22,
    jumpPerks: TNG_PERKS,
    focalPerkIndex: 2,
    spotlight: true,
    beam: true,
    outcome: "hit",
    rollMeta: { roll: 327, jump: "Star Trek: TNG", perk: "Skills: Engineering", cost: 100, hue: 268, color_text: "Knowledge · TNG · 100 CP" },
  },

  // ===== Section B — outcomes (all using A2 baseline) =====
  {
    id: "out-perk-vertex",
    section: "outcomes",
    title: "Single hit · perk-vertex constellation",
    description: "When the constellation already shows one star per perk (vertex_source = perks), there is no jump-interior step. Camera flies straight from drift to the rolled perk star and locks. No cluster reveal — the perk already lives in the sky.",
    tech: ["vertex_source = perks", "no inner-perk reveal", "5 frames"],
    shape: "Clothing",
    anchorMarker: 0,                   // a marker that's roughly the rolled perk
    jumpPerks: null,                   // none — focal IS a cluster-level star
    focalPerkIndex: null,
    focalIsClusterMarker: 0,           // pick marker[0]
    spotlight: true,
    beam: true,
    outcome: "hit",
    rollMeta: { roll: 412, jump: "Mass Effect", perk: "Quarian Enviro-Suit", cost: 400, hue: 320, color_text: "Clothing · Mass Effect · 400 CP" },
  },
  {
    id: "out-multi-perk-jump",
    section: "outcomes",
    title: "Single hit · multi-perk jump in jump-vertex constellation",
    description: "The canonical case: cluster shows one star per jump, but the rolled jump contains 4 perks. Motion blur at end of approach; the single jump-vertex then SPLITS into four distinct perk stars in their wireframe positions. Beam rises from below onto the rolled perk; spotlight tightens around it.",
    tech: ["vertex_source = jumps", "motion blur F3 → split F4", "beam apex on focal perk, beam base off the bottom of the viewport"],
    shape: "Alchemy",
    anchorMarker: 8,                   // (0.175, 0.878) — lower-left base of flask
    jumpPerks: [
      { name: "Truth",                x: 0.00, y: 0.85, cost: 800 },
      { name: "Alkahestry",           x: 0.74, y:-0.42, cost: 300 },
      { name: "Advanced Formulae",    x:-0.74, y:-0.42, cost: 100 },
      { name: "Simplified Formulae", x: 0.00, y: 0.00, cost: 100 },   // <- focal
    ],
    focalPerkIndex: 3,
    spotlight: true,
    beam: true,
    outcome: "hit",
    rollMeta: { roll: 481, jump: "Full Metal Alchemist", perk: "Simplified Formulae", cost: 100, hue: 170, color_text: "Alchemy · FMA · 100 CP" },
  },
  {
    id: "out-multi-grab",
    section: "outcomes",
    title: "Multi-grab · perks sucked into the beam",
    description: "One roll buys two perks at once (Size / Transformers — Science! Mechanics + Science! Engineering, 100 CP each). After motion blur and split, the beam rises toward the centerpoint between the two grabbed perks; as the beam approaches, the perks are pulled into its apex, merging with a flash into the binary diffraction marker the scrubber uses.",
    tech: ["split F4 → suck-into-beam F5", "Science! Mechanics + Science! Engineering", "binary diffraction marker (matches scrubber)"],
    shape: "Size",
    anchorMarker: 8,                   // mid of spire
    jumpPerks: TRANSFORMERS_PERKS,
    focalPerkIndices: [2, 3],          // the two grabbed perks
    spotlight: true,
    beam: true,
    outcome: "multi-grab",
    rollMeta: { roll: 156, jump: "Transformers", perk: "Science! Mechanics + Engineering", cost: 200, hue: 100, color_text: "Size · Transformers · 200 CP · multi-grab" },
  },
  {
    id: "out-miss",
    section: "outcomes",
    title: "Miss · spotlight does not connect",
    description: "Roll cost > available CP, so the Forge reaches for a perk in the right cost bracket but does not land. After the split, the beam still rises from below toward an inferred candidate star, but its apex never quite touches and the star never flares — it pulses dimmer. Future: when the data lets us infer the specific missed perk, that star fills this role exactly.",
    tech: ["candidate star inferred from miss_cost_estimate", "beam apex doesn't connect", "no flare, no diffraction lock"],
    shape: "Vehicles",
    anchorMarker: 6,                   // (0.733, 0.392) — top of car
    jumpPerks: [
      { name: "Cinder Block of Power", x: 0.00, y: 0.00, cost: 600 },   // <- candidate (miss target)
    ],
    focalPerkIndex: 0,
    spotlight: true,
    beam: true,
    outcome: "miss",
    rollMeta: { roll: 233, jump: "Mad Max", perk: "(inferred 600-CP target)", cost: 600, miss_estimate: 600, hue: 30, color_text: "Vehicles · ?? · miss ~600" },
  },
];

window.STORYBOARD = {
  SHAPES, SCENARIOS,
  CLUSTER_SCALE, CLUSTER_OFFSET_X, CLUSTER_OFFSET_Y, JUMP_RADIUS,
  clusterToWorld, jumpPerkToWorld,
};

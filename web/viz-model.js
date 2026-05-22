// Half-width of the word-distance window inside which the scrubber is treated
// as "firing" / locked onto a roll. Used both by the playthrough renderer
// (firing flag) and the playback-state machine (onRoll for cinematic + pause).
// Single source of truth — do not duplicate this literal.
export const ROLL_FIRING_WINDOW_WORDS = 700;

// Cinematic roll-focus animation duration. Cinematic playback decouples the
// camera animation from word advance: while firing, wordPos locks to the
// roll's word_position so the cinematic plays out at wall-clock pace
// regardless of the configured words/second. After the cinematic completes
// (t >= 1), `cinematic` mode auto-resumes word advance; `pause` mode holds
// until the user presses play.
export const FOCUS_ANIM_DURATION_MS = 2800;
export function focusAnimDurationFor(_behavior) {
  return FOCUS_ANIM_DURATION_MS;
}

// Easing + math helpers. Match the prototype `animation.js:32-37` exactly so
// all phases agree on the curves. Exported so renderers can compose them
// directly — no parallel ad-hoc easing scattered through app.js.
export function easeInOutCubic(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
export function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
export function lerp(a, b, t) { return a + (b - a) * t; }
export function clamp01(t) { return t < 0 ? 0 : t > 1 ? 1 : t; }
export function phase(t, a, b) { return clamp01((t - a) / (b - a)); }

// Cluster accent hues keyed by constellation name. Consumed by app.js and by
// focusScene below. The animation handoff README documents these as the
// authoritative palette source.
export const HUES = {
  "Toolkits": 196,
  "Knowledge": 268,
  "Vehicles": 30,
  "Time": 218,
  "Crafting": 152,
  "Clothing": 320,
  "Magic": 286,
  "Quality": 48,
  "Size": 100,
  "Resources and Durability": 8,
  "Magitech": 240,
  "Alchemy": 170,
  "Capstone": 52,
  "Personal Reality": 130,
};

export function paidRollPerks(roll) {
  return (roll.purchased_perks || []).filter(perk => !perk.free);
}

export function rollTotalCost(roll) {
  if (roll.purchased_perk_cost_total != null) return roll.purchased_perk_cost_total;
  return paidRollPerks(roll).reduce((total, perk) => total + Number(perk.cost || 0), 0);
}

export function rollMarkerModel(roll) {
  const paidCount = paidRollPerks(roll).length;
  const freeCount = (roll.free_perks || []).length;
  const isUntracked = roll.evidence_kind === "untracked_acquisition";
  const isMissLike = roll.outcome !== "hit" && !isUntracked;
  const cost = isMissLike ? null : rollTotalCost(roll);

  let baseKind = "single";
  if (isMissLike) baseKind = "miss";
  else if (paidCount >= 3) baseKind = "trinary";
  else if (paidCount === 2) baseKind = "binary";

  const suffixes = [];
  if (freeCount > 0 && !isMissLike) suffixes.push("free");
  if (isUntracked) suffixes.push("untracked");

  return {
    kind: [baseKind, ...suffixes].join("-"),
    paidCount,
    freeCount,
    isUntracked,
    isMissLike,
    cost,
  };
}

export function skippedPredictedRollTitle(marker, chapter) {
  const chapterNum = chapter?.chapter_num ?? marker?.mechanical_chapter_num ?? "?";
  const rollNumber = marker?.roll_number != null
    ? `#${marker.roll_number}`
    : `slot ${marker?.slot_index ?? "?"}`;
  return `ch ${chapterNum} · predicted roll ${rollNumber} · skipped to align with narrative mentions`;
}

// `constellationOrder` is required: callers (web app, tests) must pass the canonical
// order — typically derived from `bundle.constellation_wireframes.cluster_constellations`
// in slot_position order.
export function buildConstellationProgressIndex(facts, constellationOrder) {
  if (!Array.isArray(constellationOrder)) {
    throw new TypeError("buildConstellationProgressIndex: constellationOrder must be an array");
  }
  const byChapter = new Map();
  let constMax = 1;
  for (const chapter of facts.chapters || []) {
    const progressByName = new Map(
      (chapter.constellation_progress || []).map(row => [row.name, row]),
    );
    const rows = [];
    const byName = new Map();
    for (const name of constellationOrder) {
      const progress = progressByName.get(name) || {};
      const count = progress.count || 0;
      const total = progress.total || 0;
      const discovered = progress.discovered || 0;
      const discoveredPct = progress.discovered_pct || 0;
      const visible = Boolean(progress.visible);
      const row = {
        name,
        count,
        total,
        discovered,
        discoveredPct,
        complete: Boolean(progress.complete),
        visible,
      };
      byName.set(name, row);
      if (visible) rows.push(row);
      constMax = Math.max(constMax, count);
    }
    byChapter.set(chapter.chapter_num, { rows, byName });
  }

  return { byChapter, constMax };
}

export function perkDisplayLabel(perk) {
  if (!perk) return "";
  const name = perk.name || "";
  const instance = perk.instance;
  if (!name) return instance || "";
  return instance ? `${name} (${instance})` : name;
}

export function rollDisplayName(roll) {
  const principal = (roll.purchased_perks || []).find(perk => !perk.free) ||
    (roll.purchased_perks || [])[0];
  if (principal?.name) return perkDisplayLabel(principal);
  if (roll.outcome === "miss") return "missed grab";
  return roll.outcome || "unknown";
}

export function fieldLogModel(roll, chapter) {
  const quotes = (roll?.evidence_quotes || [])
    .map(quote => typeof quote === "string" ? quote : quote?.text)
    .filter(text => typeof text === "string" && text.trim())
    .map(text => text.trim());
  const chapterNum = roll?.chapter_num || chapter?.chapter_num || "?";
  const outcome = String(roll?.outcome || "unknown").toUpperCase();
  const rollNumber = roll?.roll_number ?? "?";
  return {
    kind: quotes.length ? "quotes" : "placeholder",
    heading: "Field log",
    source: roll?.evidence_kind || null,
    quotes,
    placeholder: quotes.length ? null : `No log data for ch ${chapterNum}.`,
    rollLabel: `roll ${rollNumber} · ch ${chapterNum} · ${outcome}`,
  };
}

// On-roll playback decision. The three behaviors share a single firing
// window (ROLL_FIRING_WINDOW_WORDS):
//   - cinematic: wordPos locks during firing, cinematic plays full wall-clock
//     duration, auto-resumes when the animation completes.
//   - pause: wordPos locks during firing, cinematic plays, holds the final
//     state until the user presses play.
//   - quick: no lock, no cinematic — the scrubber flies through at base speed.
// `speedMultiplier` is preserved in the return shape for the quick path and
// for outside-window callers, but the lock during firing is enforced in
// app.js by suppressing wordPos advance — not by multiplier scaling.
export function onRollPlaybackState(roll, wordPos, behavior = "cinematic") {
  const normalized = behavior === "pause" || behavior === "quick"
    ? behavior
    : "cinematic";
  if (!roll || normalized === "quick") {
    return { behavior: normalized, onRoll: false, speedMultiplier: 1 };
  }
  const rollWord = roll.word_position;
  const distance = Math.abs(Number(wordPos) - Number(rollWord));
  if (!Number.isFinite(distance)) {
    return { behavior: normalized, onRoll: false, speedMultiplier: 1 };
  }
  const onRoll = distance <= ROLL_FIRING_WINDOW_WORDS;
  return { behavior: normalized, onRoll, speedMultiplier: 1 };
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function rollOrderValue(roll) {
  return finiteNumber(roll?.roll_number)
    ?? finiteNumber(roll?.global_roll_number)
    ?? finiteNumber(roll?.source_roll_index)
    ?? finiteNumber(roll?.word_position)
    ?? finiteNumber(roll?.epub_word_offset_curated)
    ?? finiteNumber(roll?.epub_word_offset_predicted)
    ?? Infinity;
}

export function buildSkyCarouselLayout(rolls, options = {}) {
  const rows = Array.isArray(rolls) ? rolls : [];
  const averageCardWidth = finiteNumber(options.averageCardWidth) ?? 348;
  const minCardSpacing = finiteNumber(options.minCardSpacing) ?? 440;
  const totalWords = Math.max(
    1,
    finiteNumber(options.totalWords)
      ?? finiteNumber(rows.at(-1)?.word_position)
      ?? 1,
  );
  const wordPos = finiteNumber(options.wordPos) ?? 0;
  const pxPerWord = (rows.length * averageCardWidth) / totalWords;
  const playheadPx = wordPos * pxPerWord;
  const positions = rows.map(roll => (finiteNumber(roll?.word_position) ?? 0) * pxPerWord);

  if (positions.length > 1) {
    let nearestIndex = 0;
    let nearestDistance = Infinity;
    for (let index = 0; index < positions.length; index += 1) {
      const distance = Math.abs(positions[index] - playheadPx);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    }

    // Enforce minimum spacing in BOTH directions anchored at the playhead's
    // nearest roll. A single rightward `max(positions[i], prev + min)` sweep
    // (and the mirrored leftward `min(positions[i], next - min)` sweep) keeps
    // naturally-spaced rolls at their pxPerWord positions while spreading any
    // cluster — not just the one touching the playhead — that sits closer
    // than `minCardSpacing`. The anchor stays put so the active card remains
    // centered on the playhead.
    for (let index = nearestIndex + 1; index < positions.length; index += 1) {
      const floor = positions[index - 1] + minCardSpacing;
      if (positions[index] < floor) positions[index] = floor;
    }
    for (let index = nearestIndex - 1; index >= 0; index -= 1) {
      const ceiling = positions[index + 1] - minCardSpacing;
      if (positions[index] > ceiling) positions[index] = ceiling;
    }
  }
  return { positions, playheadPx, pxPerWord };
}

function rollAcquiresConstellation(roll) {
  if (!roll?.constellation || roll.outcome !== "hit") return false;
  return (roll.purchased_perks || []).length > 0
    || (roll.free_perks || []).length > 0
    || Boolean(roll.rolled_perk_name)
    || rollTotalCost(roll) > 0;
}

export function buildConstellationKnowledgeIndex(rolls) {
  const firstKnownByConstellation = new Map();
  for (const roll of rolls || []) {
    if (!rollAcquiresConstellation(roll)) continue;
    const order = rollOrderValue(roll);
    const current = firstKnownByConstellation.get(roll.constellation);
    if (!current || order < current.order) {
      firstKnownByConstellation.set(roll.constellation, { order, roll });
    }
  }
  return firstKnownByConstellation;
}

export function constellationOutlineVisibleForRoll(roll, knowledgeIndex) {
  if (!roll?.constellation) return false;
  const firstKnown = knowledgeIndex?.get?.(roll.constellation);
  if (!firstKnown) return false;
  return rollOrderValue(roll) >= firstKnown.order;
}

export function buildRollLogRows(rolls, currentWord, options = {}) {
  const filter = options.filter || "all";
  const sort = options.sort || "roll";
  let rows = (rolls || [])
    .filter(roll => Number(roll.word_position) <= Number(currentWord))
    .map(roll => {
      const paidCost = rollTotalCost(roll) ||
        Number(roll.rolled_perk_cost ?? roll.miss_cost_estimate ?? 0);
      const paidPerks = paidRollPerks(roll);
      const names = [
        ...paidPerks.map(perk => perkDisplayLabel(perk)),
        ...(roll.free_perks || []).map(perk => `${perk.name} (free)`),
      ].filter(Boolean);
      return {
        roll,
        rollNumber: roll.roll_number,
        chapterNum: roll.chapter_num,
        outcome: roll.outcome || "unknown",
        constellation: roll.constellation || null,
        jump: roll.purchased_perk_jump || roll.jump || null,
        names,
        paidCost,
        availableCp: roll.available_cp ?? null,
        clickWord: roll.word_position,
        multi: paidPerks.length >= 2,
      };
    });

  if (filter === "hit") rows = rows.filter(row => row.outcome === "hit");
  else if (filter === "miss") rows = rows.filter(row => row.outcome === "miss");
  else if (filter === "multi") rows = rows.filter(row => row.multi);

  if (sort === "cost") rows.sort((a, b) => b.paidCost - a.paidCost || b.clickWord - a.clickWord);
  else if (sort === "chapter") {
    rows.sort((a, b) => String(b.chapterNum).localeCompare(String(a.chapterNum), undefined, { numeric: true }) ||
      b.clickWord - a.clickWord);
  } else {
    rows.sort((a, b) => b.clickWord - a.clickWord);
  }
  return rows;
}

// ---------------------------------------------------------------------------
// Sky-view roll-focus scene derivation (Phase 0 of cinematic zoom rollout).
//
// `focusScene(roll, data)` packages everything the animation phases need to
// stage a single roll-focus shot: branch (single-hit / multi-grab / miss),
// focal vs ambient vs free-satellite stars from the jump wireframe, miss
// candidate inference, world-space anchor in the 1600x1000 conceptual stage,
// and the cluster hue. No animation logic — purely scene composition.
// ---------------------------------------------------------------------------

// Conceptual world stage from the design handoff README "Camera Math" section.
export const WORLD_STAGE_WIDTH = 1600;
export const WORLD_STAGE_HEIGHT = 1000;
const CLUSTER_REGION_SIZE = 620;          // cluster occupies a 620x620 box ...
const CLUSTER_REGION_ORIGIN_X = 490;      // ... offset so it centers at (800, 500)
const CLUSTER_REGION_ORIGIN_Y = 190;
export const JUMP_RADIUS_WORLD = 70;      // star-local [-1,1] → world units

// Multi-grab binary positions sit close to the merge center, offset slightly so
// the two focals' diffraction rays heavily overlap (reading as one fused unit).
// Mirrors `animation.js:323-326` — first focal lands at (-x, +y), second at
// (+x, -y) relative to the merge center.
export const HALO_BINARY_OFFSET = { x: 5, y: 1 };

export function clusterLocalToWorld(clusterX, clusterY) {
  return [
    CLUSTER_REGION_ORIGIN_X + clusterX * CLUSTER_REGION_SIZE,
    CLUSTER_REGION_ORIGIN_Y + clusterY * CLUSTER_REGION_SIZE,
  ];
}

export function starLocalToWorld(anchorX, anchorY, star) {
  // The wireframe's star.y is "up-positive" — flip to screen coords.
  return [
    anchorX + Number(star?.x ?? 0) * JUMP_RADIUS_WORLD,
    anchorY - Number(star?.y ?? 0) * JUMP_RADIUS_WORLD,
  ];
}

// Build a lookup keyed by constellation name with the anchor data each cluster
// exposes. For `vertex_source === "jumps"` the cluster's marker_positions are
// 1:1 with the constellation's `jump_constellations` entries in order. For
// `vertex_source === "perks"` they are 1:1 with the *flattened* stars across
// those jump_constellations entries (in jump order, then star order).
export function buildClusterAnchors(wireframes) {
  const byConstellation = new Map();
  const clusters = wireframes?.cluster_constellations || [];
  const jumps = wireframes?.jump_constellations || [];

  // Group jumps by constellation, preserving file order — that's the canonical
  // order both vertex_source modes index into.
  const jumpsByConstellation = new Map();
  for (const jump of jumps) {
    const list = jumpsByConstellation.get(jump.constellation) || [];
    list.push(jump);
    jumpsByConstellation.set(jump.constellation, list);
  }

  for (const cluster of clusters) {
    const markers = cluster.marker_positions || [];
    const constellationJumps = jumpsByConstellation.get(cluster.name) || [];
    const byJump = new Map();
    const byPerkId = new Map();
    const vertexSource = cluster.vertex_source;

    // perkId → jumpName map lets miss-branch consumers (which lack roll.jump
    // in the current dataset) re-derive a jump anchor from the inferred
    // missCandidate's star id.
    const jumpByPerkId = new Map();

    if (vertexSource === "jumps") {
      for (let i = 0; i < constellationJumps.length && i < markers.length; i += 1) {
        const marker = markers[i];
        if (!marker) continue;
        byJump.set(constellationJumps[i].jump, [marker[0], marker[1]]);
      }
      for (const jump of constellationJumps) {
        for (const star of (jump.stars || [])) jumpByPerkId.set(star.id, jump.jump);
      }
    } else if (vertexSource === "perks") {
      let flatIndex = 0;
      for (const jump of constellationJumps) {
        // First star per jump is the canonical jump anchor in perk-vertex mode.
        let firstStarMarker = null;
        for (const star of (jump.stars || [])) {
          const marker = markers[flatIndex];
          flatIndex += 1;
          jumpByPerkId.set(star.id, jump.jump);
          if (!marker) continue;
          if (!firstStarMarker) firstStarMarker = [marker[0], marker[1]];
          byPerkId.set(star.id, [marker[0], marker[1]]);
        }
        if (firstStarMarker) byJump.set(jump.jump, firstStarMarker);
      }
    }

    byConstellation.set(cluster.name, { vertexSource, byJump, byPerkId, jumpByPerkId });
  }

  return byConstellation;
}

function rollJumpKey(roll) {
  return roll?.purchased_perk_jump || roll?.jump || null;
}

// Stable 32-bit hash for deterministic stand-in selection. Seeded by a roll
// identifier so the same miss-with-unknown-constellation always picks the
// same stand-in across re-renders.
function hashSeed(key) {
  const str = String(key ?? "");
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Resolve a stand-in constellation for misses where the curator's source
// records no constellation. Prefer ones still unrevealed through the roll's
// chapter (per `chapter.constellation_progress[*].count == 0`); fall back to
// all known constellations so the animation still plays gracefully at end of
// story. Returns the constellation name or null when no candidates exist.
function resolveStandInConstellation(roll, data) {
  const anchors = data?.clusterAnchors;
  if (!anchors || typeof anchors.keys !== "function") return null;
  const allNames = Array.from(anchors.keys());
  if (!allNames.length) return null;

  const chapters = data?.story?.chapters || [];
  const rollChapter = roll?.chapter_num;
  const revealed = new Set();
  if (chapters.length && rollChapter != null) {
    for (const chapter of chapters) {
      // Walk forward through the story until (inclusive of) the roll's chapter.
      // Anything with count > 0 in any prior or current chapter is revealed.
      for (const row of (chapter.constellation_progress || [])) {
        if (row && Number(row.count || 0) > 0) revealed.add(row.name);
      }
      if (String(chapter.chapter_num) === String(rollChapter)) break;
    }
  }

  const unrevealed = allNames.filter(name => !revealed.has(name));
  const pool = unrevealed.length ? unrevealed : allNames;
  const seedKey = roll?.uid ?? roll?.roll_number ?? roll?.word_position ?? roll?.chapter_num ?? "";
  const idx = hashSeed(seedKey) % pool.length;
  return pool[idx];
}

function inferMissCandidate(roll, wf, allStarsInConstellation, { isStandIn = false } = {}) {
  const avail = Number(roll?.available_cp ?? 0);
  const est = roll?.miss_cost_estimate != null ? Number(roll.miss_cost_estimate) : null;
  const sourceStars = wf?.stars?.length ? wf.stars : (allStarsInConstellation || []);
  // For stand-in constellations the character demonstrably hasn't reached that
  // constellation yet (the curator's source didn't even know which one it was),
  // so the wireframe's "Obtained" markers are end-of-story state, irrelevant
  // to this roll. Don't filter them out — otherwise stand-ins for fully-
  // discovered constellations (Time, Resources and Durability, etc.) leave
  // the candidate pool empty and the camera anchors at world center.
  const stars = isStandIn ? sourceStars : sourceStars.filter(star => star && star.status !== "Obtained");
  if (!stars.length) return null;
  const tooExpensive = stars.filter(star => Number(star.cost || 0) > avail);
  const pool = (tooExpensive.length ? tooExpensive : stars).slice();
  if (est != null && Number.isFinite(est)) {
    pool.sort((a, b) => Math.abs(Number(a.cost || 0) - est) - Math.abs(Number(b.cost || 0) - est));
  } else {
    pool.sort((a, b) => Number(b.cost || 0) - Number(a.cost || 0));
  }
  return pool[0] || null;
}

export function focusScene(roll, data) {
  const isMiss = roll?.outcome === "miss";
  const rawConstellation = roll?.constellation || null;
  const anchorsMap = data?.clusterAnchors;
  const constellationKnown = rawConstellation
    && anchorsMap
    && typeof anchorsMap.has === "function"
    && anchorsMap.has(rawConstellation);

  // Stand-in resolution: when the curator's source records a miss but doesn't
  // know which constellation it would have hit, swap in a still-unrevealed
  // constellation so the camera has something to focus on. Deterministic by
  // roll so re-renders stay stable. The renderer reads
  // `isUnknownConstellationStandIn` to apply the dashed silhouette treatment.
  let isUnknownConstellationStandIn = false;
  let constellation = rawConstellation;
  if (isMiss && !constellationKnown) {
    const standIn = resolveStandInConstellation(roll, data);
    if (standIn) {
      constellation = standIn;
      isUnknownConstellationStandIn = true;
    }
  }

  const jumpName = rollJumpKey(roll);
  const wf = (constellation && jumpName && data?.jumpWireframeByKey)
    ? data.jumpWireframeByKey.get(`${constellation}::${jumpName}`)
    : null;
  const stars = wf?.stars || [];

  // ---------- branch ----------
  const paid = paidRollPerks(roll);
  let branch;
  if (roll?.outcome === "miss") branch = "miss";
  else if (paid.length >= 2) branch = "multi-grab";
  else branch = "single-hit";

  // ---------- focal / free / ambient ----------
  const paidNames = new Set(paid.map(perk => perk?.name).filter(Boolean));
  const freeNames = new Set((roll?.free_perks || []).map(perk => perk?.name).filter(Boolean));
  const focalStars = branch === "miss"
    ? []
    : stars.filter(star => paidNames.has(star.perk_name));
  const freeStars = stars.filter(star => freeNames.has(star.perk_name));
  const focalIds = new Set(focalStars.map(star => star.id));
  const freeIds = new Set(freeStars.map(star => star.id));
  const ambientStars = stars.filter(star => !focalIds.has(star.id) && !freeIds.has(star.id));

  // ---------- miss candidate ----------
  let missCandidate = null;
  if (branch === "miss" && constellation) {
    // Gather every wireframe star in the constellation as a fallback pool when
    // the roll lacks a `jump` (current data ships every miss with jump=null).
    let constellationStars = [];
    if (data?.wireframes?.jump_constellations) {
      for (const j of data.wireframes.jump_constellations) {
        if (j.constellation === constellation) constellationStars = constellationStars.concat(j.stars || []);
      }
    }
    missCandidate = inferMissCandidate(roll, wf, constellationStars, { isStandIn: isUnknownConstellationStandIn });
  }

  // ---------- anchorWorld ----------
  const hue = (constellation && HUES[constellation] != null) ? HUES[constellation] : 196;
  let anchorWorld = [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2];

  const anchors = data?.clusterAnchors;
  const clusterEntry = anchors && constellation ? anchors.get(constellation) : null;

  // Determine the cluster-local anchor for the jump (or fall back to the miss
  // candidate's home jump — the current dataset ships every miss with
  // jump=null, so this fallback is the primary path for misses).
  let clusterLocal = null;
  let resolvedJump = jumpName;
  if (clusterEntry) {
    if (!resolvedJump && missCandidate?.id && clusterEntry.jumpByPerkId) {
      resolvedJump = clusterEntry.jumpByPerkId.get(missCandidate.id) || null;
    }
    if (clusterEntry.vertexSource === "jumps" && resolvedJump) {
      clusterLocal = clusterEntry.byJump.get(resolvedJump) || null;
    } else if (clusterEntry.vertexSource === "perks") {
      const lookupId = focalStars[0]?.id || missCandidate?.id || null;
      if (lookupId) clusterLocal = clusterEntry.byPerkId.get(lookupId) || null;
      if (!clusterLocal && resolvedJump) clusterLocal = clusterEntry.byJump.get(resolvedJump) || null;
    }
  }

  if (clusterLocal) {
    const [anchorX, anchorY] = clusterLocalToWorld(clusterLocal[0], clusterLocal[1]);
    // For `vertex_source = "perks"` clusters the cluster-local anchor IS the
    // perk's position already, so adding star-local offsets would double-count
    // and displace the focal by `(star.x * 70, -star.y * 70)` world units.
    // Only apply star-local offsets for `vertex_source = "jumps"` clusters,
    // where the anchor is the jump centroid.
    const anchorIsJumpCentroid = clusterEntry.vertexSource === "jumps";
    if (anchorIsJumpCentroid && stars.length === 1 && stars[0]) {
      // Single-perk jump: per design "jump anchor in world (or focal if jump
      // has 1 perk)" — the focal IS the only star, offset from centroid.
      anchorWorld = starLocalToWorld(anchorX, anchorY, stars[0]);
    } else if (anchorIsJumpCentroid && branch === "miss" && missCandidate && missCandidate.x != null && missCandidate.y != null) {
      // Miss candidate may live in a different jump than the cluster anchor we
      // looked up; use its local star coords against this jump's centroid.
      anchorWorld = starLocalToWorld(anchorX, anchorY, missCandidate);
    } else {
      // perks-vertex cluster, or multi-perk jumps-vertex cluster: cluster anchor
      // already points at the right world coord (the perk's own marker, or the
      // jump centroid that the camera reveal phase wants).
      anchorWorld = [anchorX, anchorY];
    }
  }

  // ---------- per-star world-coord map ----------
  // Build one lookup so renderers don't have to re-derive (and so multi-grab
  // focals in perks-vertex clusters don't all collapse to anchorWorld).
  //
  // perks-vertex: each star has its own cluster-local marker position; convert
  //   every star independently. anchorWorld is just focalStars[0]'s position.
  // jumps-vertex: anchor is the jump centroid; every star.x/star.y is [-1,1]
  //   relative to that centroid.
  //
  // For misses where roll.jump=null we resolve the missCandidate's home jump
  // above (clusterLocal). In jumps-vertex misses, ambient/focal stars from the
  // candidate's jump map relative to that centroid; in perks-vertex misses each
  // candidate has its own perk-id marker.
  const starWorldById = new Map();
  if (clusterEntry?.vertexSource === "perks") {
    const collect = (star) => {
      if (!star?.id) return;
      const local = clusterEntry.byPerkId?.get(star.id);
      if (local) starWorldById.set(star.id, clusterLocalToWorld(local[0], local[1]));
    };
    stars.forEach(collect);
    freeStars.forEach(collect);
    if (missCandidate) collect(missCandidate);
  } else if (clusterEntry?.vertexSource === "jumps" && clusterLocal) {
    const [anchorX, anchorY] = clusterLocalToWorld(clusterLocal[0], clusterLocal[1]);
    const collect = (star) => {
      if (!star?.id) return;
      starWorldById.set(star.id, starLocalToWorld(anchorX, anchorY, star));
    };
    stars.forEach(collect);
    freeStars.forEach(collect);
    if (missCandidate && missCandidate.x != null && missCandidate.y != null) collect(missCandidate);
  }

  return {
    branch,
    focalStars,
    ambientStars,
    missCandidate,
    anchorWorld,
    hue,
    freeStars,
    vertexSource: clusterEntry?.vertexSource ?? null,
    starWorldById,
    resolvedConstellation: constellation,
    isUnknownConstellationStandIn,
  };
}

// Compute the world-space coords of a focal/ambient star given a scene built
// by focusScene. Indexes into the scene's per-star world-coord map (which
// handles the perks-vertex vs jumps-vertex distinction at scene-build time).
// Falls back to anchorWorld when the star isn't in the map (defensive only —
// every star surfaced by focusScene should have been registered).
export function starWorldFromScene(scene, star) {
  if (!scene) return [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2];
  if (!star) return scene.anchorWorld ?? [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2];
  const mapped = scene.starWorldById?.get(star.id);
  if (mapped) return mapped;
  return scene.anchorWorld ?? [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2];
}

// ---------------------------------------------------------------------------
// Phase 3 progress curves: motion blur, focal split, and silhouette/marker
// fades. All mirror `design/design_handoff_roll_focus_zoom/animation.js`
// exactly so the production renderer and the prototype agree on the curves.
//
// Timing chart (animation.js:165-184, 247-294, 348-350):
//   t in [0.22, 0.50]   motion blur stdDeviation rises 0 → 8
//   t in [0.50, 0.62]   motion blur stdDeviation falls 8 → 0
//   t in [0.40, 0.58]   split progress eases 0 → 1 (interior perks emerge)
//   t in [0.50, 0.60]   silhouette + vertex pins + non-focal cluster markers
//                        fade out under cover of the motion blur peak
//   t in [0.66, 0.90]   non-focal interior perks dim toward the dimFloor
//
// All curves return their saturated end-state at t=1, matching the
// prefers-reduced-motion held-final-frame contract (Phase 1 returns t=1).
// ---------------------------------------------------------------------------
export function motionBlurStdDeviation(t) {
  if (t < 0.22) return 0;
  if (t < 0.50) return ((t - 0.22) / 0.28) * 8;
  if (t < 0.62) return 8 - ((t - 0.50) / 0.12) * 8;
  return 0;
}

export function splitProgress(t) {
  return easeInOutCubic(phase(t, 0.40, 0.58));
}

export function silhouetteOpacity(t) {
  return 0.62 * (1 - phase(t, 0.50, 0.60));
}

export function vertexPinOpacity(t) {
  return 0.85 * (1 - phase(t, 0.50, 0.60));
}

export function nonFocalClusterOpacity(t) {
  return 0.65 * (1 - phase(t, 0.50, 0.60));
}

export function focalClusterOpacity(t) {
  return 0.85 * (1 - splitProgress(t));
}

export function nonFocalInteriorOpacity(t, isMiss = false) {
  // Per animation.js:348-350 — base fades from 0.72 down to dimFloor across
  // t=0.66-0.90, then multiplied by split progress for the fade-in.
  const dimFloor = isMiss ? 0.30 : 0.28;
  const baseDimmed = lerp(0.72, dimFloor, phase(t, 0.66, 0.90));
  return baseDimmed * splitProgress(t);
}

// Focal world coords for a focus scene. The camera, beam, and any future
// overlays all need the same answer — keep it single-sourced here so no two
// callers can ever disagree on what "the focal" is.
//   - single-hit / multi-grab: first focal star's world coord
//   - miss: missCandidate's world coord (if any), else anchor
//   - degenerate: anchor, else stage center
export function focalWorldFromScene(scene) {
  if (scene?.focalStars?.length) return starWorldFromScene(scene, scene.focalStars[0]);
  if (scene?.branch === "miss" && scene?.missCandidate) {
    return starWorldFromScene(scene, scene.missCandidate);
  }
  return scene?.anchorWorld ?? [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2];
}

// Camera view rect for the roll-focus animation. Returns `{cx, cy, w, h}` in
// world units. The beam renderer needs `bottomY = cy + h/2 + 30`, so the
// structural view is the single source of truth — `focusCameraViewBox`
// formats it as an SVG viewBox attribute string.
//
// Mirrors `animation.js:132-162`. Three keyframes:
//   wide   t<0.10            — whole stage
//   reveal 0.10 ≤ t < 0.65   — pan/scale toward jump anchor (or focal if single)
//   hit    0.65 ≤ t < 0.86   — tighten onto the focal perk
// After 0.86 the camera holds at hit. Easing is easeInOutCubic between phases.
export function focusCameraViewRect(t, scene) {
  const wide = { cx: WORLD_STAGE_WIDTH / 2, cy: WORLD_STAGE_HEIGHT / 2, w: 1280, h: 800 };
  const focal = focalWorldFromScene(scene);
  // Reveal centers on the jump anchor so the full cluster stays in frame as
  // the split resolves the focal vertex into per-perk motes. For single-perk
  // jumps and perks-vertex clusters, `focusScene` already collapses
  // `anchorWorld` onto the focal's own marker — so this works uniformly.
  const anchor = scene?.anchorWorld ?? [wide.cx, wide.cy];
  const reveal = { cx: anchor[0], cy: anchor[1], w: 320, h: 200 };
  const hit = { cx: focal[0], cy: focal[1], w: 192, h: 120 };

  if (t < 0.10) return wide;
  if (t < 0.65) {
    const k = easeInOutCubic(phase(t, 0.10, 0.65));
    return {
      cx: lerp(wide.cx, reveal.cx, k),
      cy: lerp(wide.cy, reveal.cy, k),
      w: lerp(wide.w, reveal.w, k),
      h: lerp(wide.h, reveal.h, k),
    };
  }
  if (t < 0.86) {
    const k = easeInOutCubic(phase(t, 0.65, 0.86));
    return {
      cx: lerp(reveal.cx, hit.cx, k),
      cy: lerp(reveal.cy, hit.cy, k),
      w: lerp(reveal.w, hit.w, k),
      h: lerp(reveal.h, hit.h, k),
    };
  }
  return hit;
}

export function focusCameraViewBox(t, scene) {
  const view = focusCameraViewRect(t, scene);
  return `${view.cx - view.w / 2} ${view.cy - view.h / 2} ${view.w} ${view.h}`;
}

// ---------------------------------------------------------------------------
// Phase 4 — forge reach beam. A 4-layer mystical light rising from below the
// viewport up to the focal perk. Mirrors `animation.js:186-201` exactly.
//
//   t in [0.55, 0.80]   opacity eases 0 → 0.92 (easeInOutCubic), then holds
//   t in [0.55, 0.82]   reach eases 0 → 1.0 (easeOutCubic), then holds
//   on a miss outcome the reach is scaled by 0.78 — beam stalls visibly short
//
// Both curves return their saturated end-state at t=1, matching the
// prefers-reduced-motion held-final-frame contract.
// ---------------------------------------------------------------------------
export function beamOpacity(t) {
  if (t < 0.55) return 0;
  return easeInOutCubic(phase(t, 0.55, 0.80)) * 0.92;
}

export function beamReach(t, outcome) {
  if (t < 0.55) return 0;
  const raw = easeOutCubic(phase(t, 0.55, 0.82));
  return outcome === "miss" ? raw * 0.78 : raw;
}

// ---------------------------------------------------------------------------
// Phase 5 — spotlight overlay, focal halo, focal scale-up, multi-grab merge,
// and multi-grab flash burst. All curves mirror `animation.js:203-240, 379`
// exactly so the production renderer and the prototype agree.
//
// Timing chart:
//   t in [0.48, 0.84]   spotlight progress eases 0 → 1 (vignette tightens)
//   t in [0.62, 0.86]   halo aura progress eases 0 → 1 (single-hit halo shrink + opacity)
//   t in [0.62, 0.88]   multi-grab merge progress eases 0 → 1 (perks slide to binary
//                        positions; multi-grab halo radius also rides this curve)
//   t in [0.82, 0.92]   multi-grab flash bursts (peak alpha 0.32 at t≈0.86)
//   t in [0.66, 0.90]   single-hit focal scale-up 1.0 → 1.50 (multi-grab stays 1.0,
//                        miss stays 0.95)
//
// All curves return saturated end-state at t=1 to honor the prefers-reduced-motion
// held-final-frame contract (Phase 1 returns t=1).
// ---------------------------------------------------------------------------
export function spotlightProgress(t) {
  return easeInOutCubic(phase(t, 0.48, 0.84));
}

export function haloAuraProgress(t) {
  return easeInOutCubic(phase(t, 0.62, 0.86));
}

export function multiGrabMergeProgress(t) {
  return easeInOutCubic(phase(t, 0.62, 0.88));
}

export function multiGrabFlashOpacity(t) {
  if (t < 0.82) return 0;
  if (t < 0.86) return easeOutCubic(phase(t, 0.82, 0.86)) * 0.32;
  if (t < 0.92) return easeOutCubic(1 - phase(t, 0.86, 0.92)) * 0.32;
  return 0;
}

// `branch` is one of "single-hit" | "multi-grab" | "miss". Multi-grab focals
// stay at base size — the binary visual comes from proximity + ray overlap,
// not size boost. Miss focals dim slightly (0.95) so the no-lock outcome
// reads visually distinct.
export function focalScaleFactor(t, branch) {
  if (branch === "miss") return 0.95;
  if (branch === "multi-grab") return 1.0;
  if (t < 0.66) return 1.0;
  if (t < 0.82) return 1.0 + easeOutCubic(phase(t, 0.66, 0.82)) * 0.28;
  if (t < 0.90) return 1.28 + easeOutCubic(phase(t, 0.82, 0.90)) * 0.22;
  return 1.50;
}

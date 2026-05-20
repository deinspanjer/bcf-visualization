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

export function rollDisplayName(roll) {
  const principal = (roll.purchased_perks || []).find(perk => !perk.free) ||
    (roll.purchased_perks || [])[0];
  if (principal?.name) return principal.name;
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

export function onRollPlaybackState(roll, wordPos, behavior = "normal") {
  const normalized = behavior === "pause" || behavior === "bullet-time"
    ? behavior
    : "normal";
  if (!roll || normalized === "normal") {
    return { behavior: normalized, onRoll: false, speedMultiplier: 1 };
  }
  const rollWord = roll.word_position;
  const distance = Math.abs(Number(wordPos) - Number(rollWord));
  if (!Number.isFinite(distance)) {
    return { behavior: normalized, onRoll: false, speedMultiplier: 1 };
  }
  if (normalized === "pause") {
    const onRoll = distance <= 700;
    return { behavior: normalized, onRoll, speedMultiplier: onRoll ? 0 : 1 };
  }
  const onRoll = distance <= 1500;
  return { behavior: normalized, onRoll, speedMultiplier: onRoll ? 0.04 : 1 };
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
        ...paidPerks.map(perk => perk.name),
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

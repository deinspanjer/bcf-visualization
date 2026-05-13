export const DEFAULT_CONSTELLATION_ORDER = [
  "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
  "Clothing", "Magic", "Quality", "Size",
  "Resources and Durability", "Magitech", "Alchemy",
  "Capstone", "Personal Reality",
];

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

export function buildConstellationProgressIndex(
  facts,
  constellationOrder = DEFAULT_CONSTELLATION_ORDER,
) {
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

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

function chapterSortKey(chapterNum) {
  return String(chapterNum || "")
    .split(".")
    .map(part => Number.parseInt(part, 10) || 0);
}

function compareChapter(a, b) {
  const aa = chapterSortKey(a);
  const bb = chapterSortKey(b);
  const len = Math.max(aa.length, bb.length);
  for (let i = 0; i < len; i += 1) {
    const delta = (aa[i] || 0) - (bb[i] || 0);
    if (delta !== 0) return delta;
  }
  return 0;
}

function shouldCountDirectoryPerk(perk) {
  if (perk.free) return false;
  if (perk.cost == null) return false;
  if (perk.status === "Locked") return false;
  return true;
}

export function buildConstellationProgressIndex(
  facts,
  directory,
  constellationOrder = DEFAULT_CONSTELLATION_ORDER,
) {
  const totals = new Map(constellationOrder.map(name => [name, 0]));
  const directoryPerks = (directory && directory.perks) || [];
  for (const perk of directoryPerks) {
    if (!shouldCountDirectoryPerk(perk)) continue;
    const constellation = perk.constellation;
    totals.set(constellation, (totals.get(constellation) || 0) + 1);
  }

  const chapters = facts.chapters || [];
  const chapterRank = new Map(chapters.map((chapter, idx) => [chapter.chapter_num, idx]));
  function acquiredByChapter(perk, chapterIdx) {
    if (!perk.acquired_chapter_num) return false;
    const rank = chapterRank.get(perk.acquired_chapter_num);
    if (rank != null) return rank <= chapterIdx;
    return compareChapter(perk.acquired_chapter_num, chapters[chapterIdx]?.chapter_num) <= 0;
  }

  const byChapter = new Map();
  let constMax = 1;
  for (let chapterIdx = 0; chapterIdx < chapters.length; chapterIdx += 1) {
    const chapter = chapters[chapterIdx];
    const counts = new Map(constellationOrder.map(name => [name, 0]));
    const discovered = new Map(constellationOrder.map(name => [name, 0]));

    for (let i = 0; i <= chapterIdx; i += 1) {
      for (const roll of chapters[i].rolls || []) {
        if (roll.outcome !== "hit" && roll.evidence_kind !== "untracked_acquisition") continue;
        for (const perk of paidRollPerks(roll)) {
          const constellation = roll.constellation || perk.constellation;
          if (!constellation) continue;
          counts.set(constellation, (counts.get(constellation) || 0) + 1);
        }
        for (const perk of roll.free_perks || []) {
          const constellation = perk.constellation || roll.constellation;
          if (!constellation) continue;
          counts.set(constellation, (counts.get(constellation) || 0) + 1);
        }
      }
    }

    for (const perk of directoryPerks) {
      if (!shouldCountDirectoryPerk(perk) || !acquiredByChapter(perk, chapterIdx)) continue;
      discovered.set(perk.constellation, (discovered.get(perk.constellation) || 0) + 1);
    }

    const rows = [];
    const byName = new Map();
    for (const name of constellationOrder) {
      const count = counts.get(name) || 0;
      const total = totals.get(name) || 0;
      const discoveredCount = discovered.get(name) || 0;
      const discoveredPct = total > 0 ? Math.round((discoveredCount / total) * 100) : 0;
      const visible = total > 0 && count > 0;
      const row = {
        name,
        count,
        total,
        discovered: discoveredCount,
        discoveredPct,
        complete: total > 0 && discoveredCount >= total,
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

/* =====================================================================
   Data loader — reads the real visualization_facts.json and flattens it
   into the minimal shape the prototype needs.

   Shape returned:
     {
       totalWords,
       chapters: [{
         num, title, pov, publishedAt,
         wordStart, wordEnd, rollsCount, hitsCount, missesCount,
       }],
       rolls: [{
         globalIndex, rollNumber, chapterNum, outcome,
         constellation, perkName, perkJump, perkCost,
         wordPosition,
       }],
     }
   ===================================================================== */

const DATA_URL_CANDIDATES = [
  // Relative to redesign/mobile-ux/prototype.html
  "../../data/derived/visualization_facts.json",
  "/data/derived/visualization_facts.json",
];

async function loadData(setProgress) {
  let lastErr = null;
  for (const url of DATA_URL_CANDIDATES) {
    try {
      setProgress?.("fetch " + url);
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) { lastErr = new Error(res.status + " " + url); continue; }
      setProgress?.("parse " + Math.round((res.headers.get("content-length") || 0) / 1024) + "kb");
      const json = await res.json();
      setProgress?.("ingest");
      return ingest(json);
    } catch (err) {
      lastErr = err;
    }
  }
  throw lastErr || new Error("Could not load data");
}

function ingest(bundle) {
  const chapters = [];
  const rolls = [];
  let runningWord = 0;

  for (const ch of bundle.chapters || []) {
    const total = Number(ch.total_word_count || 0);
    const wordStart = runningWord;
    const wordEnd = wordStart + total;
    runningWord = wordEnd;

    const pov = (ch.pov_characters || [])[0] || "Joe";
    chapters.push({
      num: ch.chapter_num,
      title: normalizeTitle(ch.full_title || `Chapter ${ch.chapter_num}`, ch.chapter_num),
      pov,
      publishedAt: ch.published_at || null,
      wordStart, wordEnd,
      total,
      rollsCount: ch.rolls_count || 0,
      hitsCount: ch.hits_count || 0,
      missesCount: ch.misses_count || 0,
    });

    // Roll word positions: rolls land at evenly distributed positions within
    // their chapter (approximation; the real app uses curated positions).
    // For prototype purposes this gives correct ordering + plausible spacing.
    const chRolls = ch.rolls || [];
    chRolls.forEach((r, idx) => {
      const frac = (idx + 0.5) / Math.max(chRolls.length, 1);
      const perks = r.purchased_perks || [];
      const perkName = perks[0]?.name || null;
      rolls.push({
        globalIndex: rolls.length,
        rollNumber: r.roll_number ?? null,
        chapterNum: ch.chapter_num,
        outcome: r.outcome || "unknown",
        constellation: r.constellation || null,
        perkName,
        perkJump: r.purchased_perk_jump || null,
        perkCost: r.purchased_perk_cost_total ?? perks[0]?.cost ?? null,
        evidenceQuote: r.evidence_quotes?.[0]?.text || null,
        wordPosition: wordStart + Math.floor(frac * total),
      });
    });
  }

  return {
    totalWords: runningWord,
    chapters,
    rolls,
  };
}

function normalizeTitle(full, num) {
  if (!full) return `Chapter ${num}`;
  // "12.3 Some Title" → "Some Title"
  const stripped = full.replace(new RegExp(`^${num}[.\\s]+`), "").trim();
  return stripped || full;
}

/* Helpers used by the UI */
function chapterAtWord(data, wordPos) {
  if (!data) return null;
  if (wordPos >= data.totalWords) return data.chapters[data.chapters.length - 1];
  return data.chapters.find(c => wordPos >= c.wordStart && wordPos < c.wordEnd) || data.chapters[0];
}

function rollIndexAtOrBeforeWord(data, wordPos) {
  if (!data || !data.rolls.length) return -1;
  let lo = 0, hi = data.rolls.length - 1, ans = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (data.rolls[mid].wordPosition <= wordPos) { ans = mid; lo = mid + 1; }
    else hi = mid - 1;
  }
  return ans;
}

function activeRollAtWord(data, wordPos) {
  const idx = rollIndexAtOrBeforeWord(data, wordPos);
  return idx >= 0 ? data.rolls[idx] : null;
}

function recentRolls(data, wordPos, count = 4) {
  const idx = rollIndexAtOrBeforeWord(data, wordPos);
  if (idx < 0) return [];
  return data.rolls.slice(Math.max(0, idx - count + 1), idx + 1).reverse();
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

/* Format helpers */
function fmtWords(n) {
  const v = Math.max(0, Math.round(Number(n) || 0));
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
  if (v >= 1000) return Math.round(v / 1000) + "k";
  return String(v);
}
function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "2-digit" });
}

Object.assign(window, {
  loadData, chapterAtWord, activeRollAtWord, rollIndexAtOrBeforeWord,
  recentRolls, clamp, fmtWords, fmtDate,
});

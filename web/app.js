import {
  dataVersionOptionLabel,
  validateDataDocument,
  validateDataPackageManifest,
} from "./data-contract.js";
import {
  DEFAULT_CONSTELLATION_ORDER,
  buildCoordinateModel,
  buildRollLogRows,
  fieldLogModel,
  onRollPlaybackState,
  paidRollPerks,
  rollWordPosition as modelRollWordPosition,
  rollTotalCost,
} from "./viz-model.js";

const DATA_BASE = "../data/derived";
const PACKAGES_INDEX_URL = "../data/packages.json";
const DATA_PACKAGE_PARAM = "dataPackage";
const DATA_VERSION = "preview-port2";

const LS_BOOKMARK = "bcf:bookmark:word_position";
const LS_SPEED = "bcf:playback:speed:v2";
const LS_ZOOM = "bcf:timeline:zoom";
const LS_MODE = "bcf:mode";
const LS_ON_ROLL_BEHAVIOR = "bcf:on-roll-behavior";
const LS_FIELD_LOG_HIDDEN = "bcf:field-log:hidden";
const LS_PORTRAIT_DISMISSED = "bcf:portrait-dismissed";
const LS_STORAGE_VERSION = "bcf:preview-port-storage-version";
const STORAGE_VERSION = "2";
const DEFAULT_WORD_POS = 450_000;
const DEFAULT_SPEED = 5_000;
const DEFAULT_ZOOM = 2.75;
const DEFAULT_ON_ROLL_BEHAVIOR = "pause";

const STORY_LINKS = [
  { label: "SV", href: "https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks" },
  { label: "FF", href: "https://www.fanfiction.net/s/13574944/1/Brockton-s-Celestial-Forge" },
  { label: "AO3", href: "https://archiveofourown.org/works/23949661/navigate" },
];
const STORY_TITLE_HREF = STORY_LINKS[0].href;
const PROJECT_REPO = "https://github.com/deinspanjer/bcf-visualization";
const BASE_PX_PER_KWORD = 8.4;

const HUES = {
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

const SHAPES = {
  "Toolkits": { outline: [[0.06, 0.32], [0.20, 0.42], [0.32, 0.46], [0.62, 0.49], [0.94, 0.50], [0.62, 0.51], [0.32, 0.54], [0.20, 0.60], [0.06, 0.70], [0.02, 0.50]], interior: [[0.46, 0.50], [0.78, 0.50]] },
  "Knowledge": { outline: [[0.18, 0.20], [0.50, 0.30], [0.82, 0.20], [0.82, 0.78], [0.50, 0.72], [0.18, 0.78]], interior: [[0.34, 0.42], [0.34, 0.56], [0.66, 0.42], [0.66, 0.56], [0.50, 0.50]] },
  "Vehicles": { outline: [[0.08, 0.62], [0.20, 0.50], [0.36, 0.40], [0.56, 0.36], [0.72, 0.42], [0.84, 0.48], [0.94, 0.55], [0.94, 0.70], [0.08, 0.70]], interior: [[0.26, 0.74], [0.74, 0.74], [0.46, 0.54], [0.66, 0.50]] },
  "Time": { outline: [[0.20, 0.16], [0.80, 0.16], [0.50, 0.50], [0.80, 0.84], [0.20, 0.84], [0.50, 0.50]], interior: [[0.50, 0.30], [0.50, 0.40], [0.50, 0.66], [0.50, 0.76]] },
  "Crafting": { outline: [[0.04, 0.30], [0.18, 0.40], [0.28, 0.36], [0.30, 0.48], [0.94, 0.54], [0.94, 0.62], [0.30, 0.66], [0.28, 0.74], [0.18, 0.70], [0.04, 0.78]], interior: [[0.18, 0.56], [0.60, 0.58]] },
  "Clothing": { outline: [[0.42, 0.18], [0.58, 0.18], [0.72, 0.28], [0.92, 0.46], [0.78, 0.54], [0.78, 0.86], [0.22, 0.86], [0.22, 0.54], [0.08, 0.46], [0.28, 0.28]], interior: [[0.50, 0.34], [0.50, 0.62]] },
  "Magic": { outline: [[0.50, 0.10], [0.40, 0.42], [0.18, 0.66], [0.10, 0.74], [0.50, 0.78], [0.90, 0.74], [0.82, 0.66], [0.60, 0.42]], interior: [[0.50, 0.54], [0.40, 0.62], [0.60, 0.62]] },
  "Quality": { outline: [[0.50, 0.20], [0.84, 0.34], [0.70, 0.42], [0.50, 0.80], [0.30, 0.42], [0.16, 0.34]], interior: [[0.50, 0.32], [0.50, 0.46], [0.40, 0.60], [0.60, 0.60]] },
  "Size": { outline: [[0.10, 0.30], [0.50, 0.18], [0.90, 0.30], [0.78, 0.52], [0.50, 0.42], [0.22, 0.52], [0.66, 0.74], [0.50, 0.66], [0.34, 0.74], [0.66, 0.84], [0.34, 0.84]], interior: [] },
  "Resources and Durability": { outline: [[0.16, 0.20], [0.84, 0.20], [0.92, 0.32], [0.80, 0.58], [0.50, 0.90], [0.20, 0.58], [0.08, 0.32]], interior: [[0.50, 0.32], [0.50, 0.50], [0.50, 0.66]] },
  "Magitech": { outline: [[0.50, 0.08], [0.82, 0.18], [0.92, 0.50], [0.82, 0.82], [0.50, 0.92], [0.18, 0.82], [0.08, 0.50], [0.18, 0.18]], interior: [[0.38, 0.34], [0.56, 0.46], [0.46, 0.54], [0.62, 0.68]] },
  "Alchemy": { outline: [[0.42, 0.16], [0.58, 0.16], [0.58, 0.40], [0.84, 0.58], [0.86, 0.78], [0.50, 0.92], [0.14, 0.78], [0.16, 0.58], [0.42, 0.40]], interior: [[0.42, 0.70], [0.56, 0.62], [0.50, 0.80]] },
  "Capstone": { outline: [[0.05, 0.85], [0.25, 0.55], [0.42, 0.70], [0.50, 0.18], [0.58, 0.70], [0.75, 0.55], [0.95, 0.85]], interior: [[0.50, 0.40], [0.50, 0.58]] },
  "Personal Reality": { outline: [[0.18, 0.50], [0.50, 0.20], [0.68, 0.30], [0.68, 0.18], [0.78, 0.18], [0.78, 0.36], [0.82, 0.50], [0.82, 0.86], [0.18, 0.86]], interior: [[0.30, 0.68], [0.50, 0.70], [0.70, 0.68]] },
};

const POV_HUE_OVERRIDES = { Joe: 196, Taylor: 270, Aisha: 330, Lisa: 318, Rachel: 14, Alec: 60, Amy: 130, Vicky: 70, Dragon: 142, Colin: 230, Survey: 184 };
const MONTH_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

migratePreviewStorage();

const app = {
  data: null,
  error: null,
  infoOpen: false,
  packageIndex: null,
  selectedPackageId: null,
  mode: readStoredChoice(LS_MODE, ["playthrough", "detail"], "playthrough"),
  wordPos: readStoredNumber(LS_BOOKMARK, DEFAULT_WORD_POS),
  playing: false,
  speed: readStoredNumber(LS_SPEED, DEFAULT_SPEED),
  zoom: clamp(readStoredNumber(LS_ZOOM, DEFAULT_ZOOM), 0.5, 6),
  onRollBehavior: readStoredChoice(LS_ON_ROLL_BEHAVIOR, ["normal", "pause", "bullet-time"], DEFAULT_ON_ROLL_BEHAVIOR),
  fieldLogHidden: readStoredBoolean(LS_FIELD_LOG_HIDDEN, false),
  portraitDismissed: readStoredBoolean(LS_PORTRAIT_DISMISSED, false),
  rollFilter: "all",
  rollSort: "roll",
  pauseBypassRollUid: null,
  raf: null,
  lastFrame: 0,
};

function el(tag, props, ...children) {
  const node = document.createElement(tag);
  setProps(node, props);
  append(node, children);
  return node;
}

function svgEl(tag, props, ...children) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  setProps(node, props, true);
  append(node, children);
  return node;
}

function setProps(node, props, svg = false) {
  if (!props) return;
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (key === "class") node.setAttribute("class", value);
    else if (key === "text") node.textContent = String(value);
    else if (key === "style" && typeof value === "object") {
      for (const [name, styleValue] of Object.entries(value)) {
        if (styleValue == null) continue;
        if (name.startsWith("--")) node.style.setProperty(name, styleValue);
        else node.style[name] = styleValue;
      }
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (svg || key.includes("-") || key === "role" || key === "for") {
      node.setAttribute(key, String(value));
    } else {
      node[key] = value;
    }
  }
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child))
      : child);
  }
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function readStoredChoice(key, allowed, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return allowed.includes(raw) ? raw : fallback;
  } catch {
    return fallback;
  }
}

function readStoredNumber(key, fallback) {
  try {
    const stored = localStorage.getItem(key);
    if (stored == null || stored === "") return fallback;
    const raw = Number(stored);
    return Number.isFinite(raw) ? raw : fallback;
  } catch {
    return fallback;
  }
}

function readStoredBoolean(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw === "true") return true;
    if (raw === "false") return false;
  } catch {}
  return fallback;
}

function store(key, value) {
  try { localStorage.setItem(key, String(value)); } catch {}
}

function migratePreviewStorage() {
  try {
    if (localStorage.getItem(LS_STORAGE_VERSION) === STORAGE_VERSION) return;
    for (const key of [LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR, LS_FIELD_LOG_HIDDEN]) {
      localStorage.removeItem(key);
    }
    localStorage.setItem(LS_STORAGE_VERSION, STORAGE_VERSION);
  } catch {}
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatWords(n) {
  const value = Math.max(0, Math.round(Number(n) || 0));
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1000) return `${Math.round(value / 1000)}k`;
  return String(value);
}

function formatCpWords(n) {
  return `${formatWords(n)} cp`;
}

function ordinal(n) {
  const v = n % 100;
  if (v >= 11 && v <= 13) return `${n}th`;
  if (n % 10 === 1) return `${n}st`;
  if (n % 10 === 2) return `${n}nd`;
  if (n % 10 === 3) return `${n}rd`;
  return `${n}th`;
}

async function fetchJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`failed to load ${url}: ${response.status}`);
  return response.json();
}

async function loadPackageIndex() {
  try {
    return await fetchJSON(`${PACKAGES_INDEX_URL}?v=${DATA_VERSION}`);
  } catch {
    return null;
  }
}

function selectPackage(packageIndex) {
  const requested = new URLSearchParams(window.location.search).get(DATA_PACKAGE_PARAM);
  const packages = Array.isArray(packageIndex?.packages) ? packageIndex.packages : [];
  const defaultId = packageIndex?.default_package_id || packages[0]?.package_id || null;
  if (requested) {
    const match = packages.find(pkg => pkg.package_id === requested);
    if (match) return { base: `../${match.path}`, packageId: match.package_id, defaultId };
    return { base: DATA_BASE, packageId: null, defaultId };
  }
  const defaultPackage = packages.find(pkg => pkg.package_id === defaultId);
  if (defaultPackage) {
    return { base: `../${defaultPackage.path}`, packageId: defaultPackage.package_id, defaultId };
  }
  return { base: DATA_BASE, packageId: null, defaultId };
}

async function loadRuntime() {
  app.packageIndex = await loadPackageIndex();
  const selected = selectPackage(app.packageIndex);
  app.selectedPackageId = selected.packageId;

  const manifest = await fetchJSON(`${selected.base}/data_package.json?v=${DATA_VERSION}`);
  const manifestInfo = validateDataPackageManifest(manifest);
  const factsMeta = manifestInfo.files.visualization_facts;
  if (!factsMeta || !factsMeta.path) {
    throw new Error("Data package manifest does not declare visualization_facts.");
  }
  const bundle = await fetchJSON(`${selected.base}/${factsMeta.path}?v=${DATA_VERSION}`);
  validateDataDocument("visualization_facts", bundle, factsMeta);

  const story = buildStory(bundle);
  const constellations = buildConstellations(bundle.constellation_wireframes);
  const conByName = Object.fromEntries(constellations.map(c => [c.name, c]));
  const jumpWireframeByKey = new Map();
  for (const jump of bundle.constellation_wireframes.jump_constellations || []) {
    jumpWireframeByKey.set(`${jump.constellation}::${jump.jump}`, jump);
  }

  const curated = bundle.predicted_rolls;
  const lastCuratedWord = curated.length ? curated[curated.length - 1].word_position : 0;
  const synthetic = buildSyntheticCpTicks(story).filter(t => t.word_position > lastCuratedWord);
  const predictedRolls = [...curated, ...synthetic];

  app.data = {
    pkg: manifest,
    bundleVersion: bundle.version,
    story,
    wireframes: bundle.constellation_wireframes,
    constellations,
    conByName,
    jumpWireframeByKey,
    predictedRolls,
    predictedRollsMeta: bundle.predicted_rolls_meta,
  };
  app.wordPos = clamp(app.wordPos, 0, story.total_words);
}

function buildStory(chapterFacts) {
  const chapters = [];
  const rolls = [];
  const sections = [];
  const coordinateModel = buildCoordinateModel(chapterFacts);
  let runningStart = 0;
  let runningCpCum = 0;

  for (const ch of chapterFacts.chapters || []) {
    const wordStart = runningStart;
    const wordEnd = Number(ch.cumulative_words_through_chapter || wordStart + (ch.total_word_count || 0));
    runningStart = wordEnd;
    const cpCumStart = runningCpCum;
    runningCpCum = Number(ch.cumulative_cp_earning_words || cpCumStart + (ch.cp_earning_word_count || 0));
    const chapter = {
      chapter_num: ch.chapter_num,
      sort_key: ch.sort_key || [Number.parseFloat(ch.chapter_num) || chapters.length + 1],
      title: normChapterTitle(ch.full_title || `Chapter ${ch.chapter_num}`, ch.chapter_num),
      full_title: ch.full_title || `Chapter ${ch.chapter_num}`,
      pov: (ch.pov_characters || [])[0] || "Joe",
      pov_characters: ch.pov_characters || [],
      structural_markers: ch.structural_markers || [],
      regime: ch.point_calculation_regime,
      word_start: wordStart,
      word_end: wordEnd,
      total_word_count: ch.total_word_count || (wordEnd - wordStart),
      cp_earning_word_count: ch.cp_earning_word_count || 0,
      cp_cum_start: cpCumStart,
      cp_cum_end: runningCpCum,
      publish_date: (ch.published_at || "").slice(0, 10),
      post_url: ch.post_url,
      banked_cp_at_start: ch.banked_cp_at_start,
      banked_cp_at_end: ch.banked_cp_at_end,
      constellation_progress: ch.constellation_progress || [],
      sections: ch.sections || [],
      recovery: false,
      rolls: [],
    };

    let sectionStart = wordStart;
    for (const [index, section] of (ch.sections || []).entries()) {
      const width = Number(section.word_count || 0);
      sections.push({
        chapter_num: ch.chapter_num,
        section_index: section.section_index || index + 1,
        marker_kind: section.marker_kind,
        classification: section.classification,
        pov_character: section.pov_character || (section.classification === "mc" ? "Joe" : null),
        header: section.header,
        word_count: width,
        counts_for_cp: !!section.counts_for_cp,
        word_start: sectionStart,
        word_end: sectionStart + width,
      });
      sectionStart += width;
    }

    (ch.rolls || []).forEach((rawRoll, index) => {
      const wordPosition = rollWordPosition(coordinateModel, rawRoll, ch, chapter, index, ch.rolls.length);
      const roll = {
        uid: `${ch.chapter_num}#${rawRoll.roll_sequence_in_chapter ?? index + 1}`,
        roll_number: rawRoll.roll_number ?? rawRoll.global_roll_number ?? `${ch.chapter_num}.${index + 1}`,
        chapter_num: ch.chapter_num,
        mechanical_chapter_num: rawRoll.mechanical_chapter_num,
        display_chapter_num: rawRoll.display_chapter_num,
        outcome: rawRoll.outcome || "unknown",
        constellation: rawRoll.constellation,
        jump: rawRoll.purchased_perk_jump || rawRoll.jump || rawRoll.free_perks?.[0]?.jump || null,
        word_position: Math.round(wordPosition),
        purchased_perks: rawRoll.purchased_perks || [],
        free_perks: rawRoll.free_perks || [],
        purchased_perk_jump: rawRoll.purchased_perk_jump,
        purchased_perk_cost_total: rawRoll.purchased_perk_cost_total,
        rolled_perk_name: rawRoll.rolled_perk_name,
        rolled_perk_cost: rawRoll.rolled_perk_cost,
        miss_cost_estimate: rawRoll.miss_cost_estimate,
        available_cp: rawRoll.available_cp,
        banked_cp_after_roll: rawRoll.banked_cp_after_roll,
        evidence_kind: rawRoll.evidence_kind,
        evidence_quotes: rawRoll.evidence_quotes || [],
        roll_sequence_in_chapter: rawRoll.roll_sequence_in_chapter,
        post_url: ch.post_url,
        publish_date: chapter.publish_date,
        chapter_title: chapter.title,
      };
      chapter.rolls.push(roll);
      rolls.push(roll);
    });

    chapters.push(chapter);
  }

  const byNum = new Map(chapters.map((chapter, index) => [chapter.chapter_num, { chapter, index }]));
  for (const shadow of chapterFacts.shadow_periods || []) {
    const start = byNum.get(shadow.trigger_chapter_num);
    const end = byNum.get(shadow.shadow_end_chapter_num);
    if (!start || !end) continue;
    for (let index = start.index; index <= end.index; index += 1) {
      chapters[index].recovery = true;
      chapters[index].recovery_trigger = shadow.trigger_perk_name;
    }
  }

  rolls.sort((a, b) => a.word_position - b.word_position);
  return {
    chapters,
    rolls,
    sections,
    total_words: chapters[chapters.length - 1]?.word_end || 0,
    shadow_periods: chapterFacts.shadow_periods || [],
  };
}

function rollWordPosition(coordinateModel, rawRoll, rawChapter, chapter, index, total) {
  if (rawRoll.display_cumulative_word_offset != null) return rawRoll.display_cumulative_word_offset;
  if (rawRoll.cumulative_word_offset != null) return rawRoll.cumulative_word_offset;
  if (rawRoll.source_cumulative_word_offset != null) return rawRoll.source_cumulative_word_offset;
  if (rawRoll.display_word_position_epub != null || rawRoll.predicted_word_position_epub != null) {
    return modelRollWordPosition(coordinateModel, rawRoll, rawChapter, index, total);
  }
  const slot = (index + 1) / ((total || 1) + 1);
  return chapter.word_start + slot * Math.max(1, chapter.word_end - chapter.word_start);
}

function normChapterTitle(fullTitle, chapterNum) {
  const prefix = `${chapterNum} `;
  return String(fullTitle).startsWith(prefix) ? String(fullTitle).slice(prefix.length) : String(fullTitle);
}

function buildConstellations(wireframes) {
  const byName = new Map((wireframes.cluster_constellations || []).map(c => [c.name, c]));
  return DEFAULT_CONSTELLATION_ORDER.map(name => ({
    name,
    hue: HUES[name] ?? 196,
    shape_concept: byName.get(name)?.shape_concept || name,
    outline: SHAPES[name]?.outline || [],
    interior: SHAPES[name]?.interior || [],
  }));
}

function hashPovHue(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) hash = ((hash * 31) + name.charCodeAt(i)) | 0;
  let hue = Math.abs(hash) % 320;
  if (hue >= 180) hue += 40;
  return hue;
}

function povColor(povName) {
  if (!povName) return { hue: null, color: "var(--dim)" };
  const hue = POV_HUE_OVERRIDES[povName] ?? hashPovHue(povName);
  return { hue, color: `oklch(0.62 0.14 ${hue})` };
}

function sectionStyle(section) {
  const cls = section.classification;
  const isMc = cls === "mc" || cls === "story";
  const isMeta = cls === "non_mc_meta" || section.marker_kind === "abilities";
  if (isMeta) return { color: "rgba(154, 215, 223, 0.22)", mc: false, meta: true };
  const povName = isMc ? "Joe" : (section.pov_character || null);
  if (!povName) return { color: "oklch(0.62 0.12 38)", mc: false, meta: false };
  const color = povColor(povName).color;
  return { color, mc: isMc, meta: false, povName };
}

function cpEarningAt(rawWords, story) {
  if (rawWords <= 0) return 0;
  for (const chapter of story.chapters) {
    if (rawWords <= chapter.word_end) {
      const rawSpan = chapter.word_end - chapter.word_start;
      const cpSpan = chapter.cp_cum_end - chapter.cp_cum_start;
      if (rawSpan <= 0) return chapter.cp_cum_end;
      return chapter.cp_cum_start + ((rawWords - chapter.word_start) / rawSpan) * cpSpan;
    }
  }
  return story.chapters.at(-1)?.cp_cum_end || 0;
}

function rawWordAtCpEarning(targetCp, story) {
  if (targetCp <= 0) return 0;
  for (const chapter of story.chapters) {
    if (chapter.cp_cum_end >= targetCp) {
      const rawSpan = chapter.word_end - chapter.word_start;
      const cpSpan = chapter.cp_cum_end - chapter.cp_cum_start;
      if (cpSpan <= 0) continue;
      return chapter.word_start + ((targetCp - chapter.cp_cum_start) / cpSpan) * rawSpan;
    }
  }
  return story.total_words;
}

function buildSyntheticCpTicks(story) {
  const totalCp = story.chapters.at(-1)?.cp_cum_end || 0;
  const ticks = [];
  for (let cp = 100; cp <= totalCp; cp += 100) {
    ticks.push({ word_position: Math.round(rawWordAtCpEarning(cp, story)), cp_threshold: cp, regime: 1 });
  }
  return ticks;
}

function chapterAtWord(wordPos) {
  const story = app.data.story;
  if (wordPos >= story.total_words) return story.chapters.at(-1);
  return story.chapters.find(chapter => wordPos >= chapter.word_start && wordPos < chapter.word_end) || story.chapters[0];
}

function chapterIndex(chapterNum) {
  return app.data.story.chapters.findIndex(chapter => chapter.chapter_num === chapterNum);
}

function lastRollAtWord(wordPos) {
  let last = null;
  for (const roll of app.data.story.rolls) {
    if (roll.word_position > wordPos) break;
    last = roll;
  }
  return last;
}

function lastConstellationRollAtWord(wordPos) {
  let last = null;
  for (const roll of app.data.story.rolls) {
    if (roll.word_position > wordPos) break;
    if (roll.constellation) last = roll;
  }
  return last;
}

function recentRolls(wordPos, count = 10) {
  const rows = [];
  for (let i = app.data.story.rolls.length - 1; i >= 0 && rows.length < count; i -= 1) {
    const roll = app.data.story.rolls[i];
    if (roll.word_position <= wordPos) rows.push(roll);
  }
  return rows;
}

function cumulativeAt(wordPos) {
  let paid = 0;
  let free = 0;
  let hits = 0;
  let miss = 0;
  for (const roll of app.data.story.rolls) {
    if (roll.word_position > wordPos) break;
    if (roll.outcome === "hit") {
      hits += 1;
      paid += paidRollPerks(roll).length;
      free += (roll.free_perks || []).length;
    } else if (roll.outcome === "miss") {
      miss += 1;
    }
  }
  const chapter = chapterAtWord(wordPos);
  return { chapter, paid, free, hits, miss };
}

function constellationColor(name) {
  return `oklch(0.78 0.13 ${HUES[name] ?? 196})`;
}

function formatRollLabel(roll) {
  if (!roll) return "";
  const chRef = roll.roll_sequence_in_chapter != null ? `ch ${roll.chapter_num} #${roll.roll_sequence_in_chapter}` : `ch ${roll.chapter_num}`;
  return roll.roll_number != null ? `roll #${roll.roll_number} · ${chRef}` : chRef;
}

function mstEdges(stars) {
  if (stars.length < 2) return [];
  const edges = [];
  for (let i = 0; i < stars.length; i += 1) {
    for (let j = i + 1; j < stars.length; j += 1) {
      const dx = stars[i].x - stars[j].x;
      const dy = stars[i].y - stars[j].y;
      edges.push({ a: i, b: j, d: dx * dx + dy * dy });
    }
  }
  edges.sort((a, b) => a.d - b.d);
  const parent = stars.map((_, index) => index);
  const find = x => {
    while (parent[x] !== x) {
      parent[x] = parent[parent[x]];
      x = parent[x];
    }
    return x;
  };
  const tree = [];
  for (const edge of edges) {
    const a = find(edge.a);
    const b = find(edge.b);
    if (a === b) continue;
    parent[a] = b;
    tree.push(edge);
    if (tree.length === stars.length - 1) break;
  }
  return tree;
}

function setWordPos(value) {
  if (!app.data) return;
  app.pauseBypassRollUid = null;
  app.wordPos = Math.round(clamp(value, 0, app.data.story.total_words));
  store(LS_BOOKMARK, app.wordPos);
  render();
}

function setMode(mode) {
  app.mode = mode;
  store(LS_MODE, mode);
  render();
}

function setFieldLogHidden(hidden) {
  app.fieldLogHidden = hidden;
  store(LS_FIELD_LOG_HIDDEN, hidden);
  render();
}

function startPlayback() {
  if (!app.data || app.playing) return;
  if (app.wordPos >= app.data.story.total_words) setWordPos(0);
  const currentRoll = lastRollAtWord(app.wordPos);
  const rollState = onRollPlaybackState(currentRoll, app.wordPos, app.onRollBehavior);
  app.pauseBypassRollUid = rollState.behavior === "pause" && rollState.onRoll
    ? currentRoll?.uid || null
    : null;
  app.playing = true;
  app.lastFrame = performance.now();
  tickPlayback(app.lastFrame);
  render();
}

function stopPlayback() {
  app.playing = false;
  if (app.raf) cancelAnimationFrame(app.raf);
  app.raf = null;
  render();
}

function togglePlayback() {
  if (app.playing) stopPlayback();
  else startPlayback();
}

function tickPlayback(now) {
  if (!app.playing || !app.data) return;
  const dt = Math.max(0, (now - app.lastFrame) / 1000);
  app.lastFrame = now;
  const currentRoll = lastRollAtWord(app.wordPos);
  const rollState = onRollPlaybackState(currentRoll, app.wordPos, app.onRollBehavior);
  if (app.pauseBypassRollUid && (!rollState.onRoll || currentRoll?.uid !== app.pauseBypassRollUid)) {
    app.pauseBypassRollUid = null;
  }
  if (
    rollState.behavior === "pause" &&
    rollState.onRoll &&
    currentRoll?.uid !== app.pauseBypassRollUid
  ) {
    stopPlayback();
    return;
  }
  const speedMultiplier = currentRoll?.uid === app.pauseBypassRollUid ? 1 : rollState.speedMultiplier;
  const next = app.wordPos + app.speed * speedMultiplier * dt;
  if (next >= app.data.story.total_words) {
    app.wordPos = app.data.story.total_words;
    store(LS_BOOKMARK, app.wordPos);
    app.playing = false;
    render();
    return;
  }
  app.wordPos = Math.round(next);
  store(LS_BOOKMARK, app.wordPos);
  render();
  app.raf = requestAnimationFrame(tickPlayback);
}

function render() {
  const root = document.getElementById("root");
  clear(root);
  if (app.error) {
    root.append(renderLoadError(app.error));
    return;
  }
  if (!app.data) {
    root.append(renderLoading());
    return;
  }
  root.append(renderAppShell());
  centerScrubber();
}

function renderLoading() {
  return el("div", { class: "loading-screen" },
    el("div", {},
      el("div", { class: "loading-kicker", text: "Establishing transmission" }),
      el("div", { class: "loading-title", text: "Loading the Forge sky..." }),
    ),
  );
}

function renderLoadError(error) {
  return el("div", { id: "load-error", class: "loading-screen" },
    el("div", {},
      el("div", { class: "loading-kicker", text: "Transmission failed" }),
      el("div", { class: "loading-title", text: "Failed to load data" }),
      el("p", { text: error.message || String(error) }),
    ),
  );
}

function renderAppShell() {
  return el("div", { class: "app" },
    renderHeader(),
    app.portraitDismissed ? null : renderPortraitBanner(),
    el("main", { class: "app-main" },
      renderScrubber(app.mode === "detail"),
      renderScrubberControls(),
      renderStatStrip(),
      app.mode === "detail" ? renderDetail() : renderPlaythrough(),
    ),
  );
}

function renderHeader() {
  const modeSwitch = el("div", { class: "app-mode-switch", role: "group", "aria-label": "Visualization mode" },
    el("button", {
      id: "mode-playthrough",
      class: app.mode === "playthrough" ? "is-active" : "",
      type: "button",
      "aria-pressed": app.mode === "playthrough",
      onClick: () => setMode("playthrough"),
      text: "Playthrough",
    }),
    el("button", {
      id: "mode-detail",
      class: app.mode === "detail" ? "is-active" : "",
      type: "button",
      "aria-pressed": app.mode === "detail",
      onClick: () => setMode("detail"),
      text: "Detail",
    }),
  );

  return el("header", { class: "app-header" },
    el("div", { class: "app-title" },
      el("h1", {}, el("a", { href: STORY_TITLE_HREF, target: "_blank", rel: "noopener noreferrer", text: "Brockton's Celestial Forge" })),
      el("span", { class: "subject", text: "Power Progression" }),
    ),
    el("div", { class: "app-credits" },
      el("span", { class: "by", text: "Story by" }),
      el("span", { class: "author", text: "LordRoustabout" }),
      STORY_LINKS.map(link => el("a", { class: "site-badge", href: link.href, target: "_blank", rel: "noopener noreferrer", text: link.label })),
    ),
    el("div", { class: "app-hint", "aria-label": "Keyboard shortcuts" },
      el("kbd", { text: "space" }), " play/pause ",
      el("span", { class: "sep", text: "·" }),
      el("kbd", { text: "← →" }), " step ",
      el("span", { class: "sep", text: "·" }),
      el("kbd", { text: "home" }), el("kbd", { text: "end" }), " jump",
    ),
    modeSwitch,
    el("button", {
      id: "info-toggle",
      class: "info-button",
      type: "button",
      "aria-label": "About this visualization",
      "aria-expanded": app.infoOpen,
      title: "About",
      onClick: () => { app.infoOpen = !app.infoOpen; render(); },
      text: "i",
    }),
    app.infoOpen ? renderInfoPopover() : null,
  );
}

function renderPackageSelector() {
  const packages = Array.isArray(app.packageIndex?.packages) ? app.packageIndex.packages : [];
  if (!packages.length) {
    return el("span", { class: "data-version", text: app.data.bundleVersion.version_label || "BCF data" });
  }
  const defaultId = app.packageIndex.default_package_id || packages[0].package_id;
  const select = el("select", {
    id: "data-package-select",
    class: "data-package-select",
    "aria-label": "Data package",
    onChange: event => {
      const selected = event.target.value;
      const url = new URL(window.location.href);
      if (selected === defaultId) url.searchParams.delete(DATA_PACKAGE_PARAM);
      else url.searchParams.set(DATA_PACKAGE_PARAM, selected);
      window.location.href = url.toString();
    },
  }, packages.map(pkg => el("option", {
    value: pkg.package_id,
    selected: (app.selectedPackageId || defaultId) === pkg.package_id,
    text: dataVersionOptionLabel(pkg, pkg.package_id === defaultId),
  })));
  return el("span", { id: "data-package-slot" }, select);
}

function renderInfoPopover() {
  return el("div", { class: "info-popover", role: "dialog", "aria-label": "About this visualization" },
    el("h3", { text: "About" }),
    el("p", {}, "An interactive timeline for ", el("em", { text: "Brockton's Celestial Forge" }), " by LordRoustabout - scrub through the story to watch the Forge reach for power-cluster constellations."),
    el("p", { style: { color: "var(--muted)", fontSize: "12.5px" }, text: "The scrubber timeline plays in publish order; the sky carousel pans to whichever constellation the Forge has touched. Each star is a roll." }),
    el("div", { class: "info-shortcuts" },
      el("h4", { text: "Keyboard shortcuts" }),
      el("dl", {},
        el("dt", {}, el("kbd", { text: "space" })), el("dd", { text: "play / pause" }),
        el("dt", {}, el("kbd", { text: "← →" })), el("dd", { text: "step" }),
        el("dt", {}, el("kbd", { text: "PgUp" }), " / ", el("kbd", { text: "PgDn" })), el("dd", { text: "jump 100k words" }),
        el("dt", {}, el("kbd", { text: "home" }), " / ", el("kbd", { text: "end" })), el("dd", { text: "jump to bounds" }),
      ),
    ),
    el("div", { class: "meta-row" },
      el("span", { text: "Visualization by deinspanjer" }),
      el("a", { class: "gh-link", href: PROJECT_REPO, target: "_blank", rel: "noopener noreferrer", text: "github.com/deinspanjer/bcf-visualization" }),
      el("span", { text: app.data.bundleVersion.version_label || app.data.bundleVersion.package_id || "BCF data" }),
      renderPackageSelector(),
    ),
  );
}

function renderPortraitBanner() {
  return el("div", { class: "portrait-banner is-visible", role: "status" },
    el("span", {}, el("strong", { text: "Best in landscape." }), " The Forge timeline reaches across millions of words - rotating gives the scrubber room to breathe."),
    el("button", { type: "button", onClick: () => { app.portraitDismissed = true; store(LS_PORTRAIT_DISMISSED, true); render(); }, text: "got it" }),
  );
}

function renderScrubber(compact) {
  const story = app.data.story;
  const total = story.total_words || 1;
  const stackPx = Math.max(1200, (total / 1000) * BASE_PX_PER_KWORD * app.zoom);
  const currentChapter = chapterAtWord(app.wordPos);
  const stack = el("div", {
    class: "scrubber-stack",
    style: { width: `${stackPx}px` },
    onPointerDown: scrubPointer,
    onPointerMove: scrubPointerMove,
    onPointerUp: scrubPointerUp,
  },
    renderDateTrack(stackPx),
    renderChapterTrack(stackPx),
    renderPovTrack(),
    renderRollTrack(),
    renderAxisTrack(stackPx),
    el("div", {
      id: "scrubber-playhead",
      class: "scrubber-playhead",
      tabindex: "0",
      role: "slider",
      "aria-label": "Word-position scrubber",
      "aria-valuemin": 0,
      "aria-valuemax": story.total_words,
      "aria-valuenow": app.wordPos,
      style: { left: `${(app.wordPos / total) * 100}%` },
    }),
  );
  return el("div", { class: "panel panel-cut scrubber", style: { minHeight: compact ? "168px" : "232px" } },
    el("div", { class: "scrubber-side" },
      el("span", { class: "label-dates", text: "dates" }),
      el("span", { class: "label-chapters", text: "chapters" }),
      el("span", { class: "label-pov", text: "pov / sections" }),
      el("span", { class: "label-rolls", text: "rolls" }),
      el("span", { class: "label-axis" }, "words", el("span", { class: "sub", text: "total / cp" })),
    ),
    el("div", { class: "scrubber-scroller" }, stack),
    el("div", { class: "scrubber-readout" },
      el("span", { class: "readout-chapter", text: `ch ${currentChapter.chapter_num} · ${currentChapter.pov}` }),
      el("span", { class: "readout-title", text: currentChapter.title }),
      el("span", { class: "readout-meta" },
        `${currentChapter.publish_date || "undated"} · word ${formatWords(app.wordPos)} / ${formatWords(story.total_words)}`,
        currentChapter.banked_cp_at_end != null ? ` · ${currentChapter.banked_cp_at_end} CP banked` : "",
        app.mode === "playthrough" && app.fieldLogHidden ? el("button", {
          id: "field-log-reopen",
          type: "button",
          class: "readout-glyph",
          "aria-label": "Show field log",
          title: "Show field log",
          onClick: () => setFieldLogHidden(false),
        }, documentIcon()) : null,
      ),
    ),
  );
}

let pointerActive = false;
function scrubPointer(event) {
  pointerActive = true;
  event.currentTarget.setPointerCapture?.(event.pointerId);
  updateWordFromPointer(event);
}
function scrubPointerMove(event) {
  if (pointerActive) updateWordFromPointer(event);
}
function scrubPointerUp(event) {
  pointerActive = false;
  event.currentTarget.releasePointerCapture?.(event.pointerId);
}
function updateWordFromPointer(event) {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = clamp(event.clientX - rect.left, 0, rect.width);
  setWordPos((x / rect.width) * app.data.story.total_words);
}

function renderDateTrack(stackPx) {
  const story = app.data.story;
  const total = story.total_words || 1;
  const years = [];
  const months = [];
  const days = [];
  let lastYear = null;
  let lastMonth = null;
  for (const chapter of story.chapters) {
    if (!chapter.publish_date) continue;
    const year = chapter.publish_date.slice(0, 4);
    const month = chapter.publish_date.slice(5, 7);
    const day = Number(chapter.publish_date.slice(8, 10));
    const frac = chapter.word_start / total;
    days.push({ key: chapter.chapter_num, frac, label: ordinal(day) });
    if (month !== lastMonth) {
      if (year === lastYear) months.push({ key: `${year}-${month}`, frac, label: MONTH_ABBR[Number(month) - 1] });
      lastMonth = month;
    }
    if (year !== lastYear) {
      years.push({ key: year, frac, label: year });
      lastYear = year;
      lastMonth = month;
    }
  }
  const monthLabels = gateLabels(months, years, stackPx, 28);
  const dayLabels = gateLabels(days, years.concat(monthLabels), stackPx, 22);
  return el("div", { class: "scrubber-track dates" },
    years.map(t => el("span", { class: "tick year", style: { left: `${t.frac * 100}%` } })),
    months.map(t => el("span", { class: "tick month", style: { left: `${t.frac * 100}%` } })),
    days.map(t => el("span", { class: "tick chapter-pub", style: { left: `${t.frac * 100}%` } })),
    years.map(t => el("span", { class: "tick-label year", style: { left: `${t.frac * 100}%` }, text: t.label })),
    monthLabels.map(t => el("span", { class: "tick-label month", style: { left: `${t.frac * 100}%` }, text: t.label })),
    dayLabels.map(t => el("span", { class: "tick-label day", style: { left: `${t.frac * 100}%` }, text: t.label })),
  );
}

function gateLabels(candidates, reserved, stackPx, gap) {
  const occupied = reserved.map(t => t.frac * stackPx);
  const output = [];
  for (const tick of candidates) {
    const px = tick.frac * stackPx;
    if (occupied.every(other => Math.abs(other - px) >= gap)) {
      output.push(tick);
      occupied.push(px);
    }
  }
  return output;
}

function renderChapterTrack(stackPx) {
  const story = app.data.story;
  const total = story.total_words || 1;
  let lastPx = -Infinity;
  const labels = [];
  for (const chapter of story.chapters) {
    const px = (chapter.word_start / total) * stackPx;
    if (px - lastPx >= 32) {
      labels.push(chapter);
      lastPx = px;
    }
  }
  return el("div", { class: "scrubber-track chapters" },
    story.chapters.map(chapter => el("span", {
      class: `ch-mark ${Number(chapter.sort_key?.[0] || 0) % 10 === 0 || chapter.chapter_num === "1" ? "major" : ""}`,
      style: { left: `${(chapter.word_start / total) * 100}%` },
    })),
    labels.map(chapter => el("span", { class: "ch-num", style: { left: `${(chapter.word_start / total) * 100}%` }, text: `ch ${chapter.chapter_num}` })),
  );
}

function renderPovTrack() {
  const story = app.data.story;
  const total = story.total_words || 1;
  return el("div", { class: "scrubber-track pov" },
    story.sections.map(section => {
      const style = sectionStyle(section);
      const kindClass = ["preamble", "interlude", "addendum"].includes(section.marker_kind) ? section.marker_kind : "";
      return el("span", {
        class: ["pov-band", style.mc ? "mc" : "", style.meta ? "meta" : "", kindClass].filter(Boolean).join(" "),
        style: {
          left: `${(section.word_start / total) * 100}%`,
          width: `${Math.max(0.02, ((section.word_end - section.word_start) / total) * 100)}%`,
          "--bandColor": style.color,
        },
        title: `ch ${section.chapter_num} · ${section.marker_kind || "main"}${section.header ? ` · ${section.header}` : ""}`,
      });
    }),
  );
}

function renderRollTrack() {
  const story = app.data.story;
  const total = story.total_words || 1;
  return el("div", { class: "scrubber-track rolls" },
    story.rolls.map(roll => el("span", {
      class: `roll-marker ${roll.outcome === "miss" ? "miss-marker" : ""}`,
      style: { left: `${(roll.word_position / total) * 100}%` },
      title: `${formatRollLabel(roll)} · ${String(roll.outcome).toUpperCase()} · ${roll.constellation || "-"}`,
      onClick: event => { event.stopPropagation(); setWordPos(roll.word_position); },
    }, diffractionMarker(roll, { scale: app.mode === "detail" ? 0.85 : 1.1, color: constellationColor(roll.constellation) }))),
  );
}

function renderAxisTrack(stackPx) {
  const story = app.data.story;
  const total = story.total_words || 1;
  const wordTicks = timelineTicks(total, app.zoom, false);
  const cpTicks = timelineTicks(story.chapters.at(-1)?.cp_cum_end || 0, app.zoom, true)
    .map(tick => ({ raw: rawWordAtCpEarning(tick.value, story), label: formatCpWords(tick.value) }));
  return el("div", { class: "scrubber-track axis" },
    sampledPredictedTicks(app.data.predictedRolls).map(tick => el("span", { class: `predicted-tick regime-${tick.regime || 1}`, style: { left: `${(tick.word_position / total) * 100}%` }, title: `predicted roll at ${formatWords(tick.word_position)}` })),
    wordTicks.map(tick => [
      el("span", { class: "word-tick", style: { left: `${(tick.value / total) * 100}%` } }),
      el("span", { class: "word-tick-label", style: { left: `${(tick.value / total) * 100}%` }, text: tick.label }),
    ]),
    cpTicks.map(tick => [
      el("span", { class: "cp-tick", style: { left: `${(tick.raw / total) * 100}%` } }),
      el("span", { class: "cp-tick-label", style: { left: `${(tick.raw / total) * 100}%` }, text: tick.label }),
    ]),
    el("span", { class: "regime-band regime-1", style: { left: "0%", width: "100%" } }),
  );
}

function sampledPredictedTicks(ticks) {
  const maxTicks = 20;
  if ((ticks || []).length <= maxTicks) return ticks || [];
  const stride = Math.ceil(ticks.length / maxTicks);
  return ticks.filter((_, index) => index % stride === 0).slice(0, maxTicks);
}

function timelineTicks(total, zoom) {
  const targetPx = 120;
  const desiredKwords = (targetPx / BASE_PX_PER_KWORD) / zoom;
  let step;
  if (desiredKwords < 75) step = 50_000;
  else if (desiredKwords < 150) step = 100_000;
  else if (desiredKwords < 300) step = 200_000;
  else if (desiredKwords < 600) step = 500_000;
  else step = 1_000_000;
  if (total <= 50_000) step = Math.max(1000, Math.ceil(total / 5 / 1000) * 1000);
  const out = [];
  for (let value = 0; value <= total; value += step) out.push({ value, label: formatWords(value) });
  if (!out.length || out.at(-1).value !== total) out.push({ value: total, label: formatWords(total) });
  return out;
}

function renderScrubberControls() {
  return el("div", { class: "scrubber-controls" },
    el("button", {
      id: "play-pause",
      class: "btn icon primary",
      type: "button",
      "aria-label": app.playing ? "Pause" : "Play",
      title: app.playing ? "Pause (space)" : "Play (space)",
      onClick: togglePlayback,
      text: app.playing ? "❚❚" : "▶",
    }),
    el("label", { class: "control-label" },
      "speed",
      el("select", {
        id: "playback-speed",
        value: String(app.speed),
        onChange: event => { app.speed = Number(event.target.value); store(LS_SPEED, app.speed); render(); },
      }, [1000, 2500, 5000, 10000, 25000, 50000, 100000].map(speed => el("option", { value: String(speed), selected: app.speed === speed, text: `${formatWords(speed)} w/s` }))),
    ),
    el("label", { class: "control-label" },
      "zoom",
      el("input", {
        id: "timeline-zoom",
        type: "range",
        min: "0.5",
        max: "6",
        step: "0.05",
        value: String(app.zoom),
        onInput: event => { app.zoom = Number(event.target.value); store(LS_ZOOM, app.zoom); render(); },
      }),
      el("span", { id: "zoom-readout", style: { minWidth: "38px", color: "var(--ink)" }, text: `${app.zoom.toFixed(2)}×` }),
    ),
    el("span", { class: "control-divider", "aria-hidden": "true" }),
    el("span", { class: "control-label", text: "on roll" }),
    el("div", { class: "app-mode-switch roll-mode-switch", role: "group", "aria-label": "Behavior when the Forge fires a roll" },
      ["normal", "pause", "bullet-time"].map(value => el("button", {
        class: app.onRollBehavior === value ? "is-active" : "",
        type: "button",
        "aria-pressed": app.onRollBehavior === value,
        onClick: () => { app.onRollBehavior = value; store(LS_ON_ROLL_BEHAVIOR, value); render(); },
        text: value,
      })),
    ),
    el("button", { class: "btn ghost", id: "reset-bookmark", type: "button", onClick: () => { app.playing = false; setWordPos(0); }, text: "reset" }),
  );
}

function renderStatStrip() {
  const cum = cumulativeAt(app.wordPos);
  return el("div", { class: "stat-strip" },
    el("div", {}, el("strong", { text: `ch ${cum.chapter.chapter_num}` }), " position"),
    el("div", {}, el("strong", { text: formatWords(app.wordPos) }), " words"),
    el("div", {}, el("strong", { text: String(cum.paid) }), " paid motes"),
    el("div", {}, el("strong", { text: String(cum.free) }), " free"),
    el("div", {}, el("strong", { text: String(cum.hits) }), " hits"),
    el("div", {}, el("strong", { text: String(cum.miss) }), " misses"),
    cum.chapter.banked_cp_at_end != null ? el("div", {}, el("strong", { text: String(cum.chapter.banked_cp_at_end) }), " CP banked") : null,
  );
}

function renderPlaythrough() {
  const chapter = chapterAtWord(app.wordPos);
  const lastRoll = lastRollAtWord(app.wordPos);
  const firing = lastRoll && Math.abs(app.wordPos - lastRoll.word_position) <= 1500;
  const lockedRoll = lastConstellationRollAtWord(app.wordPos);
  const activeRoll = firing && lastRoll?.constellation ? lastRoll : lockedRoll;
  const activeName = activeRoll?.constellation || "Toolkits";
  return el("div", { class: `playthrough ${app.fieldLogHidden ? "field-log-hidden" : ""}` },
    el("div", { class: "viewport" },
      starfield(140),
      el("div", { class: "viewport-hud" },
        hudToken("sky lock", activeName.toLowerCase(), "hud-lock"),
        hudToken(firing ? "forge active" : "drifting", firing && lastRoll ? formatRollLabel(lastRoll) : "", `hud-state ${firing ? "active" : "drift"}`),
        hudToken("chapter", `${chapter.chapter_num} / ${app.data.story.chapters.length}`, ""),
      ),
      renderCarousel(),
      renderViewportFrame(),
      firing && lastRoll ? renderJumpFocus(lastRoll) : null,
    ),
    !app.fieldLogHidden ? renderNarrativeReadout(firing ? lastRoll : null, chapter) : null,
  );
}

function hudToken(key, value, extraClass) {
  return el("span", { class: `hud-token ${extraClass}` },
    el("span", { class: "hud-key", text: key }),
    value ? el("span", { class: "hud-val", text: value }) : null,
  );
}


function renderViewportFrame() {
  return el("div", { class: "viewport-frame" },
    el("span", { class: "corner tl" }),
    el("span", { class: "corner tr" }),
    el("span", { class: "corner bl" }),
    el("span", { class: "corner br" }),
  );
}

function renderCarousel() {
  const rolls = app.data.story.rolls;
  const cardWidth = 348;
  let virtualIndex = 0;
  if (rolls.length) {
    if (app.wordPos >= rolls.at(-1).word_position) virtualIndex = rolls.length - 1;
    else {
      const nextIndex = rolls.findIndex(roll => roll.word_position > app.wordPos);
      if (nextIndex <= 0) virtualIndex = 0;
      else {
        const prev = rolls[nextIndex - 1];
        const next = rolls[nextIndex];
        virtualIndex = nextIndex - 1 + ((app.wordPos - prev.word_position) / Math.max(1, next.word_position - prev.word_position));
      }
    }
  }
  const min = Math.max(0, Math.floor(virtualIndex) - 5);
  const max = Math.min(rolls.length - 1, Math.ceil(virtualIndex) + 5);
  const slots = [];
  for (let index = min; index <= max; index += 1) {
    const roll = rolls[index];
    const con = roll.constellation ? app.data.conByName[roll.constellation] : null;
    const distance = Math.abs(index - virtualIndex);
    slots.push(el("div", { class: "carousel-slot", style: { left: `${index * cardWidth}px` } },
      con ? renderConstellationCard(con, distance < 0.4, distance >= 0.4 && distance < 1.3) : renderUnresolvedCard(distance < 0.4, distance >= 0.4 && distance < 1.3),
    ));
  }
  return el("div", { class: "carousel-strip", style: { transform: `translateX(${-(virtualIndex * cardWidth + 160)}px)` } }, slots);
}

function renderConstellationCard(con, active, flank) {
  const size = 320;
  const color = `oklch(0.82 0.14 ${con.hue})`;
  const points = con.outline.length
    ? con.outline.concat([con.outline[0]]).map(point => `${(point[0] * size).toFixed(1)},${(point[1] * size).toFixed(1)}`).join(" ")
    : "";
  return el("div", { class: `const-card ${active ? "is-active" : ""} ${flank ? "is-flank" : ""}`, style: { "--hue": con.hue } },
    el("span", { class: "halo" }),
    svgEl("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: "outline", style: "position:absolute;inset:0" },
      svgEl("polyline", { points, fill: "none", stroke: color, "stroke-width": active ? "1.1" : "0.9", "stroke-linejoin": "round", "stroke-linecap": "round", opacity: active ? "0.32" : "0.20" }),
    ),
    con.outline.map((point, index) => simpleStar({ key: index, color, cost: 300, visualSize: 30, opacity: active ? 1 : 0.85, left: point[0], top: point[1] })),
    con.interior.map((point, index) => simpleStar({ key: index, color, cost: 150, visualSize: 20, opacity: active ? 0.95 : 0.7, left: point[0], top: point[1] })),
  );
}

function renderUnresolvedCard(active, flank) {
  return el("div", { class: `const-card unresolved-card ${active ? "is-active" : ""} ${flank ? "is-flank" : ""}` },
    el("span", { class: "halo" }),
    svgEl("svg", { viewBox: "0 0 320 320", width: "320", height: "320", style: "position:absolute;inset:0;opacity:.25" },
      svgEl("circle", { cx: 160, cy: 160, r: 120, fill: "none", stroke: "rgba(154,215,223,0.4)", "stroke-dasharray": "3 6", "stroke-width": "0.8" }),
    ),
  );
}

function renderJumpFocus(roll) {
  const con = roll.constellation ? app.data.conByName[roll.constellation] : null;
  const wf = roll.constellation && roll.jump ? app.data.jumpWireframeByKey.get(`${roll.constellation}::${roll.jump}`) : null;
  const color = `oklch(0.82 0.14 ${con?.hue ?? 196})`;
  const stars = wf?.stars || [];
  const transform = star => ({ x: ((star.x + 1.4) / 2.8) * 320, y: ((star.y + 1.4) / 2.8) * 220 });
  const acquired = new Set([...(roll.purchased_perks || []).map(p => p.name), ...(roll.free_perks || []).map(p => p.name)]);
  const target = stars.find(star => acquired.has(star.perk_name)) || stars.find(star => star.status === "Obtained") || stars[0];
  return el("div", { class: `jump-focus outcome-${roll.outcome === "hit" ? "hit" : roll.outcome === "miss" ? "miss" : "unknown"}` },
    el("div", { class: "label", text: formatRollLabel(roll) }),
    el("div", { class: "jump-name" }, roll.constellation || "unresolved constellation", roll.jump ? el("span", { style: { color: "var(--muted)", fontFamily: "var(--mono)", fontSize: "11px", marginLeft: "8px" }, text: `· ${roll.jump}` }) : null),
    wf ? el("div", { class: "mini-sky" },
      svgEl("svg", { viewBox: "0 0 320 220", width: "100%", height: "100%", style: "position:absolute;inset:0" },
        mstEdges(stars).map(edge => {
          const a = transform(stars[edge.a]);
          const b = transform(stars[edge.b]);
          return svgEl("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, stroke: color, "stroke-width": "0.5", opacity: "0.30" });
        }),
      ),
      stars.map(star => {
        const p = transform(star);
        const isTarget = target && star.id === target.id;
        return simpleStar({ color: isTarget ? "#fff" : color, cost: star.cost || 100, visualSize: isTarget ? 60 : 36, opacity: isTarget ? 1 : 0.55, left: p.x / 320, top: p.y / 220 });
      }),
    ) : null,
    el("div", { class: "summary" },
      el("span", { text: roll.outcome === "hit" ? `HIT · ${paidRollPerks(roll).length} paid · ${(roll.free_perks || []).length} free` : `MISS · est. ${roll.miss_cost_estimate ?? "?"} CP` }),
      el("span", {}, el("strong", { text: String(rollTotalCost(roll) || roll.miss_cost_estimate || 0) }), " CP"),
    ),
  );
}

function renderNarrativeReadout(roll, chapter) {
  const model = fieldLogModel(roll, chapter);
  const body = el("div", { id: "field-log-body", class: "narrative-body" });
  if (model.kind === "quotes") {
    model.quotes.slice(0, 2).forEach(quote => body.append(el("p", { text: quote })));
  } else {
    body.append(el("p", { class: "no-log" },
      el("span", { class: "no-log-kicker", text: "No log data" }),
      el("span", { class: "no-log-detail", text: roll ? `roll ${roll.roll_number} · ch ${roll.chapter_num}` : `ch ${chapter.chapter_num} · the Forge is between reaches` }),
    ));
  }
  if (roll) body.append(el("span", { class: `roll-line ${roll.outcome === "hit" ? "accent-hit" : "accent-miss"}`, text: model.rollLabel }));
  return el("div", { id: "field-log-panel", class: "panel panel-cut narrative", style: { minHeight: "0" } },
    el("div", { class: "panel-title" },
      el("span", {}, el("span", { class: "pip" }), " Field log", model.source ? el("span", { style: { marginLeft: "8px", color: "var(--dim)" }, text: `· ${model.source}` }) : null),
      el("span", { class: "source", text: "- Joe's event description" }),
      el("button", { id: "field-log-hide", class: "panel-glyph", type: "button", "aria-label": "Collapse Field Log", onClick: () => setFieldLogHidden(true) }, closeIcon()),
    ),
    body,
    renderRecentRolls(roll?.word_position ?? chapter.word_start),
  );
}

function renderRecentRolls(wordPos) {
  return el("div", { class: "recent-rolls" },
    el("div", { class: "head", text: "Recent reaches" }),
    el("ol", {}, recentRolls(wordPos, 8).map(roll => el("li", { class: roll.outcome },
      el("span", { class: "dot" }),
      el("span", { class: "roll-id", text: `#${String(roll.roll_number).slice(0, 6)}` }),
      el("span", {}, el("span", { class: "roll-where", text: roll.constellation || "-" }), el("span", { style: { display: "block", color: "var(--dim)", fontFamily: "var(--mono)", fontSize: "9.5px" }, text: `${roll.jump || "-"} · ch ${roll.chapter_num}` })),
      el("span", { class: "roll-cost", text: roll.outcome === "hit" ? `${rollTotalCost(roll)} CP` : `miss ${roll.miss_cost_estimate ?? "?"}` }),
    ))),
  );
}

function renderDetail() {
  return el("div", { class: "detail" },
    renderSelectedChapter(),
    renderRecentAcquisitions(),
    renderConstellationBars(),
    renderRollLog(),
  );
}

function renderSelectedChapter() {
  const chapter = chapterAtWord(app.wordPos);
  const items = [];
  for (const roll of chapter.rolls) {
    for (const perk of paidRollPerks(roll)) items.push({ perk, roll, free: false });
    for (const perk of roll.free_perks || []) items.push({ perk, roll, free: true });
  }
  return el("div", { class: "panel panel-cut detail-panel" },
    el("div", { class: "panel-title" }, el("span", { class: "pip" }), " Selected chapter"),
    el("div", { class: "body" },
      el("div", { class: "chapter-meta" },
        el("strong", { text: `ch ${chapter.chapter_num} - ${chapter.title}` }),
        ` · ${chapter.publish_date || "undated"} · ${Number(chapter.total_word_count || 0).toLocaleString()} words`,
      ),
      items.length ? el("ul", { class: "perk-list" }, items.map(item => perkListItem(item.perk, item.roll, item.free))) : el("p", { class: "empty-copy", text: "No motes were caught in this chapter." }),
    ),
  );
}

function renderRecentAcquisitions() {
  const items = [];
  for (const roll of recentRolls(app.wordPos, 20).filter(r => r.outcome === "hit")) {
    for (const perk of paidRollPerks(roll)) items.push({ perk, roll, free: false });
    for (const perk of roll.free_perks || []) items.push({ perk, roll, free: true });
    if (items.length >= 14) break;
  }
  return el("div", { class: "panel panel-cut detail-panel" },
    el("div", { class: "panel-title" }, el("span", { class: "pip" }), " Most recent acquisitions"),
    el("div", { class: "body" },
      items.length ? el("ul", { class: "perk-list" }, items.slice(0, 14).map(item => perkListItem(item.perk, item.roll, item.free))) : el("p", { class: "empty-copy", text: "No motes acquired yet." }),
    ),
  );
}

function perkListItem(perk, roll, free) {
  return el("li", {},
    el("span", { class: "perk-marker" }, diffractionMarker(roll, { scale: 0.55, color: constellationColor(roll.constellation) })),
    el("span", {}, el("span", { class: "perk-name", text: perk.name }), el("span", { class: "perk-source", text: `${roll.constellation || "-"} · ${perk.jump || roll.jump || "-"} · ch ${roll.chapter_num}` })),
    el("span", { class: `perk-cost ${free ? "free" : ""}`, text: free ? "FREE" : `${perk.cost || 0} CP` }),
  );
}

function renderConstellationBars() {
  const chapter = chapterAtWord(app.wordPos);
  const progressByName = new Map((chapter.constellation_progress || []).map(row => [row.name, row]));
  return el("div", { class: "panel panel-cut detail-panel" },
    el("div", { class: "panel-title" }, el("span", { class: "pip" }), " Constellation progress"),
    el("div", { class: "body" },
      el("div", { class: "constellation-bars" },
        DEFAULT_CONSTELLATION_ORDER.map(name => {
          const progress = progressByName.get(name) || { discovered: 0, total: 0, discovered_pct: 0 };
          return el("div", { class: "bar-row" },
            el("span", { class: "name", text: name }),
            el("span", { class: "bar" }, el("span", { style: { width: `${progress.discovered_pct || 0}%`, "--bar-color": constellationColor(name) } })),
            el("span", { class: "count", text: `${progress.discovered || 0} / ${progress.total || 0}` }),
          );
        }),
      ),
    ),
  );
}

function renderRollLog() {
  const rows = buildRollLogRows(app.data.story.rolls, app.wordPos, { filter: app.rollFilter, sort: app.rollSort });
  return el("div", { id: "detail-roll-log-panel", class: "panel panel-cut detail-panel full-row" },
    el("div", { class: "panel-title" },
      el("span", { class: "pip" }), " Roll log ",
      el("span", { style: { marginLeft: "12px", color: "var(--dim)", fontWeight: "400", letterSpacing: ".08em", fontSize: "10px" }, text: `${rows.length} shown` }),
      el("span", { class: "roll-log-controls" },
        el("span", { text: "filter" }),
        ["all", "hit", "miss", "multi"].map(filter => el("button", { class: "btn ghost", type: "button", "data-roll-filter": filter, onClick: () => { app.rollFilter = filter; render(); }, text: filter })),
        el("span", { text: "sort" }),
        ["roll", "chapter", "cost"].map(sort => el("button", { class: "btn ghost", type: "button", "data-roll-sort": sort, onClick: () => { app.rollSort = sort; render(); }, text: sort })),
      ),
    ),
    el("div", { class: "body", style: { padding: "0", overflow: "auto" } },
      el("table", { class: "roll-log" },
        el("thead", {}, el("tr", {}, ["#", "Ch", "Word", "Outcome", "Constellation", "Jump", "Mote(s)", "CP paid", "CP avail", ""].map(label => el("th", { text: label })))),
        el("tbody", { id: "detail-roll-log-body" }, rows.slice(0, 250).map(row => renderRollRow(row))),
      ),
    ),
  );
}

function renderRollRow(row) {
  const roll = row.roll;
  return el("tr", { onClick: () => setWordPos(row.clickWord), style: { cursor: "pointer" } },
    el("td", { text: String(row.rollNumber).slice(0, 6) }),
    el("td", { text: row.chapterNum }),
    el("td", { text: Math.round(row.clickWord).toLocaleString() }),
    el("td", { class: `outcome-${row.outcome}`, text: row.outcome.toUpperCase() }),
    el("td", { style: { color: constellationColor(row.constellation) }, text: row.constellation || "-" }),
    el("td", { text: row.jump || "-" }),
    el("td", { class: "perk-cell", text: row.names.length ? row.names.join(" · ") : "-" }),
    el("td", { style: { textAlign: "right" }, text: String(row.paidCost || "-") }),
    el("td", { style: { textAlign: "right" }, text: String(row.availableCp ?? "-") }),
    el("td", {}, diffractionMarker(roll, { scale: 0.5, color: constellationColor(row.constellation) })),
  );
}

let starId = 0;
function diffractionMarker(roll, { scale = 1, color = "#71cef9" } = {}) {
  if (!roll) return null;
  if (roll.outcome === "miss") {
    const cost = roll.miss_cost_estimate || roll.rolled_perk_cost || 100;
    return el("span", { class: "star-wrap", style: { width: `${20 * scale}px`, height: `${20 * scale}px` } }, starSvg("#cfe9ff", cost, 46 * scale));
  }
  const paid = paidRollPerks(roll);
  const free = roll.free_perks || [];
  const cost = rollTotalCost(roll) || 100;
  const size = (paid.length >= 3 ? 34 : paid.length === 2 ? 32 : 28) * scale;
  const positions = paid.length >= 3
    ? [{ x: -8, y: 4, s: .72 }, { x: 8, y: 4, s: .72 }, { x: 0, y: -8, s: .82 }]
    : paid.length === 2
      ? [{ x: -6, y: 2, s: .86 }, { x: 7, y: -2, s: .80 }]
      : [{ x: 0, y: 0, s: 1 }];
  return el("span", { class: "star-wrap", style: { width: `${size}px`, height: `${size}px` } },
    positions.map((pos, index) => el("span", { class: "star-position", style: { transform: `translate(calc(-50% + ${pos.x}px), calc(-50% + ${pos.y}px)) scale(${pos.s})` } }, starSvg(color, paid[index]?.cost || cost, Math.max(46, size * 3.35)))),
    free.slice(0, 3).map((_, index) => el("span", { class: "star-satellite sat-" + index })),
  );
}

function simpleStar({ color = "#71cef9", cost = 100, visualSize = 24, opacity = 1, left = 0.5, top = 0.5 }) {
  return el("span", {
    style: {
      position: "absolute",
      width: "0",
      height: "0",
      left: `${left * 100}%`,
      top: `${top * 100}%`,
      opacity,
      transform: "translate(-50%, -50%)",
    },
  }, starSvg(color, cost, visualSize));
}

function starSvg(color, cost, pixelSize) {
  const id = `ray-${starId++}`;
  const recipe = recipeFor(cost);
  const rays = (count, length, width, offset = 0) => Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index + offset + (index % 2 ? recipe.jitter : -recipe.jitter);
    return svgEl("rect", { x: -length, y: -width / 2, width: length * 2, height: width, rx: width / 2, fill: `url(#${id})`, transform: `rotate(${angle.toFixed(2)})` });
  });
  return svgEl("svg", {
    viewBox: "-50 -50 100 100",
    "aria-hidden": "true",
    focusable: "false",
    style: `position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:${pixelSize}px;height:${pixelSize}px;overflow:visible;opacity:.76;filter:drop-shadow(0 0 1px #fff) drop-shadow(0 0 3px ${color});pointer-events:none`,
  },
    svgEl("defs", {}, svgEl("linearGradient", { id, x1: "0", y1: "0", x2: "1", y2: "0" },
      svgEl("stop", { offset: "0", "stop-color": "transparent" }),
      svgEl("stop", { offset: "0.48", "stop-color": "#fff", "stop-opacity": "0.58" }),
      svgEl("stop", { offset: "0.50", "stop-color": "#fff", "stop-opacity": "0.92" }),
      svgEl("stop", { offset: "0.52", "stop-color": "#fff", "stop-opacity": "0.58" }),
      svgEl("stop", { offset: "1", "stop-color": "transparent" }),
    )),
    svgEl("g", { opacity: "0.68", style: "mix-blend-mode:screen" }, rays(recipe.major, recipe.length, recipe.width)),
    svgEl("g", { opacity: "0.32", style: "mix-blend-mode:screen" }, rays(recipe.minor, recipe.minorLength, recipe.minorWidth, 360 / (recipe.major * 2))),
    svgEl("circle", { r: "2.2", fill: color, opacity: "0.16" }),
    svgEl("circle", { r: "1.4", fill: "#fff" }),
  );
}

function recipeFor(cost) {
  if (cost >= 800) return { major: 12, minor: 12, length: 46, width: 1.05, minorLength: 32, minorWidth: 0.32, jitter: 8 };
  if (cost >= 400) return { major: 8, minor: 8, length: 39, width: 0.92, minorLength: 24, minorWidth: 0.28, jitter: 5 };
  if (cost >= 200) return { major: 6, minor: 6, length: 32, width: 0.78, minorLength: 18, minorWidth: 0.25, jitter: 3 };
  return { major: 4, minor: 4, length: 27, width: 0.7, minorLength: 12, minorWidth: 0.22, jitter: 1 };
}

function starfield(count) {
  let seed = 71;
  const random = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  return el("div", { class: "starfield", "aria-hidden": "true" },
    Array.from({ length: count }, () => el("span", { class: `bg-star ${random() > 0.6 ? "dim" : ""}`, style: { left: `${random() * 100}%`, top: `${random() * 100}%` } })),
  );
}

function documentIcon() {
  return svgEl("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" },
    svgEl("path", { d: "M3.5 1.5 H10 L12.5 4 V14.5 H3.5 Z", fill: "none", stroke: "currentColor", "stroke-width": "1.2", "stroke-linejoin": "round" }),
    svgEl("path", { d: "M10 1.5 V4 H12.5", fill: "none", stroke: "currentColor", "stroke-width": "1.2", "stroke-linejoin": "round" }),
    svgEl("path", { d: "M5.5 7 H10.5 M5.5 9.5 H10.5 M5.5 12 H8.5", stroke: "currentColor", "stroke-width": "1", "stroke-linecap": "round" }),
  );
}

function closeIcon() {
  return svgEl("svg", { viewBox: "0 0 16 16", "aria-hidden": "true" },
    svgEl("path", { d: "M4 4 L12 12 M12 4 L4 12", stroke: "currentColor", "stroke-width": "1.4", "stroke-linecap": "round" }),
  );
}

function centerScrubber() {
  const scroller = document.querySelector(".scrubber-scroller");
  const stack = document.querySelector(".scrubber-stack");
  if (!scroller || !stack || !app.data) return;
  const x = (app.wordPos / Math.max(1, app.data.story.total_words)) * stack.getBoundingClientRect().width;
  const target = clamp(x - scroller.clientWidth / 2, 0, Math.max(0, stack.scrollWidth - scroller.clientWidth));
  scroller.scrollLeft = target;
}

window.addEventListener("keydown", event => {
  if (!app.data) return;
  const active = document.activeElement;
  const tag = active?.tagName;
  const editable = active?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  if (event.key === " ") {
    if (editable) return;
    if (tag === "BUTTON") active.blur();
    togglePlayback();
    event.preventDefault();
    return;
  }
  if (editable) return;
  const step = event.shiftKey ? 2000 : 10000;
  if (event.key === "ArrowRight") setWordPos(app.wordPos + step);
  else if (event.key === "ArrowLeft") setWordPos(app.wordPos - step);
  else if (event.key === "PageDown") setWordPos(app.wordPos + 100000);
  else if (event.key === "PageUp") setWordPos(app.wordPos - 100000);
  else if (event.key === "Home") setWordPos(0);
  else if (event.key === "End") setWordPos(app.data.story.total_words);
});

render();
(async () => {
  try {
    await loadRuntime();
  } catch (error) {
    app.error = error;
  }
  render();
})();

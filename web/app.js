import {
  dataVersionOptionLabel,
  validateDataDocument,
  validateDataPackageManifest,
} from "./data-contract.js";
import {
  buildConstellationProgressIndex,
  paidRollPerks,
  rollMarkerModel,
} from "./viz-model.js";

/* Brockton's Celestial Forge — DAW scrubber app
 *
 * Reads data/derived/chapter_facts.json and renders a multi-track
 * scrubber whose primary axis is total words read.
 *
 *   coordinate system
 *   ─────────────────
 *   Word axis runs from -PRE_ROLL_WORDS (lead-in band) through 0 (start
 *   of chapter 1) to TOTAL_WORDS (end of last chapter). The runtime data
 *   stores visualization positions on that same story-word axis; legacy
 *   CP-word positions are mapped only as a fallback for incomplete rows.
 *
 *   playback
 *   ────────
 *   Speed = "k words per second". 50ms tick interval; advance per tick
 *   = speed * 1000 * (interval/1000) = speed * 50. Default 10 kw/s plays
 *   through 2.7M words in ~4.5 minutes; 100 kw/s in ~27 seconds.
 *
 *   DOM safety
 *   ──────────
 *   We build elements via `el()` + textContent only — no innerHTML or
 *   insertAdjacentHTML, so dynamic strings can't be injected as markup.
 */

const DATA_BASE = "../data/derived";
const PACKAGES_INDEX_URL = "../data/packages.json";
const DATA_PACKAGE_PARAM = "dataPackage";
const DATA_VERSION = "cpfix1";

/* Multi-grab schema helpers: rolls now carry `purchased_perks: [...]`
 * (and `purchased_perk_cost_total`) instead of singular fields.
 */
function rollPrincipalName(r) {
  const arr = r.purchased_perks || [];
  if (arr.length === 0) return null;
  const paid = arr.filter(p => !p.free);
  return (paid[0] || arr[0]).name;
}
function rollTotalCost(r) {
  if (r.purchased_perk_cost_total != null) return r.purchased_perk_cost_total;
  return (r.purchased_perks || [])
    .filter(p => !p.free)
    .reduce((s, p) => s + Number(p.cost || 0), 0);
}

const CONSTELLATION_ORDER = [
  "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
  "Clothing", "Magic", "Quality", "Size",
  "Resources and Durability", "Magitech", "Alchemy",
  "Capstone", "Personal Reality",
];
const CONSTELLATION_COLORS = {
  "Toolkits": "#2f6f9f",
  "Knowledge": "#6a5acd",
  "Vehicles": "#d66b2d",
  "Time": "#7b4fa3",
  "Crafting": "#1f8f6a",
  "Clothing": "#c44f8f",
  "Magic": "#8a63d2",
  "Quality": "#3d7c44",
  "Size": "#a3572a",
  "Resources and Durability": "#8a6f2a",
  "Magitech": "#2c8aa0",
  "Alchemy": "#b48a00",
  "Capstone": "#b63b3b",
  "Personal Reality": "#4f6f3b",
};
const POV_COLORS = [
  "#2a4f7d", "#b86b2c", "#2a7d4f", "#8a4f9f", "#a84f64",
  "#4f7d83", "#8a6f2a", "#6f6f6f", "#7a5c45", "#3d6f9f",
];
const MECHANIC_MARKERS = [
  {
    chapter: "91",
    label: "¹",
    title: "Mechanic change 1: points are accrued and spent differently from here; every other roll attempt is skipped.",
  },
  {
    chapter: "97",
    label: "²",
    title: "Mechanic change 2: points are accrued and spent differently from here; points accrue more slowly and expensive purchases create recovery cooldowns.",
  },
];

const SKY_CLUSTER_LAYOUT = {
  "Toolkits": { r: 0.15, a: -92, size: 0.19 },
  "Knowledge": { r: 0.50, a: -152, size: 0.16 },
  "Vehicles": { r: 0.62, a: -38, size: 0.14 },
  "Time": { r: 0.45, a: 32, size: 0.13 },
  "Crafting": { r: 0.58, a: 158, size: 0.14 },
  "Clothing": { r: 0.68, a: 112, size: 0.13 },
  "Magic": { r: 0.54, a: 82, size: 0.14 },
  "Quality": { r: 0.70, a: -178, size: 0.14 },
  "Size": { r: 0.58, a: -114, size: 0.13 },
  "Resources and Durability": { r: 0.72, a: -76, size: 0.15 },
  "Magitech": { r: 0.60, a: 8, size: 0.13 },
  "Alchemy": { r: 0.42, a: 128, size: 0.13 },
  "Capstone": { r: 0.76, a: 54, size: 0.15 },
  "Personal Reality": { r: 0.78, a: -132, size: 0.16 },
};

const SKY_DEFAULT_PREFS = {
  focus: false,
  art: true,
  wireframes: true,
  labels: true,
  rotate: true,
};

// localStorage keys (versioned).
const LS_BOOKMARK = "bcf:bookmark:word_position";
const LS_SPEED = "bcf:playback:speed:v2";
const LS_ZOOM = "bcf:timeline:zoom";
const LS_THEME = "bcf:theme";   // "auto" | "light" | "dark" (must match the inline script in index.html)
const LS_SKY_PREFS = "bcf:sky:prefs:v1";
const LS_VERSION = "bcf:storage:version";
const STORAGE_VERSION = "3";   // bumped when pre-roll changed from 100k to 5k

// Pre-roll lead-in: empty band before chapter 1 word=0. Useful for
// animations to settle before content arrives.
const PRE_ROLL_WORDS = 5_000;
const DEFAULT_SPEED = 10;
const BASELINE_ZOOM_MULTIPLIER = 30;
const FIT_ZOOM = 1 / BASELINE_ZOOM_MULTIPLIER;
const DEFAULT_ZOOM = 1;
const MIN_ZOOM = FIT_ZOOM;
const MAX_ZOOM = 2;
const ZOOM_STEP = 0.1;

// Playback constants.
const TICK_INTERVAL_MS = 50;   // 20fps
const MANUAL_SCROLL_HOLD_MS = 3_000;

// ---------- DOM helpers --------------------------------------------------

function el(tag, props, ...children) {
  const e = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v == null) continue;
      if (k === "class") e.className = v;
      else if (k === "style" && typeof v === "object") {
        for (const [styleName, styleValue] of Object.entries(v)) {
          if (styleValue == null) continue;
          if (styleName.startsWith("--")) e.style.setProperty(styleName, styleValue);
          else e.style[styleName] = styleValue;
        }
      }
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("data-")) e.setAttribute(k, v);
      else e[k] = v;
    }
  }
  for (const child of children) {
    if (child == null) continue;
    e.appendChild(typeof child === "string"
      ? document.createTextNode(child) : child);
  }
  return e;
}
function svgEl(tag, props, ...children) {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v == null) continue;
      if (k === "class") e.setAttribute("class", v);
      else if (k === "text") e.textContent = v;
      else e.setAttribute(k, v);
    }
  }
  for (const child of children) {
    if (child == null) continue;
    e.appendChild(typeof child === "string"
      ? document.createTextNode(child) : child);
  }
  return e;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function $(id) { return document.getElementById(id); }

// ---------- data loading -------------------------------------------------

async function fetchJSON(url) {
  const r = await fetch(url, {
    cache: "no-store",
  });
  if (!r.ok) throw new Error(`failed to load ${url}: ${r.status}`);
  return r.json();
}

async function loadJSON(base, path) {
  return fetchJSON(`${base}/${path}?v=${DATA_VERSION}`);
}

async function loadPackageIndex() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get(DATA_PACKAGE_PARAM);
  const isLocal = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
  if (isLocal && !requested) {
    return null;
  }
  try {
    return await fetchJSON(`${PACKAGES_INDEX_URL}?v=${DATA_VERSION}`);
  } catch (err) {
    return null;
  }
}

function selectedPackageBase(packageIndex) {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get(DATA_PACKAGE_PARAM);
  const packages = Array.isArray(packageIndex?.packages) ? packageIndex.packages : [];
  const selected = packages.find(p => p.package_id === requested);
  if (!selected) {
    return { base: DATA_BASE, packageId: null };
  }
  return { base: `../${selected.path}`, packageId: selected.package_id };
}

async function loadDataPackage(base) {
  const manifest = await loadJSON(base, "data_package.json");
  const contract = validateDataPackageManifest(manifest);
  return { base, manifest, contract };
}

function dataCreditLabel(pkg, isDefault = false) {
  return dataVersionOptionLabel(pkg, isDefault).replace(/^BCF data\s+/, "v");
}

async function loadContractJSON(dataPackage, name, { optional = false } = {}) {
  const meta = dataPackage.contract.files[name];
  if (!meta) {
    if (optional) return null;
    throw new Error(`Data package manifest is missing required file metadata: ${name}.`);
  }
  try {
    const doc = await loadJSON(dataPackage.base, meta.path);
    const validation = validateDataDocument(name, doc, meta, { optional });
    if (!validation.ok) {
      console.warn(validation.reason);
      return null;
    }
    return doc;
  } catch (err) {
    if (optional) {
      console.warn(`optional data not loaded: ${name}`, err);
      return null;
    }
    throw err;
  }
}

function attachDataPackageSelector(packageIndex, activePackageId, activeManifest) {
  const packages = Array.isArray(packageIndex?.packages) ? packageIndex.packages : [];
  const activePackage = packages.find(pkg => pkg.package_id === activePackageId) || activeManifest;
  const slot = $("data-package-slot") || document.body;

  const selector = el("label", { id: "data-package-selector" },
    el("span", { text: "Data" }));
  const defaultId = packageIndex?.default_package_id;
  if (packages.length <= 1) {
    selector.appendChild(el("span", {
      class: "data-package-static",
      text: dataCreditLabel(activePackage, activePackage?.package_id === defaultId),
    }));
  } else {
    const select = el("select", { id: "data-package-select", "aria-label": "Data version" });
    for (const pkg of packages) {
      const label = dataCreditLabel(pkg, pkg.package_id === defaultId);
      select.appendChild(el("option", {
        value: pkg.package_id,
        text: label,
        selected: pkg.package_id === activePackageId,
      }));
    }
    select.addEventListener("change", () => {
      const params = new URLSearchParams(window.location.search);
      if (select.value === defaultId) params.delete(DATA_PACKAGE_PARAM);
      else params.set(DATA_PACKAGE_PARAM, select.value);
      const qs = params.toString();
      window.location.href = `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`;
    });
    selector.appendChild(select);
  }
  slot.replaceChildren(selector);
}

// ---------- coordinate model ---------------------------------------------

function buildCoordinateModel(facts) {
  const chapters = facts.chapters;
  const totalWords = chapters[chapters.length - 1].cumulative_words_through_chapter;
  const totalCpWords = chapters[chapters.length - 1].cumulative_cp_earning_words;

  const chapterSpans = chapters.map(c => ({
    chapter_num: c.chapter_num,
    start_word: c.cumulative_words_through_chapter - c.total_word_count,
    end_word: c.cumulative_words_through_chapter,
    start_cp: c.cumulative_cp_earning_words - c.cp_earning_word_count,
    end_cp: c.cumulative_cp_earning_words,
    chapter: c,
  }));
  const idxOf = new Map(chapters.map((c, i) => [c.chapter_num, i]));

  return { chapters, chapterSpans, idxOf, totalWords, totalCpWords };
}

function chapterAtWord(model, wordPos) {
  if (wordPos < 0) return null;
  if (wordPos >= model.totalWords) return model.chapters[model.chapters.length - 1];
  for (const span of model.chapterSpans) {
    if (wordPos >= span.start_word && wordPos < span.end_word) return span.chapter;
  }
  return model.chapters[model.chapters.length - 1];
}

function rollWordPosition(model, roll, chapter, fallbackIndex = 0, fallbackTotal = 1) {
  const displayChapterNum = roll.display_chapter_num || chapter.chapter_num;
  const span = model.chapterSpans[model.idxOf.get(displayChapterNum)] ||
    model.chapterSpans[model.idxOf.get(chapter.chapter_num)];
  if (roll.display_word_position_epub != null) {
    return roll.display_word_position_epub;
  }
  const cpPosition = roll.predicted_word_position_epub;
  if (cpPosition == null) {
    if (roll.source_kind === "trigger") return span.start_word;
    const chapterWidth = Math.max(1, span.end_word - span.start_word);
    const slot = (fallbackIndex + 1) / (fallbackTotal + 1);
    return span.start_word + chapterWidth * slot;
  }
  if (span.end_cp > span.start_cp) {
    const cpFrac = (cpPosition - span.start_cp) /
                   (span.end_cp - span.start_cp);
    return span.start_word + cpFrac * (span.end_word - span.start_word);
  }
  return (span.start_word + span.end_word) / 2;
}

function shadowWordRange(model, facts, sp) {
  function purchaseWord(chapter, roll) {
    const fallbackRolls = chapter.rolls.filter(r => r.predicted_word_position_epub == null);
    const fallbackIndex = fallbackRolls.indexOf(roll);
    return rollWordPosition(model, roll, chapter,
      Math.max(0, fallbackIndex), fallbackRolls.length || 1);
  }

  const triggerChapter = facts.chapters.find(c => c.chapter_num === sp.trigger_chapter_num);
  const mappedStart = sp.trigger_word_position_epub ?? 0;
  const mappedEnd = sp.shadow_end_word_position_epub ?? mappedStart;
  let triggerWord = mappedStart;
  if (triggerChapter) {
    const triggerRoll = triggerChapter.rolls.find(r =>
      sp.trigger_perk_id && r.purchased_perk_id === sp.trigger_perk_id) ||
      triggerChapter.rolls.find(r =>
        (r.purchased_perks || []).some(p =>
          p.name === sp.trigger_perk_name &&
          Number(p.cost) === Number(sp.trigger_perk_cost)));
    if (triggerRoll) {
      triggerWord = purchaseWord(triggerChapter, triggerRoll);
    }
  }

  let nextPurchaseWord = Infinity;
  for (const chapter of facts.chapters) {
    for (const roll of chapter.rolls) {
      if (roll.outcome !== "hit" && roll.evidence_kind !== "untracked_acquisition") continue;
      const word = purchaseWord(chapter, roll);
      if (word > triggerWord + 0.5 && word < nextPurchaseWord) {
        nextPurchaseWord = word;
      }
    }
  }

  const mappedWidth = Math.max(0, mappedEnd - mappedStart);
  const fallbackWidth = Number(sp.shadow_word_length) || 0;
  const rawEnd = triggerWord + Math.max(mappedWidth, fallbackWidth);
  return [triggerWord, Math.max(triggerWord, Math.min(rawEnd, nextPurchaseWord))];
}

// ---------- track rendering ----------------------------------------------

function pctOf(model, wordPos) {
  const fullSpan = PRE_ROLL_WORDS + model.totalWords;
  return ((wordPos + PRE_ROLL_WORDS) / fullSpan) * 100;
}

function renderTracks(model, facts) {
  const stack = $("track-stack");
  stack.appendChild(el("div", {
    class: "preroll-band",
    style: { left: "0%", width: `${pctOf(model, 0).toFixed(4)}%` },
  }));
  renderRealWorldDateTrack(model);
  renderChaptersTrack(model);
  renderPovTrack(model);
  renderRegimeChangeMarkers(model);
  renderShadowsTrack(model, facts);
  renderRollsTrack(model, facts);
  renderAxisTrack(model);
  renderLegend();
}

function layoutTimelineTracks() {
  layoutChapterLabels();
  layoutAxisLabels();
  layoutRollDots();
}

function clampZoom(z) {
  if (!Number.isFinite(z)) return DEFAULT_ZOOM;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(z * 100) / 100));
}

function normalizeStoredZoom(z) {
  if (!Number.isFinite(z)) return DEFAULT_ZOOM;
  return clampZoom(z > MAX_ZOOM ? z / BASELINE_ZOOM_MULTIPLIER : z);
}

function timelineWidthForZoom(zoom) {
  const container = $("scrubber-container");
  const baseWidth = container.clientWidth || container.getBoundingClientRect().width || 1;
  return Math.max(baseWidth, Math.round(baseWidth * BASELINE_ZOOM_MULTIPLIER * clampZoom(zoom)));
}

function applyTimelineZoom(state, options = {}) {
  const zoom = clampZoom(state.zoom);
  state.zoom = zoom;
  const stack = $("track-stack");
  stack.style.width = `${timelineWidthForZoom(zoom)}px`;
  stack.dataset.zoomDetail = zoom >= 0.54 ? "exact" : zoom >= 0.27 ? "high" : zoom >= 0.14 ? "medium" : "low";
  layoutTimelineTracks();
  $("timeline-zoom").value = String(zoom);
  $("zoom-readout").textContent = zoom <= FIT_ZOOM ? "fit" : `${zoom.toFixed(2).replace(/\.?0+$/, "")}×`;
  saveZoom(zoom);
  if (options.center) {
    state.scrollFollow.pausedManualLock = false;
    centerWordInView(state, state.currentWord);
  } else {
    updateScrollFollow(state);
  }
}

function wordPixel(state, wordPos) {
  const stack = $("track-stack");
  return (pctOf(state.model, wordPos) / 100) * stack.getBoundingClientRect().width;
}

function timelineMaxScroll() {
  const container = $("scrubber-container");
  return Math.max(0, $("track-stack").getBoundingClientRect().width - container.clientWidth);
}

function naturalScrollLeftForWord(state, wordPos) {
  const container = $("scrubber-container");
  return Math.max(0, Math.min(timelineMaxScroll(), wordPixel(state, wordPos) - container.clientWidth / 2));
}

function setTimelineScroll(state, scrollLeft) {
  const container = $("scrubber-container");
  state.scrollFollow.ignoreProgrammaticScroll = true;
  container.scrollLeft = Math.max(0, Math.min(timelineMaxScroll(), scrollLeft));
  requestAnimationFrame(() => { state.scrollFollow.ignoreProgrammaticScroll = false; });
}

function centerWordInView(state, wordPos) {
  setTimelineScroll(state, naturalScrollLeftForWord(state, wordPos));
}

function updateScrollFollow(state, options = {}) {
  const container = $("scrubber-container");
  const target = naturalScrollLeftForWord(state, state.currentWord);
  if (options.force) {
    state.scrollFollow.pausedManualLock = false;
    state.scrollFollow.catchupStartedAt = 0;
    setTimelineScroll(state, target);
    return;
  }

  if (!state.playing) {
    if (!state.scrollFollow.pausedManualLock) setTimelineScroll(state, target);
    return;
  }

  const now = performance.now();
  if (now < state.scrollFollow.holdUntil) return;

  const delta = target - container.scrollLeft;
  if (Math.abs(delta) < 1) {
    state.scrollFollow.catchupStartedAt = 0;
    setTimelineScroll(state, target);
    return;
  }

  if (!state.scrollFollow.catchupStartedAt) state.scrollFollow.catchupStartedAt = now;
  const seconds = (now - state.scrollFollow.catchupStartedAt) / 1000;
  const easing = Math.min(0.28, 0.025 + seconds * 0.035);
  setTimelineScroll(state, container.scrollLeft + delta * easing);
}

function getISOWeek(date) {
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  target.setUTCDate(target.getUTCDate() + 4 - (target.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil(((target - yearStart) / 86400000 + 1) / 7);
}

function renderRealWorldDateTrack(model) {
  const track = $("track-dates");
  const yearSeen = new Set();
  const monthSeen = new Set();
  const weekSeen = new Set();

  for (const span of model.chapterSpans) {
    const date = new Date(span.chapter.published_at);
    const dateStr = span.chapter.published_at.slice(0, 10);
    const left = `${pctOf(model, span.start_word).toFixed(4)}%`;
    const year = date.getFullYear();
    const monthKey = `${year}-${date.getMonth()}`;
    const weekKey = `${year}-${getISOWeek(date)}`;

    track.appendChild(el("div", {
      class: "date-tick chapter",
      style: { left },
      title: `${dateStr}: ch ${span.chapter.chapter_num} — ${span.chapter.full_title}`,
    }));
    track.appendChild(el("div", {
      class: "date-label chapter-label",
      text: dateStr.slice(5),
      style: { left },
    }));
    if (!weekSeen.has(weekKey)) {
      weekSeen.add(weekKey);
      track.appendChild(el("div", {
        class: "date-tick week",
        style: { left },
        title: `Week of ${dateStr}: ch ${span.chapter.chapter_num}`,
      }));
    }
    if (!monthSeen.has(monthKey)) {
      monthSeen.add(monthKey);
      const monthLabel = date.toLocaleString("en-US", { month: "short" });
      track.appendChild(el("div", {
        class: "date-tick month",
        style: { left },
        title: `${monthLabel} ${year}: first chapter is ch ${span.chapter.chapter_num}, published ${dateStr}`,
      }));
      track.appendChild(el("div", {
        class: "date-label month-label",
        text: monthLabel,
        style: { left },
      }));
    }
    if (!yearSeen.has(year)) {
      yearSeen.add(year);
      track.appendChild(el("div", {
        class: "date-tick year",
        style: { left },
        title: `${year}: first chapter at or after Jan 1 is ch ${span.chapter.chapter_num}, published ${dateStr}`,
      }));
      track.appendChild(el("div", {
        class: "date-label year-label",
        text: String(year),
        style: { left },
      }));
    }
  }
}

function renderRegimeChangeMarkers(model) {
  const track = $("track-markers");
  for (const marker of MECHANIC_MARKERS) {
    const span = model.chapterSpans[model.idxOf.get(marker.chapter)];
    if (!span) continue;
    track.appendChild(el("div", {
      class: "regime-change-marker",
      style: { left: `${pctOf(model, span.end_word).toFixed(4)}%` },
      title: marker.title,
    }, el("span", { text: marker.label })));
  }
}

function renderPovTrack(model) {
  const track = $("track-pov");
  const povColor = new Map([["Joe", CONSTELLATION_COLORS.Toolkits]]);
  for (const span of model.chapterSpans) {
    let sectionStart = span.start_word;
    const total = Math.max(1, span.chapter.total_word_count);
    for (const section of span.chapter.sections || []) {
      const width = (section.word_count / total) * (span.end_word - span.start_word);
      const pov = section.pov_character || section.marker_kind || "unknown";
      if (!povColor.has(pov)) {
        povColor.set(pov, POV_COLORS[povColor.size % POV_COLORS.length]);
      }
      const title = [
        section.header || `section ${section.section_index}`,
        `POV: ${pov}`,
        `${fmt(section.word_count)} words`,
        `marker: ${section.marker_kind}`,
        `classification: ${section.classification} (${section.classification_confidence})`,
      ].join(" · ");
      track.appendChild(el("div", {
        class: `pov-segment ${section.counts_for_cp ? "cp-earning" : "non-cp"}`,
        style: {
          left: `${pctOf(model, sectionStart).toFixed(4)}%`,
          width: `${Math.max(0.02, pctOf(model, sectionStart + width) - pctOf(model, sectionStart)).toFixed(4)}%`,
          backgroundColor: povColor.get(pov),
        },
        title,
      }));
      sectionStart += width;
    }
  }
}

function renderChaptersTrack(model) {
  const track = $("track-chapters");
  for (const span of model.chapterSpans) {
    const chap = span.chapter;
    const ch_int = parseInt(chap.chapter_num.split(".")[0], 10);
    const isSubChapter = chap.chapter_num.includes(".");
    const isMajor = !isSubChapter && ch_int % 10 === 0;
    const leftPct = pctOf(model, span.start_word);
    const tick = el("button", {
      type: "button",
      class: `chap-tick ${isMajor ? "major" : "minor"}`,
      style: { left: `${leftPct.toFixed(4)}%` },
      title: `ch ${chap.chapter_num} — ${chap.full_title} · published ${chap.published_at.slice(0, 10)} · last edited ${chap.last_edited_at || "unknown"}`,
      "data-chapter-num": chap.chapter_num,
    });
    tick._chapter = chap;
    tick._wordPos = span.start_word;
    track.appendChild(tick);
    const label = el("div", {
      class: `chap-label ${isMajor ? "major" : isSubChapter ? "sub" : "minor"}`,
      text: chap.chapter_num,
      style: { left: `${leftPct.toFixed(4)}%` },
    });
    label._wordPct = leftPct;
    track.appendChild(label);
  }
}

function renderShadowsTrack(model, facts) {
  const track = $("track-rolls");
  for (const sp of facts.shadow_periods) {
    const [a, b] = shadowWordRange(model, facts, sp);
    const widthPct = pctOf(model, b) - pctOf(model, a);
    if (widthPct <= 0) continue;
    track.appendChild(el("div", {
      class: "shadow-bar",
      style: { left: `${pctOf(model, a).toFixed(4)}%`,
               width: `${Math.max(0.02, widthPct).toFixed(4)}%` },
      title: `${sp.trigger_perk_cost} CP shadow: ${sp.trigger_perk_name} ` +
             `(ch ${sp.trigger_chapter_num} → ch ${sp.shadow_end_chapter_num})`,
    }));
  }
}

function renderRollsTrack(model, facts) {
  const track = $("track-rolls");
  track.appendChild(el("div", { class: "roll-lane-label hit-label", text: "hits" }));
  track.appendChild(el("div", { class: "roll-lane-label miss-label", text: "misses / unknown" }));

  for (const c of facts.chapters) {
    const fallbackRolls = c.rolls.filter(r => r.predicted_word_position_epub == null);
    for (const r of c.rolls) {
      const fallbackIndex = fallbackRolls.indexOf(r);
      const wp = rollWordPosition(model, r, c, Math.max(0, fallbackIndex), fallbackRolls.length || 1);
      const leftPct = pctOf(model, wp);
      const dot = el("button", {
        type: "button",
        class: `roll-dot ${rollClass(r)} ${rollMarkerClass(r)}`,
        style: rollDotStyle(r, leftPct),
        "data-chapter-num": c.chapter_num,
        "data-roll-number": r.roll_number ?? "",
        title: rollDotTitle(r, c),
      });
      renderRollMarker(dot, r);
      dot._roll = r;
      dot._chapter = c;
      dot._wordPos = wp;
      dot._wordPct = leftPct;
      dot._dotSize = rollDotSize(r);
      track.appendChild(dot);
    }
  }
}

function rollMarkerClass(r) {
  return `marker-${rollMarkerModel(r).kind}`;
}

function renderRollMarker(dot, roll) {
  const marker = rollMarkerModel(roll);
  const colorKey = roll.outcome === "miss" || roll.outcome === "unknown"
    ? "miss"
    : colorKeyForConstellation(roll.constellation);
  const system = el("span", {
    class: `roll-star-system ${colorKey} ${marker.isMissLike ? "is-miss-like" : ""}`,
    "aria-hidden": "true",
  });

  const sourceCount = marker.kind.startsWith("trinary") ? 3 :
    marker.kind.startsWith("binary") ? 2 : 1;
  const offsets = sourceOffsets(sourceCount);
  offsets.forEach((offset, idx) => {
    const source = el("span", {
      class: `star-source ${colorKey} source-${idx + 1}`,
      style: {
        "--source-x": `${offset.x}px`,
        "--source-y": `${offset.y}px`,
        "--source-scale": String(offset.scale),
      },
    });
    source.appendChild(renderStarSourceSvg(markerVisualCost(roll, marker)));
    system.appendChild(source);
  });

  const companions = companionOffsets((roll.free_perks || []).length);
  companions.forEach((offset, idx) => {
    const freePerk = roll.free_perks[idx] || {};
    system.appendChild(el("span", {
      class: `star-companion ${colorKeyForConstellation(freePerk.constellation || roll.constellation)}`,
      style: {
        "--companion-x": `${offset.x}px`,
        "--companion-y": `${offset.y}px`,
        "--companion-scale": String(offset.scale),
      },
    }));
  });

  if (marker.isUntracked) {
    system.appendChild(el("span", { class: "star-untracked-ring" }));
  }
  dot.appendChild(system);
}

function markerVisualCost(roll, marker) {
  return marker.cost ?? roll.rolled_perk_cost ?? roll.miss_cost_estimate ??
    nextVisualCostAbove(roll.available_cp);
}

let starSourceSvgId = 0;

function starRecipeForCost(cost) {
  const base = cost >= 1000
    ? { major: 16, minor: 16, length: 50, width: 1.18, minorLength: 40, minorWidth: 0.34, jitter: 10 }
    : cost >= 800
      ? { major: 12, minor: 10, length: 46, width: 1.05, minorLength: 32, minorWidth: 0.3, jitter: 8 }
      : cost >= 600
        ? { major: 8, minor: 8, length: 41, width: 0.95, minorLength: 27, minorWidth: 0.28, jitter: 6 }
        : cost >= 400
          ? { major: 6, minor: 4, length: 36, width: 0.86, minorLength: 20, minorWidth: 0.24, jitter: 4 }
          : cost >= 300
            ? { major: 4, minor: 4, length: 33, width: 0.78, minorLength: 17, minorWidth: 0.22, jitter: 3 }
            : cost >= 200
              ? { major: 4, minor: 0, length: 30, width: 0.72, minorLength: 0, minorWidth: 0, jitter: 0 }
              : { major: 2, minor: 0, length: 26, width: 0.66, minorLength: 0, minorWidth: 0, jitter: 0 };
  return {
    ...base,
    length: base.length * 1.06,
    minorLength: base.minorLength * 1.18,
  };
}

function starRayRects(recipe, gradientId, secondary = false) {
  const count = secondary ? recipe.minor : recipe.major;
  const length = secondary ? recipe.minorLength : recipe.length;
  const width = secondary ? recipe.minorWidth : recipe.width;
  const offset = secondary ? 360 / (recipe.major * 2) : 0;
  return Array.from({ length: count }, (_, idx) => {
    const angle = (360 / count) * idx + offset + (idx % 2 ? recipe.jitter : -recipe.jitter);
    const finalLength = length * (secondary ? 1 : (idx % 3 === 0 ? 1.12 : 1));
    return svgEl("rect", {
      x: (-finalLength).toFixed(2),
      y: (-width / 2).toFixed(2),
      width: (finalLength * 2).toFixed(2),
      height: width.toFixed(2),
      rx: (width / 2).toFixed(2),
      fill: `url(#${gradientId})`,
      transform: `rotate(${angle.toFixed(2)})`,
    });
  });
}

function renderStarSourceSvg(cost) {
  starSourceSvgId += 1;
  const spikeId = `star-spike-gradient-${starSourceSvgId}`;
  const recipe = starRecipeForCost(cost || 0);
  const luminosity = cost >= 1000 ? 1.32 : cost >= 800 ? 1.2 : cost >= 600 ? 1.05 :
    cost >= 400 ? 0.86 : cost >= 300 ? 0.76 : cost >= 200 ? 0.64 : 0.52;
  return svgEl("svg", {
    class: "star-source-svg",
    viewBox: "-50 -50 100 100",
    "aria-hidden": "true",
    focusable: "false",
  },
    svgEl("defs", null,
      svgEl("linearGradient", { id: spikeId, x1: "0", y1: "0", x2: "1", y2: "0" },
        svgEl("stop", { offset: "0", "stop-color": "var(--spike-fade)" }),
        svgEl("stop", { offset: ".28", "stop-color": "var(--spike-tint)", "stop-opacity": ".16" }),
        svgEl("stop", { offset: ".46", "stop-color": "var(--star-core)", "stop-opacity": ".68" }),
        svgEl("stop", { offset: ".5", "stop-color": "var(--star-core)", "stop-opacity": ".98" }),
        svgEl("stop", { offset: ".54", "stop-color": "var(--star-core)", "stop-opacity": ".68" }),
        svgEl("stop", { offset: ".72", "stop-color": "var(--spike-tint)", "stop-opacity": ".16" }),
        svgEl("stop", { offset: "1", "stop-color": "var(--spike-fade)" }),
      ),
    ),
    svgEl("g", { class: "star-svg-spikes star-svg-spikes-primary" },
      ...starRayRects(recipe, spikeId),
    ),
    svgEl("g", { class: "star-svg-spikes star-svg-spikes-secondary" },
      ...starRayRects(recipe, spikeId, true),
    ),
    svgEl("circle", { class: "star-svg-tint", r: (2.6 + luminosity * 1.8).toFixed(2) }),
    svgEl("circle", { class: "star-svg-core", r: (1.2 + luminosity * 0.62).toFixed(2) }),
  );
}

function rollClass(r) {
  if (r.evidence_kind === "untracked_acquisition") return "untracked";
  if (r.outcome === "hit") return "hit";
  if (r.outcome === "miss") return "miss";
  return "unknown";
}

function rollDotStyle(r, leftPct) {
  const size = rollDotSize(r);
  return {
    left: `${leftPct.toFixed(4)}%`,
    width: `${size}px`,
    height: `${size}px`,
    marginLeft: `${-(size / 2)}px`,
    "--roll-size": `${size}px`,
    "--marker-color": rollDotColor(r),
  };
}

function sourceOffsets(count) {
  if (count >= 3) {
    return [
      { x: -8, y: 4, scale: 0.78 },
      { x: 8, y: 4, scale: 0.78 },
      { x: 0, y: -7, scale: 0.92 },
    ];
  }
  if (count === 2) {
    return [
      { x: -5, y: 1, scale: 0.88 },
      { x: 6, y: -1, scale: 0.78 },
    ];
  }
  return [{ x: 0, y: 0, scale: 1 }];
}

function companionOffsets(count) {
  if (count === 1) return [{ x: 8, y: 6, scale: 1 }];
  if (count === 2) {
    return [
      { x: -7, y: 7, scale: 1 },
      { x: 7, y: 7, scale: 0.94 },
    ];
  }
  if (count === 3) {
    return [
      { x: 0, y: -9, scale: 1 },
      { x: 8, y: 6, scale: 0.94 },
      { x: -8, y: 6, scale: 0.88 },
    ];
  }
  const positions = [
    { x: 0, y: -10, scale: 1 },
    { x: 9, y: -3, scale: 0.94 },
    { x: 6, y: 8, scale: 0.88 },
    { x: -6, y: 8, scale: 0.82 },
    { x: -9, y: -3, scale: 0.78 },
    { x: 0, y: 0, scale: 0.72 },
  ];
  return positions.slice(0, count);
}

function colorKeyForConstellation(constellation) {
  const key = String(constellation || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return key || "unknown";
}

function rollDotColor(r) {
  if ((r.outcome === "hit" || r.outcome === "miss" ||
      r.evidence_kind === "untracked_acquisition") && r.constellation) {
    return CONSTELLATION_COLORS[r.constellation] || "var(--hit)";
  }
  return "var(--unknown)";
}

const ROLL_COST_SIZES = [
  [0, 18],
  [100, 22],
  [200, 25],
  [300, 28],
  [400, 31],
  [600, 36],
  [800, 40],
];

function sizeForCost(cost, fallback = 6) {
  const numericCost = Number(cost);
  if (!Number.isFinite(numericCost)) return fallback;
  let best = ROLL_COST_SIZES[0][1];
  for (const [costFloor, size] of ROLL_COST_SIZES) {
    if (numericCost >= costFloor) best = size;
  }
  return best;
}

function nextVisualCostAbove(availableCp) {
  const available = Number(availableCp);
  if (!Number.isFinite(available)) return 200;
  for (const [cost] of ROLL_COST_SIZES) {
    if (cost > available) return cost;
  }
  return available + 100;
}

function rollDotSize(r) {
  const marker = rollMarkerModel(r);
  if (!marker.isMissLike) {
    const base = sizeForCost(marker.cost, 24);
    if (marker.paidCount >= 3) return Math.max(40, base + 8);
    if (marker.paidCount === 2) return Math.max(36, base + 6);
    if (marker.freeCount > 0) return Math.max(34, base + 4);
    return base;
  }
  const missCost = r.rolled_perk_cost ?? r.miss_cost_estimate ??
    nextVisualCostAbove(r.available_cp);
  return Math.max(24, sizeForCost(missCost, 24));
}

function rollDotTitle(r, c) {
  const name = rollPrincipalName(r) ||
    (r.outcome === "miss" ? "missed grab" : r.outcome);
  const bits = [`ch ${c.chapter_num}`, name];
  if (r.constellation) bits.push(r.constellation);
  let cost = rollTotalCost(r);
  if (!cost) {
    cost = r.purchased_perk_cost ?? r.rolled_perk_cost ?? r.miss_cost_estimate;
  }
  if (cost != null) bits.push(`${cost} CP`);
  if (r.outcome === "miss" && r.available_cp != null) {
    bits.push(`${r.available_cp} available`);
  }
  return bits.join(" · ");
}

function freePerkTitle(freePerk, roll, chapter) {
  const bits = [`ch ${chapter.chapter_num}`, freePerk.name, "free with " + (rollPrincipalName(roll) || "roll")];
  if (freePerk.constellation) bits.push(freePerk.constellation);
  if (freePerk.jump) bits.push(freePerk.jump);
  return bits.join(" · ");
}

function renderLegend() {
  renderConstellationLegend();
  renderMarkerMeaningLegend();
  renderMarkerCostLegend();
}

function legendStar(colorKey, cost, options = {}) {
  const system = el("span", {
    class: `legend-star roll-star-system ${colorKey} ${options.miss ? "is-miss-like" : ""}`,
    "aria-hidden": "true",
  });
  const sourceCount = options.sources || 1;
  sourceOffsets(sourceCount).forEach((offset, idx) => {
    const source = el("span", {
      class: `star-source ${colorKey} source-${idx + 1}`,
      style: {
        "--source-x": `${offset.x}px`,
        "--source-y": `${offset.y}px`,
        "--source-scale": String(offset.scale),
      },
    });
    source.appendChild(renderStarSourceSvg(cost));
    system.appendChild(source);
  });
  companionOffsets(options.companions || 0).forEach((offset, idx) => {
    system.appendChild(el("span", {
      class: `star-companion ${colorKey} companion-${idx + 1}`,
      style: {
        "--companion-x": `${offset.x}px`,
        "--companion-y": `${offset.y}px`,
        "--companion-scale": String(offset.scale),
      },
    }));
  });
  if (options.untracked) system.appendChild(el("span", { class: "star-untracked-ring" }));
  return system;
}

function renderConstellationLegend() {
  const container = $("constellation-legend");
  if (!container) return;
  clear(container);
  for (const name of CONSTELLATION_ORDER) {
    const colorKey = colorKeyForConstellation(name);
    container.appendChild(el("span", { class: "swatch-row" },
      legendStar(colorKey, 300),
      el("span", { text: name })));
  }
}

function renderMarkerMeaningLegend() {
  const container = $("marker-meaning-legend");
  if (!container) return;
  clear(container);
  [
    ["simple perk", legendStar("toolkits", 300)],
    ["perk with add-ons", legendStar("toolkits", 300, { companions: 2 })],
    ["binary paid grab", legendStar("toolkits", 300, { sources: 2 })],
    ["trinary with add-ons", legendStar("toolkits", 400, { sources: 3, companions: 2 })],
    ["miss or unknown", legendStar("miss", 300, { miss: true })],
  ].forEach(([label, marker]) => {
    container.appendChild(el("div", { class: "legend-row marker-example-row" },
      marker,
      el("span", { text: label })));
  });
}

function renderMarkerCostLegend() {
  const container = $("marker-cost-legend");
  if (!container) return;
  clear(container);
  [100, 200, 300, 400, 600, 800, 1000].forEach(cost => {
    container.appendChild(el("span", { class: "cost-example" },
      legendStar("toolkits", cost),
      el("span", { text: `${cost} CP` })));
  });
}

function renderAxisTrack(model) {
  const track = $("track-axis");
  const step = 1_000;
  for (let w = 0; w <= model.totalWords; w += step) {
    const leftPct = pctOf(model, w);
    const tickClass = w % 10_000 === 0 ? "major" : w % 5_000 === 0 ? "mid" : "minor";
    track.appendChild(el("div", {
      class: `axis-tick ${tickClass}`,
      style: { left: `${leftPct.toFixed(4)}%` },
    }));
    if (w % 5_000 === 0) {
      const label = el("div", {
        class: `axis-label ${w === 0 ? "origin-label " : ""}${w % 50_000 === 0 ? "milestone-50 " : ""}${w % 25_000 === 0 ? "milestone-25 " : ""}${w % 10_000 === 0 ? "milestone-10" : ""}`,
        text: w === 0 ? "0" : `${(w / 1000).toFixed(0)}k`,
        style: { left: `${leftPct.toFixed(4)}%` },
      });
      label._wordPct = leftPct;
      track.appendChild(label);
    }
  }
}

function layoutItemsInRows(items, rowTops, options = {}) {
  const rows = rowTops.map(top => ({ top, lastRight: -Infinity }));
  const gap = options.gap ?? 4;
  const widthOf = options.widthOf || (item => item.el.offsetWidth || 1);
  const sorted = [...items].sort((a, b) => a.x - b.x);
  for (const item of sorted) {
    const width = widthOf(item);
    const left = item.x - width / 2;
    const right = item.x + width / 2;
    let row = rows.find(candidate => left - gap >= candidate.lastRight);
    if (!row) {
      row = rows.reduce((best, candidate) =>
        candidate.lastRight < best.lastRight ? candidate : best, rows[0]);
    }
    item.el.style.top = `${row.top}px`;
    row.lastRight = Math.max(row.lastRight, right + gap);
  }
}

function layoutChapterLabels() {
  const stack = $("track-stack");
  const width = stack.getBoundingClientRect().width || 1;
  const labels = Array.from($("track-chapters").querySelectorAll(".chap-label"))
    .filter(elm => getComputedStyle(elm).display !== "none")
    .map(elm => ({ el: elm, x: (elm._wordPct / 100) * width }));
  layoutItemsInRows(labels, [2, 16, 28], { gap: 5 });
}

function layoutAxisLabels() {
  const stack = $("track-stack");
  const width = stack.getBoundingClientRect().width || 1;
  const labels = Array.from($("track-axis").querySelectorAll(".axis-label"))
    .filter(elm => getComputedStyle(elm).display !== "none")
    .map(elm => ({ el: elm, x: (elm._wordPct / 100) * width }));
  layoutItemsInRows(labels, [2, 16], { gap: 3 });
  const origin = $("track-axis").querySelector(".origin-label");
  if (origin) origin.style.top = "16px";
}

function rollDotLane(dot) {
  if (dot.classList.contains("miss") || dot.classList.contains("unknown")) return "miss";
  return "hit";
}

function layoutRollDots() {
  const stack = $("track-stack");
  const width = stack.getBoundingClientRect().width || 1;
  const compact = $("track-rolls").getBoundingClientRect().height < 120;
  const lanes = compact
    ? {
        hit: [18, 6, 30, 42],
        miss: [66, 78, 54, 90],
      }
    : {
        hit: [26, 12, 40, 54],
        miss: [82, 96, 68, 110],
      };
  for (const [lane, rowTops] of Object.entries(lanes)) {
    const dots = Array.from($("track-rolls").querySelectorAll(".roll-dot"))
      .filter(dot => rollDotLane(dot) === lane)
      .map(dot => ({
        el: dot,
        x: (dot._wordPct / 100) * width,
        size: dot._dotSize || dot.offsetWidth || 6,
      }));
    layoutItemsInRows(dots, rowTops, {
      gap: 2,
      widthOf: item => item.size,
    });
  }
}

// ---------- state-dependent panels --------------------------------------

function fmt(n) { return Number(n).toLocaleString("en-US"); }
function fmtKWords(n) {
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n / 1000).toFixed(0)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function buildCumulativeIndex(facts) {
  let paid = 0, free = 0, hits = 0, otherRolls = 0;
  const cumByCh = new Map();
  const progressIndex = buildConstellationProgressIndex(
    facts,
    CONSTELLATION_ORDER,
  );
  for (const c of facts.chapters) {
    paid += c.paid_perks_gained;
    free += c.free_perks_gained;
    hits += c.hits_count;
    otherRolls += c.misses_count + c.unknowns_count;
    cumByCh.set(c.chapter_num, { paid, free, hits, otherRolls });
  }
  return {
    cumByCh,
    constProgressByCh: progressIndex.byChapter,
    constMax: progressIndex.constMax,
  };
}

function renderState(state) {
  const { model, facts, cumIdx, currentWord } = state;
  const inPreroll = currentWord < 0;
  const ch = chapterAtWord(model, currentWord);
  const idx = ch ? model.idxOf.get(ch.chapter_num) : -1;
  if (state.selectedChapterNum && (!ch || ch.chapter_num !== state.selectedChapterNum)) {
    state.selectedChapterNum = null;
  }

  // Playhead
  const playhead = $("scrubber-playhead");
  const pct = pctOf(model, Math.max(-PRE_ROLL_WORDS, Math.min(currentWord, model.totalWords)));
  playhead.style.left = `${pct.toFixed(4)}%`;
  playhead.setAttribute("aria-valuenow",
    String(Math.round(currentWord + PRE_ROLL_WORDS)));
  playhead.setAttribute("aria-valuemax",
    String(Math.round(model.totalWords + PRE_ROLL_WORDS)));

  // Readout
  const stateEl = $("readout-state");
  if (inPreroll) { stateEl.textContent = "pre-roll"; stateEl.className = "preroll"; }
  else { stateEl.textContent = state.playing ? "playing" : "paused";
         stateEl.className = state.playing ? "playing" : ""; }
  $("readout-chapter").textContent = ch ? `ch ${ch.chapter_num}` : "—";
  $("readout-title").textContent = ch
    ? ch.full_title.replace(/^\d+(\.\d+)?\s*/, "")
    : "lead-in";
  $("readout-words").textContent = inPreroll
    ? `−${fmt(Math.round(Math.abs(currentWord)))} words (pre-roll)`
    : `${fmt(Math.round(currentWord))} / ${fmt(model.totalWords)} words`;
  const sv = $("readout-sv-link");
  if (ch && ch.post_url) { sv.href = ch.post_url; sv.hidden = false; }
  else { sv.hidden = true; }

  const cum = (!inPreroll && ch)
    ? cumIdx.cumByCh.get(ch.chapter_num)
    : { paid: 0, free: 0, hits: 0, otherRolls: 0 };
  $("stat-chapters").textContent = inPreroll ? "0" : fmt(idx + 1);
  $("stat-words").textContent = fmtKWords(Math.max(0, currentWord));
  $("stat-perks-paid").textContent = fmt(cum.paid);
  $("stat-perks-free").textContent = fmt(cum.free);
  $("stat-rolls-hits").textContent = fmt(cum.hits);
  $("stat-rolls-other").textContent = fmt(cum.otherRolls);

  renderSelectedChapter(state);
  const constProgress = (!inPreroll && ch)
    ? cumIdx.constProgressByCh.get(ch.chapter_num)
    : { rows: [] };
  renderConstellations(constProgress.rows, cumIdx.constMax);
  renderRecent(state, ch, inPreroll);
  updateSkyState(state);
}

function clearSelectedChapter(state) {
  state.selectedChapterNum = null;
  renderSelectedChapter(state);
}

function selectChapter(state, chapterNum) {
  state.selectedChapterNum = chapterNum;
}

function renderSelectedChapter(state) {
  const panel = $("chapter-detail-panel");
  if (!state.selectedChapterNum) {
    panel.hidden = true;
    return;
  }
  const ch = state.model.chapters[state.model.idxOf.get(state.selectedChapterNum)];
  if (!ch) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  renderThisChapter(ch, false);
}

function renderThisChapter(ch, inPreroll) {
  const meta = $("this-chapter-meta");
  const list = $("this-chapter-perks");
  clear(meta);
  clear(list);

  if (inPreroll || !ch) {
    meta.appendChild(el("em", null, "Pre-roll lead-in. The story has not yet begun."));
    list.appendChild(el("li", { class: "empty" },
      el("span", { class: "perk-name", style: { color: "var(--gray-3)" } }, "—")));
    return;
  }

  meta.appendChild(el("strong", null, ch.full_title));
  meta.appendChild(document.createTextNode(
    ` · ${fmt(ch.total_word_count)} words` +
    ` · mechanics phase ${ch.point_calculation_regime}` +
    ` · ${ch.paid_perks_gained} paid + ${ch.free_perks_gained} free` +
    ` · ${ch.hits_count} hits / ${ch.misses_count + ch.unknowns_count} others`));
  meta.appendChild(el("br"));
  const editStr = ch.last_edited_known
    ? ` · last edited ${ch.last_edited_at}`
    : "";
  meta.appendChild(el("span",
    { style: { color: "var(--gray-3)" } },
    `published ${ch.published_at.slice(0, 10)}${editStr} · ${ch.likes} likes`));

  if (ch.rolls.length === 0) {
    list.appendChild(el("li", { class: "empty" },
      el("span", { class: "perk-name", style: { color: "var(--gray-3)" } },
        "No rolls in this chapter.")));
    return;
  }
  for (const r of ch.rolls) {
    const tagEl = el("span",
      { class: r.outcome === "hit" ? "perk-cost" : "perk-cost free" },
      r.outcome === "hit" ? (r.constellation || "?")
        : (r.outcome === "miss" ? "miss" : "unknown"));
    const name = rollPrincipalName(r) || (r.outcome === "hit" ? "(unattributed)" : "missed grab");
    const left = el("span", null, el("span", { class: "perk-name" }, name));
    if (r.free_perks.length) {
      left.appendChild(el("span", { class: "perk-source" },
        ` + ${r.free_perks.length} free`));
    }
    if (r.outcome === "miss" && r.available_cp != null) {
      const attempted = r.rolled_perk_cost ?? r.miss_cost_estimate;
      const text = attempted != null
        ? ` ${attempted} CP > ${r.available_cp} CP`
        : ` ${r.available_cp} CP available`;
      left.appendChild(el("span", { class: "perk-source" }, text));
    }
    list.appendChild(el("li", null, left, tagEl));
  }
}

function renderConstellations(rows, scaleMax) {
  const container = $("constellation-bars");
  clear(container);
  const max = Math.max(1, scaleMax);
  if (!rows || rows.length === 0) {
    container.appendChild(el("span", { class: "const-empty" }, "No constellations opened yet."));
    return;
  }
  for (const row of rows) {
    const { name, count, discoveredPct, complete } = row;
    const pct = (count / max) * 100;
    container.appendChild(el("span", {
      class: `const-name ${complete ? "complete" : ""}`,
    }, name));
    container.appendChild(el("span", {
      class: "const-bar-wrap",
      style: { display: "block", height: "12px" },
    }, el("span", {
      class: "const-bar",
      style: {
        display: "block",
        width: `${pct.toFixed(2)}%`,
        height: "100%",
        backgroundColor: CONSTELLATION_COLORS[name],
      },
    })));
    container.appendChild(el("span", {
      class: `const-count ${complete ? "complete" : ""}`,
    }, fmt(count)));
    container.appendChild(el("span", {
      class: `const-discovered ${complete ? "complete" : ""}`,
    }, `${discoveredPct}%`));
  }
}

function renderRecent(state, ch, inPreroll) {
  const list = $("recent-perks");
  clear(list);
  if (inPreroll || !ch) {
    list.appendChild(el("li", { class: "empty" },
      el("span", { class: "perk-name", style: { color: "var(--gray-3)" } }, "—")));
    return;
  }
  const idx = state.model.idxOf.get(ch.chapter_num);
  const collected = [];
  for (let i = idx; i >= 0 && collected.length < 10; i--) {
    const c = state.facts.chapters[i];
    for (const r of [...c.rolls].reverse()) {
      const name = rollPrincipalName(r);
      if (r.outcome !== "hit" || !name) continue;
      collected.push({ roll: r, chapter: c, name });
      if (collected.length >= 10) break;
    }
  }
  if (collected.length === 0) {
    list.appendChild(el("li", { class: "empty" },
      el("span", { class: "perk-name", style: { color: "var(--gray-3)" } },
        "No acquisitions yet.")));
    return;
  }
  for (const { roll, chapter, name } of collected) {
    const left = el("span", { class: "perk-name" }, name);
    list.appendChild(el("li", null,
      left,
      el("span", { class: "perk-cost" }, roll.constellation || "?"),
      el("span", { class: "perk-chapter" }, `ch ${chapter.chapter_num}`)));
  }
}

// ---------- planetarium sky ----------------------------------------------

function hexToRgb(hex) {
  const m = String(hex || "").replace("#", "");
  if (m.length !== 6) return [255, 255, 255];
  return [
    parseInt(m.slice(0, 2), 16),
    parseInt(m.slice(2, 4), 16),
    parseInt(m.slice(4, 6), 16),
  ];
}

function rgba(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function degToRad(deg) {
  return (deg * Math.PI) / 180;
}

function skyNormName(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function readSkyPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(LS_SKY_PREFS));
    return { ...SKY_DEFAULT_PREFS, ...(saved || {}) };
  } catch {
    return { ...SKY_DEFAULT_PREFS };
  }
}

function saveSkyPrefs(prefs) {
  try {
    localStorage.setItem(LS_SKY_PREFS, JSON.stringify(prefs));
  } catch {}
}

function skyHash(n) {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function makeSkyDust(count) {
  const dust = [];
  for (let i = 0; i < count; i++) {
    const r = Math.sqrt(skyHash(i + 1)) * 0.985;
    const a = skyHash(i + 1001) * Math.PI * 2;
    dust.push({
      x: Math.cos(a) * r,
      y: Math.sin(a) * r,
      size: 0.45 + skyHash(i + 2001) * 1.45,
      phase: skyHash(i + 3001) * Math.PI * 2,
      tint: skyHash(i + 4001),
    });
  }
  return dust;
}

function buildSkyModel(wireframes) {
  const clusterRows = wireframes?.cluster_constellations || [];
  const jumpRows = wireframes?.jump_constellations || [];
  const clusterByName = new Map(clusterRows.map(c => [c.name, c]));
  const jumpByKey = new Map();
  const perkIndex = new Map();

  for (const jump of jumpRows) {
    const key = `${jump.constellation}::${jump.jump}`;
    jumpByKey.set(key, jump);
    for (const star of jump.stars || []) {
      const name = skyNormName(star.perk_name);
      if (!name) continue;
      const entries = perkIndex.get(name) || [];
      entries.push({ jump, star });
      perkIndex.set(name, entries);
    }
  }

  const clusters = CONSTELLATION_ORDER.map(name => {
    const data = clusterByName.get(name) || { name, cluster_vertices: [] };
    const vertices = data.cluster_vertices || [];
    const vertexByJump = new Map(vertices.map(v => [v.jump, v]));
    const jumps = new Map();
    let revealSeq = Infinity;
    for (const v of vertices) {
      const jump = jumpByKey.get(`${name}::${v.jump}`);
      if (jump) {
        jumps.set(v.jump, jump);
        for (const star of jump.stars || []) {
          if (star.acquired_epub_sequence != null) {
            revealSeq = Math.min(revealSeq, Number(star.acquired_epub_sequence));
          }
        }
      }
    }
    return {
      name,
      color: CONSTELLATION_COLORS[name] || "#dfe6f1",
      data,
      vertices,
      vertexByJump,
      jumps,
      revealSeq: Number.isFinite(revealSeq) ? revealSeq : null,
    };
  });

  return { clusters, jumpByKey, perkIndex };
}

function buildRollResolutionMaps(resolutions) {
  const byChapterRoll = new Map();
  const byRoll = new Map();
  for (const r of resolutions?.rolls || []) {
    if (r.roll_number == null) continue;
    byChapterRoll.set(`${r.chapter_num}::${r.roll_number}`, r);
    if (!byRoll.has(String(r.roll_number))) byRoll.set(String(r.roll_number), r);
  }
  return { byChapterRoll, byRoll };
}

function lookupRollResolution(sky, chapter, roll) {
  if (!sky || !roll || roll.roll_number == null) return null;
  return sky.resolutions.byChapterRoll.get(`${chapter.chapter_num}::${roll.roll_number}`)
    || sky.resolutions.byRoll.get(String(roll.roll_number))
    || null;
}

function findPerkInSky(sky, perkName, constellation) {
  const entries = sky.model.perkIndex.get(skyNormName(perkName)) || [];
  if (constellation) {
    const exact = entries.find(entry => entry.jump.constellation === constellation);
    if (exact) return exact;
  }
  return entries[0] || null;
}

function cheapestMissCandidate(resolution, available) {
  let best = null;
  for (const candidate of resolution?.outstanding_perks_with_cost_gt_banked || []) {
    const cost = Number(candidate.cost);
    if (!Number.isFinite(cost) || cost <= available) continue;
    if (!best || cost < Number(best.cost)) best = candidate;
  }
  return best;
}

function numericOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function skyRollInfo(state, chapter, roll, wordPos) {
  const sky = state.sky;
  const resolution = lookupRollResolution(sky, chapter, roll);
  const rawAvailable = numericOrNull(roll.available_cp)
    ?? numericOrNull(resolution?.banked_at_roll)
    ?? numericOrNull(resolution?.curator_banked_before)
    ?? numericOrNull(roll.purchased_perk_cost)
    ?? numericOrNull(resolution?.curator_cost)
    ?? 100;
  const resolutionOutcome = resolution?.curator_outcome
    ? resolution.curator_outcome.toLowerCase()
    : null;
  const baseOutcome = roll.outcome === "hit" ? "hit" : (resolutionOutcome || roll.outcome || "unknown");
  const missCandidate = baseOutcome === "hit" ? null : cheapestMissCandidate(resolution, rawAvailable);
  let cost = numericOrNull(roll.rolled_perk_cost)
    ?? numericOrNull(roll.purchased_perk_cost)
    ?? numericOrNull(resolution?.curator_cost)
    ?? numericOrNull(missCandidate?.cost);
  let perkName = rollPrincipalName(roll)
    || resolution?.curator_perk_name
    || missCandidate?.name
    || (baseOutcome === "hit" ? "acquired mote" : "unresolved mote");
  let constellation = roll.constellation
    || resolution?.curator_constellation
    || missCandidate?.constellation
    || null;
  const indexed = findPerkInSky(sky, perkName, constellation);
  if (!constellation && indexed) constellation = indexed.jump.constellation;
  const jump = roll.purchased_perk_jump || indexed?.jump.jump || null;

  if (cost == null && baseOutcome === "hit") cost = 100;
  const available = baseOutcome === "hit" && cost != null
    ? Math.max(rawAvailable, cost)
    : rawAvailable;
  const outcome = baseOutcome === "hit" ? "hit"
    : (cost != null && cost > available ? "miss" : baseOutcome);

  return {
    chapter,
    roll,
    wordPos,
    resolution,
    available,
    rawAvailable,
    cost,
    outcome,
    perkName,
    constellation: constellation || "Toolkits",
    jump,
    source: resolution?.banked_at_roll_source || "visual fallback",
  };
}

function findActiveSkyRoll(state, chapter) {
  if (!chapter || !state.sky) return null;
  const displayed = [];
  for (const owner of state.facts.chapters) {
    for (const roll of owner.rolls || []) {
      const displayChapterNum = roll.display_chapter_num || owner.chapter_num;
      if (displayChapterNum !== chapter.chapter_num) continue;
      if (roll.outcome !== "hit" && roll.outcome !== "miss" &&
          roll.outcome !== "unknown" && roll.evidence_kind !== "untracked_acquisition") {
        continue;
      }
      displayed.push({ owner, roll });
    }
  }
  if (!displayed.length) return null;
  const fallbackRolls = displayed
    .map(item => item.roll)
    .filter(r => r.predicted_word_position_epub == null);
  let best = null;
  for (const { owner, roll } of displayed) {
    const fallbackIndex = fallbackRolls.indexOf(roll);
    const wordPos = rollWordPosition(
      state.model, roll, owner, Math.max(0, fallbackIndex), fallbackRolls.length || 1);
    const distance = Math.abs(state.currentWord - wordPos);
    if (!best || distance < best.distance) {
      best = { owner, roll, wordPos, distance };
    }
  }
  if (!best) return null;
  return skyRollInfo(state, best.owner, best.roll, best.wordPos);
}

function setSkyButtonPressed(id, pressed) {
  const btn = $(id);
  if (btn) btn.setAttribute("aria-pressed", String(!!pressed));
}

function reflectSkyPrefs(state) {
  const prefs = state.sky.prefs;
  setSkyButtonPressed("sky-focus-toggle", prefs.focus);
  setSkyButtonPressed("sky-art-toggle", prefs.art);
  setSkyButtonPressed("sky-wire-toggle", prefs.wireframes);
  setSkyButtonPressed("sky-label-toggle", prefs.labels);
  setSkyButtonPressed("sky-rotate-toggle", prefs.rotate);
  document.body.classList.toggle("sky-focus-mode", prefs.focus);
}

function attachSkyControls(state) {
  const bindings = [
    ["sky-focus-toggle", "focus"],
    ["sky-art-toggle", "art"],
    ["sky-wire-toggle", "wireframes"],
    ["sky-label-toggle", "labels"],
    ["sky-rotate-toggle", "rotate"],
  ];
  for (const [id, key] of bindings) {
    const btn = $(id);
    if (!btn) continue;
    btn.addEventListener("click", () => {
      state.sky.prefs[key] = !state.sky.prefs[key];
      saveSkyPrefs(state.sky.prefs);
      reflectSkyPrefs(state);
      if (key === "focus") {
        window.setTimeout(() => applyTimelineZoom(state, { center: true }), 60);
      }
    });
  }
  reflectSkyPrefs(state);
}

function skyFrame(canvas) {
  const rect = canvas.getBoundingClientRect();
  const w = rect.width || 1;
  const h = rect.height || 1;
  const radius = Math.max(120, Math.min(w, h) * 0.455);
  return { w, h, cx: w / 2, cy: h / 2, radius };
}

function resizeSkyCanvas(state) {
  const sky = state.sky;
  const rect = sky.canvas.getBoundingClientRect();
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const width = Math.max(1, Math.round(rect.width * dpr));
  const height = Math.max(1, Math.round(rect.height * dpr));
  if (sky.canvas.width !== width || sky.canvas.height !== height) {
    sky.canvas.width = width;
    sky.canvas.height = height;
    sky.dpr = dpr;
  }
}

function clusterScreenPosition(frame, cluster, worldRotation) {
  const layout = SKY_CLUSTER_LAYOUT[cluster.name] || { r: 0.6, a: 0, size: 0.13 };
  const angle = degToRad(layout.a) + worldRotation;
  return {
    x: frame.cx + Math.cos(angle) * layout.r * frame.radius,
    y: frame.cy + Math.sin(angle) * layout.r * frame.radius,
    size: layout.size * frame.radius,
    rotation: worldRotation * 0.55 + degToRad(layout.a) * 0.18,
  };
}

function localPoint(v, size, rotation) {
  const x = (v?.x || 0) * size;
  const y = -(v?.y || 0) * size;
  const c = Math.cos(rotation);
  const s = Math.sin(rotation);
  return { x: x * c - y * s, y: x * s + y * c };
}

function skyTargetPoint(state, frame, active, worldRotation) {
  const cluster = state.sky.model.clusters.find(c => c.name === active.constellation)
    || state.sky.model.clusters[0];
  const pos = clusterScreenPosition(frame, cluster, worldRotation);
  const vertex = active.jump ? cluster.vertexByJump.get(active.jump) : null;
  if (!vertex) return { x: pos.x, y: pos.y, cluster, pos };
  const p = localPoint(vertex, pos.size * 1.45, pos.rotation);
  return { x: pos.x + p.x, y: pos.y + p.y, cluster, pos };
}

function drawSkyBackground(ctx, frame, sky, time, worldRotation) {
  const gradient = ctx.createRadialGradient(
    frame.cx - frame.radius * 0.2,
    frame.cy - frame.radius * 0.18,
    frame.radius * 0.08,
    frame.cx,
    frame.cy,
    frame.radius * 1.08);
  gradient.addColorStop(0, "#172037");
  gradient.addColorStop(0.46, "#080d1b");
  gradient.addColorStop(1, "#02040a");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, frame.w, frame.h);

  ctx.save();
  ctx.beginPath();
  ctx.arc(frame.cx, frame.cy, frame.radius, 0, Math.PI * 2);
  ctx.clip();
  ctx.fillStyle = "#04070e";
  ctx.globalAlpha = 0.28;
  ctx.fillRect(frame.cx - frame.radius, frame.cy - frame.radius, frame.radius * 2, frame.radius * 2);

  for (const p of sky.dust) {
    const c = Math.cos(worldRotation * 0.12);
    const s = Math.sin(worldRotation * 0.12);
    const x0 = p.x * c - p.y * s;
    const y0 = p.x * s + p.y * c;
    const x = frame.cx + x0 * frame.radius;
    const y = frame.cy + y0 * frame.radius;
    const twinkle = 0.38 + Math.sin(time * 0.0015 + p.phase) * 0.16;
    ctx.globalAlpha = twinkle;
    ctx.fillStyle = p.tint > 0.86 ? "#ffd9a6" : p.tint > 0.68 ? "#a9d6ff" : "#f6fbff";
    ctx.beginPath();
    ctx.arc(x, y, p.size, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = "rgba(170, 190, 220, 0.22)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(frame.cx, frame.cy, frame.radius, 0, Math.PI * 2);
  ctx.stroke();
  ctx.strokeStyle = "rgba(110, 163, 214, 0.12)";
  for (const ring of [0.33, 0.66]) {
    ctx.beginPath();
    ctx.arc(frame.cx, frame.cy, frame.radius * ring, 0, Math.PI * 2);
    ctx.stroke();
  }
  for (let i = 0; i < 8; i++) {
    const a = worldRotation + (i * Math.PI) / 4;
    ctx.beginPath();
    ctx.moveTo(frame.cx + Math.cos(a) * frame.radius * 0.08,
      frame.cy + Math.sin(a) * frame.radius * 0.08);
    ctx.lineTo(frame.cx + Math.cos(a) * frame.radius,
      frame.cy + Math.sin(a) * frame.radius);
    ctx.stroke();
  }
  ctx.restore();
}

function drawSkyGlyph(ctx, name, color) {
  ctx.fillStyle = rgba(color, 0.10);
  ctx.strokeStyle = rgba(color, 0.40);
  ctx.lineWidth = 0.055;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  switch (name) {
    case "Toolkits":
      ctx.moveTo(-0.9, -0.25); ctx.lineTo(-0.48, -0.58); ctx.lineTo(-0.18, -0.28);
      ctx.lineTo(0.82, 0.52); ctx.lineTo(0.62, 0.76); ctx.lineTo(-0.38, -0.04);
      ctx.lineTo(-0.68, 0.28); ctx.lineTo(-0.92, 0.06); ctx.lineTo(-0.64, -0.1);
      break;
    case "Knowledge":
      ctx.moveTo(-0.9, -0.55); ctx.lineTo(0, -0.28); ctx.lineTo(0.9, -0.55);
      ctx.lineTo(0.9, 0.55); ctx.lineTo(0, 0.28); ctx.lineTo(-0.9, 0.55); ctx.closePath();
      break;
    case "Vehicles":
      ctx.moveTo(-0.9, 0.2); ctx.lineTo(-0.55, -0.28); ctx.lineTo(0.2, -0.34);
      ctx.lineTo(0.72, 0.1); ctx.lineTo(0.9, 0.42); ctx.lineTo(-0.9, 0.42); ctx.closePath();
      break;
    case "Time":
      ctx.moveTo(-0.72, -0.72); ctx.lineTo(0.72, -0.72); ctx.lineTo(0, 0);
      ctx.lineTo(0.72, 0.72); ctx.lineTo(-0.72, 0.72); ctx.lineTo(0, 0); ctx.closePath();
      break;
    case "Crafting":
      ctx.moveTo(-0.75, -0.45); ctx.lineTo(-0.28, -0.78); ctx.lineTo(0.08, -0.46);
      ctx.lineTo(-0.12, -0.2); ctx.lineTo(0.78, 0.54); ctx.lineTo(0.52, 0.8);
      ctx.lineTo(-0.34, 0.04); ctx.lineTo(-0.56, 0.24); ctx.lineTo(-0.78, 0.02);
      break;
    case "Clothing":
      ctx.moveTo(-0.52, -0.72); ctx.lineTo(-0.9, -0.32); ctx.lineTo(-0.62, 0.02);
      ctx.lineTo(-0.48, 0.76); ctx.lineTo(0.48, 0.76); ctx.lineTo(0.62, 0.02);
      ctx.lineTo(0.9, -0.32); ctx.lineTo(0.52, -0.72); ctx.lineTo(0.22, -0.44);
      ctx.lineTo(0, -0.62); ctx.lineTo(-0.22, -0.44); ctx.closePath();
      break;
    case "Magic":
      ctx.moveTo(-0.86, 0.56); ctx.quadraticCurveTo(0.06, 0.82, 0.82, 0.52);
      ctx.lineTo(0.28, 0.18); ctx.lineTo(0.02, -0.84); ctx.lineTo(-0.34, 0.2); ctx.closePath();
      break;
    case "Quality":
      ctx.moveTo(0, -0.86); ctx.lineTo(0.78, -0.22); ctx.lineTo(0.46, 0.84);
      ctx.lineTo(-0.46, 0.84); ctx.lineTo(-0.78, -0.22); ctx.closePath();
      break;
    case "Size":
      ctx.moveTo(-0.68, 0.72); ctx.lineTo(0, 0.32); ctx.lineTo(0.68, 0.72);
      ctx.moveTo(-0.48, 0.18); ctx.lineTo(0, -0.12); ctx.lineTo(0.48, 0.18);
      ctx.moveTo(-0.28, -0.28); ctx.lineTo(0, -0.54); ctx.lineTo(0.28, -0.28);
      break;
    case "Resources and Durability":
      ctx.moveTo(0, -0.82); ctx.lineTo(0.72, -0.52); ctx.lineTo(0.58, 0.34);
      ctx.quadraticCurveTo(0.28, 0.72, 0, 0.9);
      ctx.quadraticCurveTo(-0.28, 0.72, -0.58, 0.34);
      ctx.lineTo(-0.72, -0.52); ctx.closePath();
      break;
    case "Magitech":
      for (let i = 0; i < 10; i++) {
        const a = (i / 10) * Math.PI * 2;
        const r = i % 2 ? 0.64 : 0.86;
        const x = Math.cos(a) * r;
        const y = Math.sin(a) * r;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.moveTo(-0.18, -0.76); ctx.lineTo(0.18, -0.08); ctx.lineTo(-0.04, -0.08);
      ctx.lineTo(0.22, 0.76);
      break;
    case "Alchemy":
      ctx.moveTo(-0.22, -0.86); ctx.lineTo(0.22, -0.86); ctx.lineTo(0.22, -0.24);
      ctx.quadraticCurveTo(0.72, 0.1, 0.58, 0.62);
      ctx.quadraticCurveTo(0, 0.94, -0.58, 0.62);
      ctx.quadraticCurveTo(-0.72, 0.1, -0.22, -0.24); ctx.closePath();
      break;
    case "Capstone":
      ctx.moveTo(-0.9, 0.7); ctx.lineTo(-0.42, 0.08); ctx.lineTo(-0.12, 0.26);
      ctx.lineTo(0.12, -0.78); ctx.lineTo(0.42, 0.12); ctx.lineTo(0.9, 0.7);
      break;
    case "Personal Reality":
      ctx.moveTo(-0.78, 0.08); ctx.lineTo(0, -0.72); ctx.lineTo(0.78, 0.08);
      ctx.lineTo(0.62, 0.08); ctx.lineTo(0.62, 0.78); ctx.lineTo(-0.62, 0.78);
      ctx.lineTo(-0.62, 0.08); ctx.closePath();
      break;
    default:
      ctx.arc(0, 0, 0.72, 0, Math.PI * 2);
  }
  ctx.fill();
  ctx.stroke();
}

function drawClusterArt(ctx, cluster, screen, alpha) {
  ctx.save();
  ctx.translate(screen.x, screen.y);
  ctx.rotate(screen.rotation);
  ctx.scale(screen.size, screen.size);
  ctx.globalAlpha = alpha;
  ctx.shadowColor = rgba(cluster.color, 0.65);
  ctx.shadowBlur = 14 / Math.max(0.5, screen.size / 80);
  drawSkyGlyph(ctx, cluster.name, cluster.color);
  ctx.restore();
}

function jumpHasAcquired(jump, chapterIdx) {
  return (jump?.stars || []).some(star =>
    star.acquired_epub_sequence != null && Number(star.acquired_epub_sequence) <= chapterIdx);
}

function drawWireframeCluster(ctx, cluster, screen, chapterIdx, active) {
  const vertices = cluster.vertices || [];
  if (!vertices.length) return;
  ctx.save();
  ctx.translate(screen.x, screen.y);
  ctx.rotate(screen.rotation);
  ctx.scale(screen.size, screen.size);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = rgba(cluster.color, active ? 0.82 : 0.46);
  ctx.lineWidth = active ? 0.025 : 0.018;
  if (vertices.length > 1) {
    ctx.beginPath();
    vertices.forEach((v, idx) => {
      const x = v.x || 0;
      const y = -(v.y || 0);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
  for (const v of vertices) {
    const jump = cluster.jumps.get(v.jump);
    const acquired = jumpHasAcquired(jump, chapterIdx);
    const r = active && active.jump === v.jump ? 0.06 : acquired ? 0.04 : 0.026;
    ctx.beginPath();
    ctx.fillStyle = acquired ? "#ffe7a3" : rgba("#dfe6f1", 0.58);
    ctx.strokeStyle = active && active.jump === v.jump ? "#ffffff" : rgba(cluster.color, 0.72);
    ctx.lineWidth = 0.012;
    ctx.arc(v.x || 0, -(v.y || 0), r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawActiveJumpStars(ctx, cluster, screen, active, chapterIdx) {
  if (!active?.jump) return;
  const jump = cluster.jumps.get(active.jump);
  const vertex = cluster.vertexByJump.get(active.jump);
  if (!jump || !vertex) return;
  const stars = jump.stars || [];
  const activeName = skyNormName(active.perkName);
  ctx.save();
  ctx.translate(screen.x, screen.y);
  ctx.rotate(screen.rotation);
  ctx.scale(screen.size, screen.size);
  const anchorX = vertex.x || 0;
  const anchorY = -(vertex.y || 0);
  const mini = Math.min(0.34, Math.max(0.18, 0.11 + stars.length * 0.006));

  if (stars.length > 1) {
    ctx.beginPath();
    stars.forEach((star, idx) => {
      const x = anchorX + (star.x || 0) * mini;
      const y = anchorY - (star.y || 0) * mini;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = rgba(cluster.color, 0.26);
    ctx.lineWidth = 0.01;
    ctx.stroke();
  }

  for (const star of stars) {
    const acquired = star.acquired_epub_sequence != null &&
      Number(star.acquired_epub_sequence) <= chapterIdx;
    const isActive = activeName && skyNormName(star.perk_name) === activeName;
    const x = anchorX + (star.x || 0) * mini;
    const y = anchorY - (star.y || 0) * mini;
    const baseR = 0.018 + (Number(star.size) || 0.25) * 0.035;
    ctx.beginPath();
    ctx.fillStyle = isActive ? "#fff7bd" : acquired ? "#ffe7a3" : rgba("#dfe6f1", 0.42);
    ctx.strokeStyle = isActive ? "#ffffff" : star.cost === 0 ? "#80e1e9" : rgba(cluster.color, 0.8);
    ctx.lineWidth = isActive ? 0.018 : 0.01;
    ctx.arc(x, y, isActive ? baseR * 1.7 : baseR, 0, Math.PI * 2);
    if (star.cost === 0 && !isActive) {
      ctx.stroke();
    } else {
      ctx.fill();
      ctx.stroke();
    }
  }
  ctx.restore();
}

function drawSkyLabel(ctx, cluster, screen, alpha, active) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = active ? "#ffffff" : "#c9d4e4";
  ctx.font = active ? "700 14px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    : "600 12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.shadowColor = "rgba(0, 0, 0, 0.8)";
  ctx.shadowBlur = 5;
  ctx.fillText(cluster.name, screen.x, screen.y + screen.size * (active ? 1.14 : 0.98));
  ctx.restore();
}

function drawGrabGauge(ctx, active, target, frame) {
  if (active.cost == null || active.available == null) return;
  const success = active.cost <= active.available;
  const max = Math.max(100, active.cost, active.available, 800);
  const availableR = 10 + Math.sqrt(active.available / max) * 32;
  const costR = 10 + Math.sqrt(active.cost / max) * 32;
  const vx = target.x - frame.cx;
  const vy = target.y - frame.cy;
  const len = Math.max(1, Math.hypot(vx, vy));
  const px = -vy / len;
  const py = vx / len;
  let gx = target.x + px * 62;
  let gy = target.y + py * 62;
  gx = Math.max(78, Math.min(frame.w - 78, gx));
  gy = Math.max(84, Math.min(frame.h - 84, gy));

  ctx.save();
  ctx.shadowColor = success ? "rgba(255, 218, 122, 0.8)" : "rgba(255, 94, 94, 0.85)";
  ctx.shadowBlur = 18;
  ctx.strokeStyle = "rgba(255, 226, 154, 0.88)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(gx, gy, availableR, 0, Math.PI * 2);
  ctx.stroke();

  ctx.shadowBlur = 10;
  ctx.strokeStyle = success ? "rgba(128, 225, 233, 0.95)" : "rgba(255, 98, 98, 0.95)";
  ctx.fillStyle = success ? "rgba(128, 225, 233, 0.12)" : "rgba(255, 98, 98, 0.12)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(gx, gy, costR, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  ctx.shadowBlur = 4;
  ctx.fillStyle = "#ffffff";
  ctx.font = "700 12px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`${active.available} / ${active.cost}`, gx, gy - 2);
  ctx.fillStyle = success ? "#b8f3d1" : "#ffb7b7";
  ctx.font = "700 10px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
  ctx.fillText(success ? "enough CP" : "too costly", gx, gy + 13);
  ctx.restore();
}

function drawBeam(ctx, active, target, frame, time) {
  const pulse = 0.65 + Math.sin(time * 0.006) * 0.22;
  const grad = ctx.createLinearGradient(frame.cx, frame.cy, target.x, target.y);
  grad.addColorStop(0, "rgba(255, 244, 184, 0.04)");
  grad.addColorStop(0.25, `rgba(255, 236, 156, ${0.38 * pulse})`);
  grad.addColorStop(0.74, `rgba(224, 137, 74, ${0.84 * pulse})`);
  grad.addColorStop(1, "rgba(224, 137, 74, 0.05)");
  ctx.save();
  ctx.strokeStyle = grad;
  ctx.lineWidth = active.outcome === "miss" ? 4 : 6;
  ctx.lineCap = "round";
  ctx.shadowColor = active.outcome === "miss"
    ? "rgba(255, 94, 94, 0.72)"
    : "rgba(255, 218, 122, 0.82)";
  ctx.shadowBlur = 18;
  ctx.beginPath();
  ctx.moveTo(frame.cx, frame.cy);
  ctx.lineTo(target.x, target.y);
  ctx.stroke();

  ctx.shadowBlur = 8;
  ctx.fillStyle = "#fff4b8";
  ctx.beginPath();
  ctx.arc(frame.cx, frame.cy, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(255, 244, 184, 0.28)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(frame.cx, frame.cy, 20 + 5 * pulse, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();

  drawGrabGauge(ctx, active, target, frame);
}

function drawSkyCluster(ctx, frame, cluster, state, worldRotation, time) {
  const sky = state.sky;
  const active = sky.activeRoll && sky.activeRoll.constellation === cluster.name
    ? sky.activeRoll
    : null;
  const screenBase = clusterScreenPosition(frame, cluster, worldRotation);
  const revealed = cluster.revealSeq == null || sky.chapterIdx >= cluster.revealSeq;
  const focusDim = sky.activeRoll && !active ? 0.42 : 1;
  const revealAlpha = revealed ? 1 : 0.18;
  const activeScale = active ? 1.62 : 1;
  const screen = { ...screenBase, size: screenBase.size * activeScale };
  const alpha = revealAlpha * focusDim;

  if (sky.prefs.art) drawClusterArt(ctx, cluster, screen, active ? 0.82 : 0.46 * alpha);
  if (sky.prefs.wireframes) {
    ctx.save();
    ctx.globalAlpha = alpha;
    drawWireframeCluster(ctx, cluster, screen, sky.chapterIdx, active);
    ctx.restore();
  }
  if (active) drawActiveJumpStars(ctx, cluster, screen, active, sky.chapterIdx);
  if (sky.prefs.labels && (revealed || active)) {
    drawSkyLabel(ctx, cluster, screen, active ? 1 : 0.78 * alpha, !!active);
  }
}

function drawSkyScene(state, time) {
  const sky = state.sky;
  if (!sky) return;
  resizeSkyCanvas(state);
  const ctx = sky.ctx;
  const dpr = sky.dpr || Math.min(2, window.devicePixelRatio || 1);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const frame = skyFrame(sky.canvas);
  const reducedMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const chapterTurn = Math.max(0, sky.chapterIdx) * 0.0075;
  const slowTurn = sky.prefs.rotate && !reducedMotion ? time * 0.000035 : 0;
  const worldRotation = slowTurn + chapterTurn;

  ctx.clearRect(0, 0, frame.w, frame.h);
  drawSkyBackground(ctx, frame, sky, time, worldRotation);

  const active = sky.activeRoll;
  let target = null;
  if (active) {
    target = skyTargetPoint(state, frame, active, worldRotation);
    drawBeam(ctx, active, target, frame, time);
  }

  const clusters = sky.model.clusters;
  for (const cluster of clusters) {
    if (active && cluster.name === active.constellation) continue;
    drawSkyCluster(ctx, frame, cluster, state, worldRotation, time);
  }
  if (active) {
    const activeCluster = clusters.find(c => c.name === active.constellation);
    if (activeCluster) drawSkyCluster(ctx, frame, activeCluster, state, worldRotation, time);
  }
}

function updateSkyHud(state) {
  const sky = state.sky;
  if (!sky) return;
  const chapter = sky.chapter;
  const active = sky.activeRoll;
  const kicker = $("sky-hud-kicker");
  const title = $("sky-hud-title");
  const meta = $("sky-hud-meta");
  const focus = $("sky-focus-readout");
  const grab = $("sky-grab-readout");
  if (!kicker || !title || !meta || !focus || !grab) return;

  if (active) {
    const success = active.cost != null && active.cost <= active.available;
    const surplus = active.cost == null ? null : active.available - active.cost;
    kicker.textContent = `Roll ${active.roll.roll_number ?? "?"} - ${active.outcome.toUpperCase()}`;
    title.textContent = active.perkName;
    meta.textContent = [
      active.constellation,
      active.jump,
      active.cost == null ? null : `${active.cost} CP mote`,
      `${active.available} CP available`,
    ].filter(Boolean).join(" / ");
    focus.textContent = `${active.constellation}${active.jump ? ` / ${active.jump}` : ""}`;
    if (active.cost == null) {
      grab.textContent = `${active.available} CP available; unresolved mote cost`;
    } else if (success) {
      grab.textContent = surplus > 0
        ? `${active.available} CP grab covers ${active.cost} CP; ${surplus} CP stays banked`
        : `${active.available} CP grab exactly covers ${active.cost} CP`;
    } else {
      grab.textContent = `${active.available} CP grab is short by ${Math.abs(surplus)} CP`;
    }
    return;
  }

  kicker.textContent = chapter ? `Chapter ${chapter.chapter_num}` : "Sky lead-in";
  title.textContent = chapter
    ? chapter.full_title.replace(/^\d+(\.\d+)?\s*/, "")
    : "The Forge sky is waiting at the story edge.";
  meta.textContent = chapter
    ? `${chapter.cumulative_perks_through_chapter} perks revealed through this point`
    : "Move into the story to reveal constellation detail.";
  focus.textContent = chapter ? "No active roll; full sky survey" : "Toolkits overhead";
  grab.textContent = "No roll at this chapter position";
}

function updateSkyState(state) {
  const sky = state.sky;
  if (!sky) return;
  const chapter = chapterAtWord(state.model, state.currentWord);
  sky.chapter = chapter;
  sky.chapterIdx = chapter ? state.model.idxOf.get(chapter.chapter_num) : -1;
  sky.activeRoll = findActiveSkyRoll(state, chapter);
  updateSkyHud(state);
}

function initSkyView(state, wireframes, rollResolutions) {
  const canvas = $("sky-canvas");
  if (!canvas || !wireframes) return;
  const sky = {
    canvas,
    ctx: canvas.getContext("2d"),
    dpr: Math.min(2, window.devicePixelRatio || 1),
    prefs: readSkyPrefs(),
    model: buildSkyModel(wireframes),
    resolutions: buildRollResolutionMaps(rollResolutions),
    dust: makeSkyDust(820),
    chapter: null,
    chapterIdx: -1,
    activeRoll: null,
  };
  state.sky = sky;
  attachSkyControls(state);
  if (window.ResizeObserver) {
    sky.resizeObserver = new ResizeObserver(() => resizeSkyCanvas(state));
    sky.resizeObserver.observe($("sky-canvas-wrap"));
  } else {
    window.addEventListener("resize", () => resizeSkyCanvas(state));
  }
  resizeSkyCanvas(state);
  updateSkyState(state);

  function tick(time) {
    drawSkyScene(state, time);
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ---------- tooltip on roll dots -----------------------------------------

function attachRollTooltip() {
  const tip = $("roll-tooltip");
  const track = $("track-rolls");
  const stack = $("track-stack");
  const coarsePointerQuery = window.matchMedia
    ? window.matchMedia("(pointer: coarse)")
    : null;
  let pinnedDot = null;
  let pinnedTap = null;
  let lastDotPointer = null;
  let pendingDotGesture = null;
  let handledDotPointerGesture = null;

  function placeTooltip(e) {
    const pad = 10;
    const tipRect = tip.getBoundingClientRect();
    let x = e.clientX + 12;
    let y = e.clientY + 12;
    if (x + tipRect.width + pad > window.innerWidth) x = e.clientX - tipRect.width - 12;
    if (y + tipRect.height + pad > window.innerHeight) y = e.clientY - tipRect.height - 12;
    x = Math.max(pad, Math.min(x, window.innerWidth - tipRect.width - pad));
    y = Math.max(pad, Math.min(y, window.innerHeight - tipRect.height - pad));
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }
  function show(dot, e) {
    clear(tip);
    const r = dot._roll;
    const c = dot._chapter;
    const outcomeText = r.outcome === "hit" ? "hit" :
                        r.outcome === "miss" ? "miss" : "unknown";
    const titleText = rollPrincipalName(r) || outcomeText.toUpperCase();
    tip.appendChild(el("div", { class: "tip-title" }, titleText));

    function row(label, value) {
      tip.appendChild(el("div", { class: "tip-row" },
        el("span", { class: "tip-label" }, label),
        " ", value));
    }
    row("chapter", `ch ${c.chapter_num} — ${c.full_title}`);
    row("outcome", outcomeText);
    if (r.constellation) row("constellation", r.constellation);
    const totalCost = rollTotalCost(r);
    if (totalCost) row("cost", `${totalCost} CP`);
    if (r.purchased_perk_jump) row("jump", r.purchased_perk_jump);
    row("evidence", r.evidence_kind);

    const paidPerks = paidRollPerks(r);
    if (paidPerks.length > 1) {
      const block = el("div", { class: "tip-perks" },
        el("span", { class: "tip-label" }, "paid bundle"));
      for (const p of paidPerks) {
        const span = el("span", { class: "perk" });
        span.appendChild(document.createTextNode(`• ${p.name}`));
        if (p.cost != null) {
          span.appendChild(el("span", { style: { color: "var(--gray-3)" } },
            ` (${p.cost} CP)`));
        }
        block.appendChild(span);
      }
      tip.appendChild(block);
    }

    if (r.free_perks && r.free_perks.length > 0) {
      const block = el("div", { class: "tip-perks" },
        el("span", { class: "tip-label" }, "free siblings"));
      for (const f of r.free_perks) {
        const span = el("span", { class: "perk" });
        span.appendChild(document.createTextNode(`• ${f.name} `));
        span.appendChild(el("span", { style: { color: "var(--gray-3)" } },
          `(${f.jump})`));
        block.appendChild(span);
      }
      tip.appendChild(block);
    }
    if (c.post_url) {
      tip.appendChild(el("div", { class: "tip-link" },
        c.post_url.split("#")[1] || "view on SV"));
    }

    tip.hidden = false;
    placeTooltip(e);
  }
  function setPinnedDot(dot) {
    if (pinnedDot && pinnedDot !== dot) pinnedDot.classList.remove("is-pinned");
    if (!dot) {
      for (const marked of track.querySelectorAll(".roll-dot.is-pinned")) {
        marked.classList.remove("is-pinned");
      }
    }
    pinnedDot = dot;
    if (pinnedDot) pinnedDot.classList.add("is-pinned");
  }
  function currentPinnedDot() {
    return pinnedDot || track.querySelector(".roll-dot.is-pinned");
  }
  function hide() {
    tip.hidden = true;
    pinnedTap = null;
    setPinnedDot(null);
  }
  function hideHover() {
    if (!currentPinnedDot()) tip.hidden = true;
  }
  function openDot(dot) {
    const url = dot._chapter.post_url;
    if (url) window.open(url, "_blank", "noopener");
  }
  function isTouchLikePointer(e) {
    return e && (e.pointerType === "touch" || e.pointerType === "pen");
  }
  function shouldUsePinnedTap(e) {
    return (coarsePointerQuery && coarsePointerQuery.matches) || isTouchLikePointer(e);
  }
  function pointNearDot(dot, e) {
    if (!dot || !e) return false;
    const pad = 14;
    const rect = dot.getBoundingClientRect();
    return e.clientX >= rect.left - pad &&
      e.clientX <= rect.right + pad &&
      e.clientY >= rect.top - pad &&
      e.clientY <= rect.bottom + pad;
  }
  function pointNearPinnedTap(e) {
    if (!pinnedTap || !e) return false;
    return Math.hypot(e.clientX - pinnedTap.x, e.clientY - pinnedTap.y) <= 24;
  }
  function pinnedTapTarget(dot, e) {
    const pinned = currentPinnedDot() || (pinnedTap && pinnedTap.dot);
    if (!pinned) return null;
    if (pinned === dot) return pinned;
    if (shouldUsePinnedTap(e) && pointNearPinnedTap(e)) return pinnedTap.dot;
    if (shouldUsePinnedTap(e) && pointNearDot(pinned, e)) return pinned;
    return null;
  }
  function pinDot(dot, e) {
    setPinnedDot(dot);
    pinnedTap = { dot, x: e.clientX, y: e.clientY };
    show(dot, e);
  }
  function markHandledDotGesture(dot) {
    const handled = { dot };
    handledDotPointerGesture = handled;
    window.setTimeout(() => {
      if (handledDotPointerGesture === handled) handledDotPointerGesture = null;
    }, 800);
  }
  function handledPointerClick(dot, e) {
    if (!handledDotPointerGesture) return false;
    return handledDotPointerGesture.dot === dot ||
      pointNearDot(handledDotPointerGesture.dot, e);
  }
  function shouldPinDot(e, dot) {
    if (coarsePointerQuery && coarsePointerQuery.matches) return true;
    return !!lastDotPointer &&
      lastDotPointer.dot === dot &&
      lastDotPointer.touchLike &&
      performance.now() - lastDotPointer.at < 1200;
  }

  track.addEventListener("mousemove", e => {
    if (pinnedDot) return;
    const dot = e.target.closest(".roll-dot");
    if (!dot) return hideHover();
    show(dot, e);
  });
  track.addEventListener("mouseleave", hideHover);
  stack.addEventListener("pointerdown", e => {
    const dot = e.target instanceof Element ? e.target.closest(".roll-dot") : null;
    const pinnedTarget = pinnedTapTarget(dot, e);
    const gestureDot = pinnedTarget || dot;
    if (dot) {
      lastDotPointer = {
        dot,
        touchLike: isTouchLikePointer(e),
        at: performance.now(),
      };
    }
    if (!gestureDot || !shouldUsePinnedTap(e)) return;
    pendingDotGesture = {
      pointerId: e.pointerId,
      dot: gestureDot,
      openTarget: pinnedTarget,
      startX: e.clientX,
      startY: e.clientY,
      moved: false,
    };
    e.preventDefault();
    e.stopImmediatePropagation();
  });
  document.addEventListener("pointermove", e => {
    if (!pendingDotGesture || pendingDotGesture.pointerId !== e.pointerId) return;
    if (Math.hypot(e.clientX - pendingDotGesture.startX,
                   e.clientY - pendingDotGesture.startY) > 10) {
      pendingDotGesture.moved = true;
    }
  });
  document.addEventListener("pointerup", e => {
    if (!pendingDotGesture || pendingDotGesture.pointerId !== e.pointerId) return;
    const gesture = pendingDotGesture;
    pendingDotGesture = null;
    if (gesture.moved) return;
    if (gesture.openTarget) openDot(gesture.openTarget);
    else pinDot(gesture.dot, e);
    markHandledDotGesture(gesture.dot);
    e.preventDefault();
    e.stopPropagation();
  });
  document.addEventListener("pointercancel", e => {
    if (pendingDotGesture && pendingDotGesture.pointerId === e.pointerId) {
      pendingDotGesture = null;
    }
  });
  track.addEventListener("click", e => {
    const dot = e.target.closest(".roll-dot");
    if (!dot) return;
    const pinnedTarget = pinnedTapTarget(dot, e);
    if (handledPointerClick(dot, e)) {
      handledDotPointerGesture = null;
      e.preventDefault();
      return;
    }
    if (shouldPinDot(e, dot)) {
      e.preventDefault();
      if (pinnedTarget) {
        openDot(pinnedTarget);
        return;
      }
      pinDot(dot, e);
      return;
    }
    openDot(dot);
  });
  document.addEventListener("click", e => {
    if (!pinnedDot) return;
    if (e.target.closest(".roll-dot, #roll-tooltip")) return;
    hide();
  });
}

// ---------- scrubber interaction -----------------------------------------

function attachScrubber(state) {
  const track = $("track-stack");
  const container = $("scrubber-container");
  const hit = $("scrubber-hitarea");
  const playhead = $("scrubber-playhead");

  container.addEventListener("scroll", () => {
    const now = performance.now();
    if (state.scrollFollow.ignoreProgrammaticScroll) return;
    state.scrollFollow.catchupStartedAt = 0;
    if (state.playing) state.scrollFollow.holdUntil = now + MANUAL_SCROLL_HOLD_MS;
    else state.scrollFollow.pausedManualLock = true;
  });

  function wordFromClientX(x) {
    const rect = track.getBoundingClientRect();
    const rel = (x - rect.left) / rect.width;
    return -PRE_ROLL_WORDS + rel * (PRE_ROLL_WORDS + state.model.totalWords);
  }

  let dragging = false;
  let activePointerId = null;
  let capturedPointerId = null;
  let activeTouchId = null;
  let pendingChapTap = null;

  function pointerClientX(e) {
    if (e.touches && e.touches.length) return e.touches[0].clientX;
    if (e.changedTouches && e.changedTouches.length) return e.changedTouches[0].clientX;
    return e.clientX;
  }
  function blockedScrubTarget(target) {
    return target instanceof Element && target.closest(".roll-dot, .shadow-bar");
  }
  function inScrubHitArea(clientX, clientY) {
    const rect = hit.getBoundingClientRect();
    return clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom;
  }
  function chapTickFromTarget(target) {
    return target instanceof Element ? target.closest(".chap-tick") : null;
  }
  function noteTapStart(target, clientX, clientY) {
    const tick = chapTickFromTarget(target);
    pendingChapTap = tick
      ? { tick, x: clientX, y: clientY, moved: false }
      : null;
  }
  function noteTapMove(clientX, clientY) {
    if (!pendingChapTap || pendingChapTap.moved) return;
    if (Math.hypot(clientX - pendingChapTap.x, clientY - pendingChapTap.y) > 6) {
      pendingChapTap.moved = true;
    }
  }
  function commitChapTap() {
    const tap = pendingChapTap;
    pendingChapTap = null;
    if (!tap || tap.moved) return;
    selectChapter(state, tap.tick.dataset.chapterNum);
    state.scrollFollow.pausedManualLock = false;
    setWord(state, tap.tick._wordPos);
    renderSelectedChapter(state);
  }
  function beginScrub(clientX) {
    state.scrollFollow.pausedManualLock = false;
    dragging = true;
    document.body.style.userSelect = "none";
    setWord(state, wordFromClientX(clientX));
  }
  function updateScrub(clientX, clientY) {
    if (!dragging) return;
    setWord(state, wordFromClientX(clientX));
    if (clientY != null) noteTapMove(clientX, clientY);
  }
  function releasePointerCapture() {
    if (capturedPointerId == null) return;
    if (track.releasePointerCapture) {
      try {
        if (!track.hasPointerCapture || track.hasPointerCapture(capturedPointerId)) {
          track.releasePointerCapture(capturedPointerId);
        }
      } catch (_) {
        // Pointer capture can already be gone after a browser-level cancel.
      }
    }
    capturedPointerId = null;
  }
  function finishScrub(e) {
    if (e && e.pointerId != null && activePointerId !== e.pointerId) return;
    commitChapTap();
    releasePointerCapture();
    dragging = false;
    activePointerId = null;
    activeTouchId = null;
    document.body.style.userSelect = "";
  }
  function touchById(touches, id) {
    for (const touch of touches) {
      if (touch.identifier === id) return touch;
    }
    return null;
  }

  if (window.PointerEvent) {
    track.addEventListener("pointerdown", e => {
      if (activePointerId != null || e.isPrimary === false) return;
      if ((e.pointerType === "mouse" || e.pointerType === "pen") && e.button !== 0) return;
      if (blockedScrubTarget(e.target)) return;
      if (!inScrubHitArea(e.clientX, e.clientY)) return;
      activePointerId = e.pointerId;
      noteTapStart(e.target, e.clientX, e.clientY);
      if (track.setPointerCapture) {
        try {
          track.setPointerCapture(e.pointerId);
          capturedPointerId = e.pointerId;
        } catch (_) {
          capturedPointerId = null;
        }
      }
      beginScrub(e.clientX);
      e.preventDefault();
    });
    document.addEventListener("pointermove", e => {
      if (!dragging || activePointerId !== e.pointerId) return;
      updateScrub(e.clientX, e.clientY);
      if (e.cancelable) e.preventDefault();
    });
    document.addEventListener("pointerup", finishScrub);
    document.addEventListener("pointercancel", finishScrub);
  } else {
    track.addEventListener("mousedown", e => {
      if (e.button !== 0 || blockedScrubTarget(e.target)) return;
      if (!inScrubHitArea(e.clientX, e.clientY)) return;
      noteTapStart(e.target, e.clientX, e.clientY);
      beginScrub(e.clientX);
      e.preventDefault();
    });
    track.addEventListener("touchstart", e => {
      if (dragging || e.touches.length !== 1 || e.changedTouches.length !== 1) return;
      if (blockedScrubTarget(e.target)) return;
      const touch = e.changedTouches[0];
      if (!inScrubHitArea(touch.clientX, touch.clientY)) return;
      activeTouchId = touch.identifier;
      noteTapStart(e.target, touch.clientX, touch.clientY);
      beginScrub(touch.clientX);
      if (e.cancelable) e.preventDefault();
    }, { passive: false });
    document.addEventListener("mousemove", e => {
      if (!dragging) return;
      updateScrub(pointerClientX(e), e.clientY);
      e.preventDefault();
    });
    document.addEventListener("mouseup", finishScrub);
    document.addEventListener("touchmove", e => {
      if (!dragging || activeTouchId == null) return;
      const touch = touchById(e.touches, activeTouchId);
      if (!touch) return;
      updateScrub(touch.clientX, touch.clientY);
      e.preventDefault();
    }, { passive: false });
    const finishTouch = e => {
      if (activeTouchId == null || !touchById(e.changedTouches, activeTouchId)) return;
      finishScrub(e);
    };
    document.addEventListener("touchend", finishTouch);
    document.addEventListener("touchcancel", finishTouch);
  }

  window.addEventListener("blur", () => {
    if (dragging) finishScrub();
  });

  playhead.addEventListener("keydown", e => {
    let delta = 0;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -2_000;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = 2_000;
    else if (e.key === "PageDown") delta = -50_000;
    else if (e.key === "PageUp") delta = 50_000;
    else if (e.key === "Home") { setWord(state, -PRE_ROLL_WORDS); e.preventDefault(); return; }
    else if (e.key === "End") { setWord(state, state.model.totalWords); e.preventDefault(); return; }
    else return;
    e.preventDefault();
    state.scrollFollow.pausedManualLock = false;
    setWord(state, state.currentWord + delta);
  });
}

function attachChapterSelection(state) {
  const track = $("track-chapters");
  const close = $("chapter-detail-close");
  if (close) {
    close.addEventListener("click", () => clearSelectedChapter(state));
  }
  track.addEventListener("click", e => {
    const tick = e.target.closest(".chap-tick");
    if (!tick) return;
    selectChapter(state, tick.dataset.chapterNum);
    state.scrollFollow.pausedManualLock = false;
    setWord(state, tick._wordPos);
    renderSelectedChapter(state);
    e.stopPropagation();
  });
}

function attachZoomControls(state) {
  const zoomInput = $("timeline-zoom");
  const zoomOut = $("zoom-out");
  const zoomIn = $("zoom-in");
  const zoomFit = $("zoom-fit");

  zoomInput.addEventListener("input", () => {
    state.zoom = clampZoom(parseFloat(zoomInput.value));
    applyTimelineZoom(state, { center: true });
  });
  zoomOut.addEventListener("click", () => {
    state.zoom = clampZoom(state.zoom - ZOOM_STEP);
    applyTimelineZoom(state, { center: true });
  });
  zoomIn.addEventListener("click", () => {
    state.zoom = clampZoom(state.zoom + ZOOM_STEP);
    applyTimelineZoom(state, { center: true });
  });
  zoomFit.addEventListener("click", () => {
    state.zoom = MIN_ZOOM;
    applyTimelineZoom(state, { center: true });
  });
  window.addEventListener("resize", () => applyTimelineZoom(state, { center: true }));
}

function setWord(state, w, options = {}) {
  const min = -PRE_ROLL_WORDS;
  const max = state.model.totalWords;
  if (w < min) w = min;
  if (w > max) w = max;
  state.currentWord = w;
  saveBookmark(w);
  renderState(state);
  updateScrollFollow(state, options);
}

// ---------- playback -----------------------------------------------------

function attachPlaybackControls(state) {
  const btn = $("play-pause");
  const sel = $("playback-speed");
  const reset = $("reset-bookmark");

  const validSpeeds = new Set([1, 2, 5, 10, 25, 50, 100]);
  const saved = parseFloat(localStorage.getItem(LS_SPEED));
  sel.value = String(validSpeeds.has(saved) ? saved : DEFAULT_SPEED);

  let timer = null;
  const playing = () => timer !== null;
  const setPlaying = (v) => {
    state.playing = v;
    if (v && !playing()) {
      if (state.currentWord >= state.model.totalWords) {
        state.scrollFollow.pausedManualLock = false;
        state.scrollFollow.holdUntil = 0;
        state.scrollFollow.catchupStartedAt = 0;
        setWord(state, -PRE_ROLL_WORDS, { force: true });
      }
      state.scrollFollow.holdUntil = 0;
      state.scrollFollow.catchupStartedAt = 0;
      const speed = parseFloat(sel.value);
      const advance = speed * 1000 * (TICK_INTERVAL_MS / 1000);
      timer = setInterval(() => {
        const next = state.currentWord + advance;
        if (next >= state.model.totalWords) {
          setWord(state, state.model.totalWords);
          setPlaying(false);
          return;
        }
        setWord(state, next);
      }, TICK_INTERVAL_MS);
      btn.classList.add("playing");
      btn.textContent = "❚❚";
      btn.setAttribute("aria-label", "Pause");
    } else if (!v && playing()) {
      clearInterval(timer);
      timer = null;
      btn.classList.remove("playing");
      btn.textContent = "▶";
      btn.setAttribute("aria-label", "Play");
    }
    renderState(state);
  };

  btn.addEventListener("click", () => setPlaying(!playing()));
  sel.addEventListener("change", () => {
    saveSpeed(parseFloat(sel.value));
    if (playing()) { setPlaying(false); setPlaying(true); }
  });
  reset.addEventListener("click", () => {
    clearBookmark();
    state.scrollFollow.pausedManualLock = false;
    setWord(state, -PRE_ROLL_WORDS);
  });
}

// ---------- parked prototypes --------------------------------------------

function skyPrototypeEnabled() {
  const params = new URLSearchParams(window.location.search);
  return params.get("sky") === "1" || window.location.hash === "#sky-prototype";
}

// ---------- localStorage -------------------------------------------------

function loadStorage() {
  try {
    if (localStorage.getItem(LS_VERSION) !== STORAGE_VERSION) {
      localStorage.removeItem(LS_BOOKMARK);
      localStorage.removeItem(LS_SPEED);
      localStorage.removeItem(LS_ZOOM);
      localStorage.setItem(LS_VERSION, STORAGE_VERSION);
    }
    return {
      word: parseFloat(localStorage.getItem(LS_BOOKMARK)),
      speed: parseFloat(localStorage.getItem(LS_SPEED)) || DEFAULT_SPEED,
      zoom: normalizeStoredZoom(parseFloat(localStorage.getItem(LS_ZOOM))),
    };
  } catch {
    return { word: NaN, speed: DEFAULT_SPEED, zoom: DEFAULT_ZOOM };
  }
}
function saveBookmark(w) { try { localStorage.setItem(LS_BOOKMARK, String(Math.round(w))); } catch {} }
function saveSpeed(s) { try { localStorage.setItem(LS_SPEED, String(s)); } catch {} }
function saveZoom(z) { try { localStorage.setItem(LS_ZOOM, String(clampZoom(z))); } catch {} }
function clearBookmark() { try { localStorage.removeItem(LS_BOOKMARK); } catch {} }

// ---------- theme ----------------------------------------------------------

const THEME_PREFS = ["auto", "light", "dark"];
const THEME_LABELS = {
  auto: "Theme: follow system (click for light)",
  light: "Theme: light (click for dark)",
  dark: "Theme: dark (click to follow system)",
};

function readThemePref() {
  try {
    const v = localStorage.getItem(LS_THEME);
    if (THEME_PREFS.includes(v)) return v;
  } catch {}
  return "auto";
}

function applyTheme(pref) {
  if (pref === "light" || pref === "dark") {
    document.documentElement.setAttribute("data-theme", pref);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

function attachThemeToggle() {
  const btn = $("theme-toggle");
  if (!btn) return;

  let pref = readThemePref();
  applyTheme(pref);

  function reflect() {
    btn.setAttribute("data-theme-pref", pref);
    btn.setAttribute("aria-label", THEME_LABELS[pref]);
    btn.title = THEME_LABELS[pref];
  }
  reflect();

  btn.addEventListener("click", () => {
    const next = THEME_PREFS[(THEME_PREFS.indexOf(pref) + 1) % THEME_PREFS.length];
    pref = next;
    applyTheme(pref);
    reflect();
    try {
      if (pref === "auto") localStorage.removeItem(LS_THEME);
      else localStorage.setItem(LS_THEME, pref);
    } catch {}
  });
}

// ---------- bootstrap ----------------------------------------------------

(async () => {
  try {
    const skyEnabled = skyPrototypeEnabled();
    const packageIndex = await loadPackageIndex();
    const packageSelection = selectedPackageBase(packageIndex);
    const dataPackage = await loadDataPackage(packageSelection.base);
    const [facts, wireframes, rollResolutions] = await Promise.all([
      loadContractJSON(dataPackage, "chapter_facts"),
      skyEnabled ? loadContractJSON(dataPackage, "constellation_wireframes", { optional: true }) : Promise.resolve(null),
      skyEnabled ? loadContractJSON(dataPackage, "roll_resolutions", { optional: true }) : Promise.resolve(null),
    ]);
    const model = buildCoordinateModel(facts);
    const cumIdx = buildCumulativeIndex(facts);
    const stored = loadStorage();
    const state = {
      facts, model, cumIdx,
      currentWord: Number.isFinite(stored.word) ? stored.word : -PRE_ROLL_WORDS,
      zoom: stored.zoom,
      selectedChapterNum: null,
      playing: false,
      scrollFollow: {
        pausedManualLock: false,
        holdUntil: 0,
        catchupStartedAt: 0,
        ignoreProgrammaticScroll: false,
      },
    };
    attachThemeToggle();
    const skySection = $("sky-section");
    if (skySection) skySection.hidden = !skyEnabled || !wireframes;
    renderTracks(model, facts);
    applyTimelineZoom(state, { center: true });
    if (skyEnabled && wireframes) initSkyView(state, wireframes, rollResolutions);
    attachDataPackageSelector(
      packageIndex,
      packageSelection.packageId || dataPackage.manifest.package_id,
      dataPackage.manifest,
    );
    attachRollTooltip();
    attachScrubber(state);
    attachChapterSelection(state);
    attachZoomControls(state);
    attachPlaybackControls(state);
    renderState(state);
    updateScrollFollow(state, { force: true });
  } catch (err) {
    console.error(err);
    const errBox = el("div",
      { style: { maxWidth: "600px", margin: "60px auto", padding: "24px",
                 fontFamily: "sans-serif", color: "#b00" } },
      el("h1", null, "Failed to load data"),
      el("p", null, err.message),
      el("p", null, "Make sure you're serving from the repo root over HTTP "
        + "(e.g. python3 -m http.server) so data/derived/data_package.json "
        + "and chapter_facts.json are reachable."));
    clear(document.body);
    document.body.appendChild(errBox);
  }
})();

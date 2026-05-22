import {
  dataVersionOptionLabel,
  validateDataDocument,
  validateDataPackageManifest,
} from "./data-contract.js";
import {
  beamOpacity,
  beamReach,
  buildClusterAnchors,
  buildRollLogRows,
  buildConstellationKnowledgeIndex,
  buildSkyCarouselLayout,
  clusterLocalToWorld,
  constellationOutlineVisibleForRoll,
  easeInOutCubic,
  fieldLogModel,
  focalClusterOpacity,
  focalScaleFactor,
  focalWorldFromScene,
  focusAnimDurationFor,
  focusCameraViewRect,
  focusScene,
  haloAuraProgress,
  HALO_BINARY_OFFSET,
  HUES,
  JUMP_RADIUS_WORLD,
  motionBlurStdDeviation,
  multiGrabFlashOpacity,
  multiGrabMergeProgress,
  nonFocalClusterOpacity,
  nonFocalInteriorOpacity,
  onRollPlaybackState,
  paidRollPerks,
  perkDisplayLabel,
  phase,
  rollTotalCost,
  ROLL_FIRING_WINDOW_WORDS,
  silhouetteOpacity,
  splitProgress,
  spotlightProgress,
  starWorldFromScene,
  vertexPinOpacity,
  WORLD_STAGE_HEIGHT,
  WORLD_STAGE_WIDTH,
  lerp,
} from "./viz-model.js";

const DATA_BASE = "../data/derived";
const PACKAGES_INDEX_URL = "../data/packages.json";
const DATA_PACKAGE_PARAM = "dataPackage";
const DATA_VERSION = "phase9-info-link";

const LS_BOOKMARK = "bcf:bookmark:word_position";
const LS_SPEED = "bcf:playback:speed:v2";
const LS_ZOOM = "bcf:timeline:zoom";
const LS_MODE = "bcf:mode";
const LS_ON_ROLL_BEHAVIOR = "bcf:on-roll-behavior";
const LS_ROLL_LOCATION = "bcf:roll-location";
const LS_FIELD_LOG_HIDDEN = "bcf:field-log:hidden";
const LS_PORTRAIT_DISMISSED = "bcf:portrait-dismissed";
const LS_STORAGE_VERSION = "bcf:preview-port-storage-version";
const STORAGE_VERSION = "2";
const DEFAULT_WORD_POS = 450_000;
const DEFAULT_SPEED = 5_000;
const DEFAULT_ZOOM = 2.75;
const DEFAULT_ON_ROLL_BEHAVIOR = "cinematic";
const ON_ROLL_BEHAVIORS = ["cinematic", "pause", "quick"];
const ROLL_LOCATIONS = ["predicted", "curated"];
const DEFAULT_ROLL_LOCATION = "predicted";

const STORY_LINKS = [
  { label: "SV", href: "https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks" },
  { label: "FF", href: "https://www.fanfiction.net/s/13574944/1/Brockton-s-Celestial-Forge" },
  { label: "AO3", href: "https://archiveofourown.org/works/23949661/navigate" },
];
const STORY_TITLE_HREF = STORY_LINKS[0].href;
const PROJECT_REPO = "https://github.com/deinspanjer/bcf-visualization";
const BASE_PX_PER_KWORD = 8.4;

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
  onRollBehavior: readStoredChoice(LS_ON_ROLL_BEHAVIOR, ON_ROLL_BEHAVIORS, DEFAULT_ON_ROLL_BEHAVIOR),
  rollLocation: readStoredChoice(LS_ROLL_LOCATION, ROLL_LOCATIONS, DEFAULT_ROLL_LOCATION),
  fieldLogHidden: readStoredBoolean(LS_FIELD_LOG_HIDDEN, false),
  portraitDismissed: readStoredBoolean(LS_PORTRAIT_DISMISSED, false),
  rollFilter: "all",
  rollSort: "roll",
  raf: null,
  lastFrame: 0,
  // Cinematic roll-focus animation state (Phase 1). Captured when the
  // playthrough renderer first observes a roll inside the firing window;
  // cleared when the scrubber leaves that window. `currentFocusAnimT()`
  // reads this every render to drive the camera viewBox interpolation.
  focusAnim: null,
  focusAnimRaf: null,
};

// Reduced-motion preference is queried once at module load. Per the design
// README, if the user has prefers-reduced-motion: reduce, the focus animation
// resolves to its end state immediately (no camera pan, no transitions).
const PREFERS_REDUCED_MOTION = (typeof window !== "undefined"
  && typeof window.matchMedia === "function"
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

function currentFocusAnimT() {
  if (PREFERS_REDUCED_MOTION) return 1;
  const anim = app.focusAnim;
  if (!anim) return 1;
  const elapsed = performance.now() - anim.startMs;
  const raw = elapsed / Math.max(1, anim.durationMs);
  return raw < 0 ? 0 : raw > 1 ? 1 : raw;
}

function focusAnimTick() {
  app.focusAnimRaf = null;
  if (!app.focusAnim) return;
  const t = currentFocusAnimT();
  if (t >= 1) {
    // Hold the final frame. The user scrubbing away will clear focusAnim via
    // the per-render trigger logic; no need to keep RAF'ing.
    if (!app.playing) render();
    return;
  }
  // Avoid double-rendering while tickPlayback is already driving frames.
  if (!app.playing) render();
  app.focusAnimRaf = requestAnimationFrame(focusAnimTick);
}

// True while the cinematic camera is locking the scrubber in place. The lock
// runs from animation start through t >= 1 in `pause` mode (held until the
// user presses play) and through t < 1 in `cinematic` mode (auto-resumes
// when the camera move finishes).
function focusAnimIsLocking() {
  const anim = app.focusAnim;
  if (!anim) return false;
  if (anim.behavior === "pause") return true;
  return currentFocusAnimT() < 1;
}

function startFocusAnim(roll, behavior) {
  if (app.focusAnimRaf != null) {
    cancelAnimationFrame(app.focusAnimRaf);
    app.focusAnimRaf = null;
  }
  const lockedWordPos = Math.round(Number(roll.word_position) || 0);
  app.focusAnim = {
    rollUid: String(roll.uid),
    startMs: performance.now(),
    durationMs: focusAnimDurationFor(behavior),
    outcome: roll.outcome === "hit" ? "hit" : "miss",
    lockedWordPos,
    behavior,
  };
  // Snap the scrubber to the roll's word position so the visible cursor jumps
  // to the firing point — this is the "cut" that signals the cinematic has
  // begun. We write directly (not through setWordPos) to avoid the
  // scrub-cancel logic clearing the focusAnim we just created.
  if (app.data) {
    app.wordPos = lockedWordPos;
    store(LS_BOOKMARK, app.wordPos);
  }
  if (PREFERS_REDUCED_MOTION) return;
  app.focusAnimRaf = requestAnimationFrame(focusAnimTick);
}

function clearFocusAnim() {
  if (app.focusAnimRaf != null) {
    cancelAnimationFrame(app.focusAnimRaf);
    app.focusAnimRaf = null;
  }
  app.focusAnim = null;
}

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
    for (const key of [LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR, LS_ROLL_LOCATION, LS_FIELD_LOG_HIDDEN]) {
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
    clusterAnchors: buildClusterAnchors(bundle.constellation_wireframes),
    predictedRolls,
    predictedRollsMeta: bundle.predicted_rolls_meta,
  };
  app.wordPos = clamp(app.wordPos, 0, story.total_words);
  mountBackgroundStarfield();
}

function buildStory(chapterFacts) {
  // Each roll in chapter_facts already ships canonical EPUB positions
  // (`epub_word_offset_predicted` and `epub_word_offset_curated`) computed
  // by the bundler via the cp↔epub map. The UI just selects which field
  // drives `roll.word_position`; the mode toggle re-selects without
  // re-deriving.
  const chapters = [];
  const rolls = [];
  const sections = [];
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

    const rawRolls = ch.rolls || [];
    rawRolls.forEach((rawRoll, index) => {
      const fallbackWordPosition = resolveRollWordPosition(rawRoll, chapter, index, rawRolls.length);
      const wpPredicted = rawRoll.epub_word_offset_predicted ?? fallbackWordPosition;
      const wpCurated = rawRoll.epub_word_offset_curated ?? fallbackWordPosition ?? wpPredicted;
      const roll = {
        uid: `${ch.chapter_num}#${rawRoll.roll_sequence_in_chapter ?? index + 1}`,
        roll_number: rawRoll.roll_number ?? rawRoll.global_roll_number ?? `${ch.chapter_num}.${index + 1}`,
        chapter_num: ch.chapter_num,
        mechanical_chapter_num: rawRoll.mechanical_chapter_num,
        display_chapter_num: rawRoll.display_chapter_num,
        outcome: rawRoll.outcome || "unknown",
        source_kind: rawRoll.source_kind || null,
        constellation: rawRoll.constellation,
        jump: rawRoll.purchased_perk_jump || rawRoll.jump || rawRoll.free_perks?.[0]?.jump || null,
        word_position_predicted: wpPredicted,
        word_position_curated: wpCurated,
        word_position: app.rollLocation === "predicted" ? wpPredicted : wpCurated,
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

  rolls.sort((a, b) => (a.word_position ?? 0) - (b.word_position ?? 0));
  return {
    chapters,
    rolls,
    sections,
    total_words: chapters[chapters.length - 1]?.word_end || 0,
    shadow_periods: chapterFacts.shadow_periods || [],
  };
}

function normChapterTitle(fullTitle, chapterNum) {
  const prefix = `${chapterNum} `;
  return String(fullTitle).startsWith(prefix) ? String(fullTitle).slice(prefix.length) : String(fullTitle);
}

function finiteNumber(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function resolveRollWordPosition(rawRoll, chapter, index, totalRolls) {
  for (const key of [
    "display_word_position_epub",
    "cumulative_word_offset",
    "display_cumulative_word_offset",
    "source_cumulative_word_offset",
  ]) {
    const position = finiteNumber(rawRoll[key]);
    if (position != null) return Math.max(0, Math.round(position));
  }

  const chapterStart = finiteNumber(chapter.word_start) ?? 0;
  const chapterEnd = finiteNumber(chapter.word_end) ?? chapterStart;
  const chapterSpan = Math.max(0, chapterEnd - chapterStart);
  for (const key of [
    "display_word_position",
    "word_position",
    "source_word_position",
    "mechanical_word_position",
  ]) {
    const localPosition = finiteNumber(rawRoll[key]);
    if (localPosition == null) continue;
    return Math.round(chapterStart + clamp(localPosition, 0, chapterSpan));
  }

  if (rawRoll.source_kind === "trigger") return Math.round(chapterStart);
  const fraction = (index + 1) / ((totalRolls || 0) + 1);
  return Math.round(chapterStart + chapterSpan * fraction);
}

function buildConstellations(wireframes) {
  // Drives directly from the bundle's cluster_constellations (already in slot_position
  // order from the Phase 4 builder). Marker positions and silhouette polylines are
  // authored upstream — no heuristic shape table here.
  return (wireframes.cluster_constellations || []).map(cluster => ({
    name: cluster.name,
    slug: cluster.slug,
    hue: HUES[cluster.name] ?? 196,
    shape_concept: cluster.shape_concept,
    slot_position: cluster.slot_position,
    revealed_at_chapter: cluster.revealed_at_chapter,
    completed_at_chapter: cluster.completed_at_chapter,
    entered_pool_at_chapter: cluster.entered_pool_at_chapter,
    vertex_source: cluster.vertex_source,
    marker_positions: cluster.marker_positions || [],
    silhouette: cluster.silhouette || [],
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

function setWordPos(value) {
  if (!app.data) return;
  const next = Math.round(clamp(value, 0, app.data.story.total_words));
  // User-initiated scrubs cancel a running focus animation when they move
  // the playhead away from the locked position. tickPlayback drives wordPos
  // directly (not through setWordPos), so we never accidentally cancel from
  // auto-resume.
  if (app.focusAnim) {
    const drift = Math.abs(next - (app.focusAnim.lockedWordPos ?? next));
    if (drift > 5) clearFocusAnim();
  }
  app.wordPos = next;
  store(LS_BOOKMARK, app.wordPos);
  render();
}

function setMode(mode) {
  app.mode = mode;
  store(LS_MODE, mode);
  render();
}

function setRollLocation(value) {
  if (!ROLL_LOCATIONS.includes(value)) return;
  app.rollLocation = value;
  store(LS_ROLL_LOCATION, value);
  if (app.data) {
    const field = value === "predicted" ? "word_position_predicted" : "word_position_curated";
    for (const roll of app.data.story.rolls) {
      roll.word_position = roll[field] ?? roll.word_position_predicted;
    }
    app.data.story.rolls.sort(
      (a, b) => (a.word_position ?? 0) - (b.word_position ?? 0),
    );
  }
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
  // If the user hits play while a `pause`-mode cinematic is holding on its
  // final frame, clear that focusAnim so playback can resume past the roll.
  // Without this the lock would re-grab on the very next render. The roll's
  // firing window is still open, so we don't re-trigger the cinematic for
  // the same roll — see startFocusAnim trigger logic.
  if (app.focusAnim && app.onRollBehavior === "pause" && currentFocusAnimT() >= 1) {
    app.focusAnim = { ...app.focusAnim, behavior: "cinematic" };
  }
  app.playing = true;
  // While playing, tickPlayback drives render(). If a focus-anim RAF is in
  // flight from a prior paused state, cancel it now so we don't double-render
  // every frame for the rest of the animation.
  if (app.focusAnimRaf != null) {
    cancelAnimationFrame(app.focusAnimRaf);
    app.focusAnimRaf = null;
  }
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
  // Special case: user is in `pause` mode with a held cinematic (t >= 1, lock
  // still engaged). They're already `app.playing = true` — pressing space here
  // means "advance past this roll", not "pause playback". Reclassify the held
  // anim to `cinematic` so the next tickPlayback releases the lock and word
  // advance resumes from the locked position. Single keypress to escape.
  if (
    app.focusAnim
    && app.focusAnim.behavior === "pause"
    && currentFocusAnimT() >= 1
  ) {
    app.focusAnim = { ...app.focusAnim, behavior: "cinematic" };
    if (!app.playing) startPlayback();
    else render();  // keep playing; next tick sees the lock released
    return;
  }
  if (app.playing) stopPlayback();
  else startPlayback();
}

function tickPlayback(now) {
  if (!app.playing || !app.data) return;
  const dt = Math.max(0, (now - app.lastFrame) / 1000);
  app.lastFrame = now;
  // Cinematic + pause modes lock wordPos while the camera animation is
  // running. The lock window depends on behavior:
  //   - cinematic: lock while t < 1, then auto-resume word advance.
  //   - pause: lock for the full focusAnim lifetime (until the user scrubs
  //     out of the firing window or hits play again — but tickPlayback
  //     itself never resumes; the user pressing pause+play recomputes).
  // In both locked cases we still render() to keep the cinematic camera
  // advancing, but we skip the wordPos write so the scrubber stays parked.
  if (focusAnimIsLocking()) {
    render();
    app.raf = requestAnimationFrame(tickPlayback);
    return;
  }
  const next = app.wordPos + app.speed * dt;
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
      app.mode === "playthrough"
        ? [
            renderPlaythrough(),
            renderScrubber(false),
            renderScrubberControls(),
            renderStatStrip(),
          ]
        : [
            renderScrubber(true),
            renderScrubberControls(),
            renderStatStrip(),
            renderDetail(),
          ],
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
    el("p", { class: "info-explore" },
      "Browse every constellation and its perks at ",
      el("a", {
        href: "./constellations/index.html",
        target: "_blank",
        rel: "noopener noreferrer",
        text: "the constellation index",
      }),
      ".",
    ),
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
      // No onClick here — the play/pause button is the hottest control during
      // cinematic playback (60fps render rebuilds the DOM every frame, which
      // breaks the click-fires-on-same-node browser invariant for
      // mousedown/mouseup pairs). Click is delegated from document.body via
      // data-action, which works regardless of which generation of the
      // button received each half of the click. Native buttons still fire
      // click on Enter/Space, so keyboard activation continues to work.
      "data-action": "toggle-playback",
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
      ON_ROLL_BEHAVIORS.map(value => el("button", {
        class: app.onRollBehavior === value ? "is-active" : "",
        type: "button",
        "aria-pressed": app.onRollBehavior === value,
        // Delegated through data-action so a click landing during a
        // cinematic render (rebuilds at 60fps) still fires.
        "data-action": "set-on-roll-behavior",
        "data-on-roll-behavior": value,
        text: value,
      })),
    ),
    el("span", { class: "control-divider", "aria-hidden": "true" }),
    el("span", { class: "control-label", text: "roll location" }),
    el("div", { class: "app-mode-switch roll-mode-switch", role: "group", "aria-label": "Source of each roll's word position" },
      ROLL_LOCATIONS.map(value => el("button", {
        class: app.rollLocation === value ? "is-active" : "",
        type: "button",
        "aria-pressed": app.rollLocation === value,
        onClick: () => setRollLocation(value),
        text: value,
      })),
    ),
    el("button", {
      class: "btn ghost",
      id: "reset-bookmark",
      type: "button",
      // Delegated — reset is a frequent escape hatch during cinematic
      // playback, so it needs the same delegated-click reliability as
      // play/pause.
      "data-action": "reset-bookmark",
      text: "reset",
    }),
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
  const firing = lastRoll && Math.abs(app.wordPos - lastRoll.word_position) <= ROLL_FIRING_WINDOW_WORDS;

  // Cinematic trigger: capture / clear the roll-focus animation clock based
  // on whether the scrubber is inside the firing window. The clock is
  // decoupled from playback — wordPos locks to roll.word_position during the
  // animation (see tickPlayback's focusAnimIsLocking check) so the cinematic
  // plays at wall-clock pace regardless of base speed.
  //
  // Two cases skip the cinematic:
  //   1. `quick` mode — the user opted out; scrubber flies through.
  //   2. `source_kind === "trigger"` rolls — these are starting bonuses (the
  //      chapter-1 trigger event sits at word 0), not forge rolls. The
  //      firing flag itself remains true so the field log readout still
  //      shows the perk, but we don't run a cinematic for them.
  const cinematicEligible = app.onRollBehavior !== "quick"
    && lastRoll?.source_kind !== "trigger";
  if (firing && lastRoll && cinematicEligible) {
    const uid = String(lastRoll.uid);
    if (!app.focusAnim || app.focusAnim.rollUid !== uid) {
      startFocusAnim(lastRoll, app.onRollBehavior);
    }
  } else if (app.focusAnim) {
    clearFocusAnim();
  }

  // The sky camera only renders when we've actually started a focus
  // animation — trigger-event rolls and `quick` mode keep the carousel
  // visible without a cinematic handoff.
  const cinematicActive = !!app.focusAnim && firing && lastRoll;
  const scene = cinematicActive ? focusScene(lastRoll, app.data) : null;
  const focusT = currentFocusAnimT();

  return el("div", { class: `playthrough ${app.fieldLogHidden ? "field-log-hidden" : ""}` },
    el("div", { class: "viewport" },
      renderCarousel(scene ? focusT : null, firing && cinematicActive),
      renderViewportFrame(),
      scene ? renderSkyCamera(lastRoll, scene, focusT) : null,
    ),
    !app.fieldLogHidden ? renderNarrativeReadout(firing ? lastRoll : null, chapter) : null,
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

function renderCarousel(focusT = null, firingCinematic = false) {
  const rolls = app.data.story.rolls;
  const cardWidth = 348;
  const minCardSpacing = 440;
  const cardHalf = 160; // half of visual card width (320px), used to center the active card on the playhead
  // Phase 2 cross-fade: when a focus animation is active, the carousel fades
  // out 1 → 0 across the wide → reveal camera move (t = 0.10 → 0.45) so the
  // sky camera SVG can take over the focal area cleanly.
  const carouselOpacity = focusT == null ? 1 : Math.max(0, 1 - phase(focusT, 0.10, 0.45));
  const stripStyle = (transform) => carouselOpacity < 1
    ? { transform, opacity: String(carouselOpacity) }
    : { transform };
  if (!rolls.length) {
    return el("div", { class: "carousel-strip", style: stripStyle(`translateX(${-cardHalf}px)`) });
  }
  // Position cards in word-space, then enforce a visual floor so dense early
  // roll bursts do not collapse named constellations into one another.
  const totalWords = Math.max(1, app.data.story.total_words || rolls.at(-1).word_position);
  const layout = buildSkyCarouselLayout(rolls, {
    totalWords,
    wordPos: app.wordPos,
    averageCardWidth: cardWidth,
    minCardSpacing,
  });
  const playheadPx = layout.playheadPx;
  const renderRadiusPx = minCardSpacing * 6;
  const activeRadiusPx = cardWidth * 0.4;
  const flankRadiusPx = minCardSpacing * 1.15;
  const knowledgeIndex = buildConstellationKnowledgeIndex(rolls);

  // Pick a single "nearest" roll to mark active so overlapping cards in a
  // dense burst don't all flare at once.
  let nearestIndex = -1;
  let nearestDistPx = Infinity;
  for (let i = 0; i < rolls.length; i += 1) {
    const distPx = Math.abs(layout.positions[i] - playheadPx);
    if (distPx < nearestDistPx) {
      nearestDistPx = distPx;
      nearestIndex = i;
    }
  }

  const slots = [];
  for (let i = 0; i < rolls.length; i += 1) {
    const roll = rolls[i];
    const cardPx = layout.positions[i];
    const distPx = Math.abs(cardPx - playheadPx);
    if (distPx > renderRadiusPx) continue;
    const active = i === nearestIndex && distPx < activeRadiusPx;
    const flank = !active && distPx < flankRadiusPx;
    const con = roll.constellation ? app.data.conByName[roll.constellation] : null;
    const outlineVisible = constellationOutlineVisibleForRoll(roll, knowledgeIndex);
    // Active-card pop-out: when the cinematic is firing, the active
    // constellation card hides instantly so its outline doesn't double up
    // with the sky-camera SVG during the t = 0.10–0.45 cross-fade. The strip
    // opacity still smoothly fades the surrounding (non-active) cards.
    const slotStyle = { left: `${cardPx}px` };
    if (firingCinematic && active) slotStyle.opacity = "0";
    slots.push(el("div", { class: "carousel-slot", style: slotStyle },
      con ? renderConstellationCard(con, active, flank, outlineVisible) : renderUnresolvedCard(active, flank),
    ));
  }
  return el("div", { class: "carousel-strip", style: stripStyle(`translateX(${-(playheadPx + cardHalf)}px)`) }, slots);
}

function renderConstellationCard(con, active, flank, outlineVisible) {
  const size = 320;
  const color = `oklch(0.82 0.14 ${con.hue})`;

  const silhouetteStroke = active ? "1.1" : "0.9";
  const silhouetteOpacity = active ? "0.32" : "0.20";
  const polylines = outlineVisible
    ? (con.silhouette || []).map(polyline => svgEl("polyline", {
        points: polyline.map(point => `${(point[0] * size).toFixed(1)},${(point[1] * size).toFixed(1)}`).join(" "),
        fill: "none",
        stroke: color,
        "stroke-width": silhouetteStroke,
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
        opacity: silhouetteOpacity,
      }))
    : [];

  const markerOpacity = active ? 1 : 0.85;
  return el("div", { class: `const-card ${active ? "is-active" : ""} ${flank ? "is-flank" : ""}`, style: { "--hue": con.hue } },
    el("span", { class: "halo" }),
    svgEl("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, class: "outline", style: "position:absolute;inset:0" },
      ...polylines,
    ),
    (con.marker_positions || []).map((pos, index) => simpleStar({
      key: index,
      color,
      cost: 300,
      visualSize: 30,
      opacity: markerOpacity,
      left: pos[0],
      top: pos[1],
    })),
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

// Sky-camera renderer (Phases 1-3). Mounts inside `.viewport` and overlays
// the carousel/sky stage while the cinematic focus animation is running.
// Uses an SVG with a world-coord viewBox (1600×1000 stage) that interpolates
// between wide / reveal / hit keyframes per `focusCameraViewBox`.
//
// Phase 3 adds:
//   - Shared `<symbol>` diffraction-star defs (one per cost tier 100/200/
//     400/600/800). Stars instance via `<use>` — much cheaper than
//     rebuilding the ~12 ray <rect>s on every frame.
//   - Motion blur (feGaussianBlur, 0 → 8 → 0 across t=0.22-0.62) wrapped
//     around the silhouette + vertex pins + cluster markers ONLY, NOT the
//     interior perks (they need to render crisp as they emerge through the
//     smear).
//   - Focal-vertex split: the focal cluster-marker fades out (opacity
//     0.85 → 0, size 54 → 38) across t=0.40-0.58 while the focal jump's
//     interior perks fade in. Non-focal interior perks dim from 0.72 to
//     dimFloor (0.28 / 0.30 for miss) across t=0.66-0.90.
//   - Silhouette, vertex pins, and non-focal cluster markers fade 0.62/
//     0.85/0.65 → 0 across t=0.50-0.60 (hidden under the blur peak).
//
// Phases 4-5 add: beam, halo, spotlight, multi-grab merge, focal scale-up,
// particles.
function renderSkyCamera(roll, scene, t) {
  const view = focusCameraViewRect(t, scene);
  const viewBox = `${view.cx - view.w / 2} ${view.cy - view.h / 2} ${view.w} ${view.h}`;
  // Camera SVG cross-fade in: snaps from 0 → 1 across t = 0.05 → 0.15 so it's
  // visible before the carousel finishes fading (carousel fade is t = 0.10
  // → 0.45). Avoids a flash of nothing during the handoff.
  const cameraOpacity = Math.min(1, Math.max(0, phase(t, 0.05, 0.15)));

  // Prefer the scene's resolvedConstellation so stand-in misses (where
  // `roll.constellation == null`) render against the swapped-in wireframe.
  const conName = scene.resolvedConstellation || roll.constellation || null;
  const con = conName ? app.data.conByName[conName] : null;
  const color = `oklch(0.82 0.14 ${scene.hue})`;
  const isStandIn = scene.isUnknownConstellationStandIn === true;

  // ---------- progress curves ----------
  const blur = motionBlurStdDeviation(t);
  const split = splitProgress(t);
  const silhOp = silhouetteOpacity(t);
  const pinOp = vertexPinOpacity(t);
  const nonFocalClusterOp = nonFocalClusterOpacity(t);
  const focalClusterOp = focalClusterOpacity(t);

  // ---------- focal-marker resolution ----------
  // Decide which cluster marker (if any) is the focal vertex. With
  // `vertex_source = "jumps"` the marker_positions are 1:1 with jumps; with
  // `vertex_source = "perks"` they are 1:1 with the flattened stars. In
  // either case, the scene's anchorWorld points at (or near) the focal
  // vertex's world coord — we match by proximity so we don't have to plumb
  // index/id from focusScene.
  let focalMarkerIdx = -1;
  if (scene.anchorWorld && con?.marker_positions?.length) {
    let bestDist = Infinity;
    con.marker_positions.forEach((pos, idx) => {
      const [wx, wy] = clusterLocalToWorld(pos[0], pos[1]);
      const dx = wx - scene.anchorWorld[0];
      const dy = wy - scene.anchorWorld[1];
      const d = dx * dx + dy * dy;
      if (d < bestDist) { bestDist = d; focalMarkerIdx = idx; }
    });
  }

  // ---------- silhouette polylines ----------
  // Stand-in misses (curator recorded a miss but doesn't know the
  // constellation) get a dashed silhouette so the unfamiliarity reads at
  // a glance — no name label is shown anywhere, but the line treatment
  // cues "this is a placeholder shape."
  const silhouetteAttrs = {
    fill: "none",
    stroke: color,
    "stroke-width": "1.6",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
    "vector-effect": "non-scaling-stroke",
  };
  if (isStandIn) silhouetteAttrs["stroke-dasharray"] = "4 3";
  const silhouettePolylines = (con?.silhouette || []).map(polyline => {
    const points = polyline.map(point => {
      const [wx, wy] = clusterLocalToWorld(point[0], point[1]);
      return `${wx.toFixed(1)},${wy.toFixed(1)}`;
    }).join(" ");
    return svgEl("polyline", { ...silhouetteAttrs, points });
  });

  // ---------- vertex pins (tiny circles beneath each cluster marker) ----------
  const vertexPins = (con?.marker_positions || []).map(pos => {
    const [wx, wy] = clusterLocalToWorld(pos[0], pos[1]);
    return svgEl("circle", { cx: wx.toFixed(1), cy: wy.toFixed(1), r: "3", fill: color });
  });

  // ---------- cluster markers (focal vs non-focal) ----------
  const nonFocalMarkers = [];
  const focalMarkerNodes = [];
  (con?.marker_positions || []).forEach((pos, idx) => {
    const [wx, wy] = clusterLocalToWorld(pos[0], pos[1]);
    if (idx === focalMarkerIdx) {
      // Focal cluster marker shrinks 54 → 38 across the split.
      const size = lerp(54, 38, split);
      if (focalClusterOp > 0.01) {
        focalMarkerNodes.push(placeCameraStar(wx, wy, 100, color, size, 1));
      }
    } else {
      // Non-focal markers shrink 34 → 18 under the blur fade.
      const size = lerp(34, 18, phase(t, 0.50, 0.60));
      if (nonFocalClusterOp > 0.01) {
        nonFocalMarkers.push(placeCameraStar(wx, wy, 100, color, size, 1));
      }
    }
  });

  // ---------- interior perks (split reveal) + halo + motion arrows + flash (Phase 5) ----------
  const interiorPerkNodes = [];
  const motionArrowNodes = [];
  const flashNodes = [];
  let haloNode = null;
  if (split > 0) {
    const isMiss = scene.branch === "miss";
    const isMultiGrab = scene.branch === "multi-grab";
    const focalScale = focalScaleFactor(t, scene.branch);

    // Resolve the multi-grab merge geometry up-front. The halo center sits at
    // the centroid of the ORIGINAL wireframe positions (it does not chase the
    // moving focals); the merge-target positions for the focal slide are tiny
    // offsets from that center so the rays overlap into one fused unit.
    let mergeCenter = null;
    let originalFocalWorlds = null;
    let mergeT = 0;
    let binaryTargets = null;
    if (isMultiGrab && scene.focalStars?.length) {
      originalFocalWorlds = scene.focalStars.map(star => starWorldFromScene(scene, star));
      const n = originalFocalWorlds.length;
      const sum = originalFocalWorlds.reduce(
        (acc, p) => [acc[0] + p[0], acc[1] + p[1]],
        [0, 0],
      );
      mergeCenter = [sum[0] / n, sum[1] / n];
      mergeT = multiGrabMergeProgress(t);
      if (n === 2) {
        // Canonical binary positions — mirrors scrubber's two-perk diffraction.
        binaryTargets = [
          [mergeCenter[0] - HALO_BINARY_OFFSET.x, mergeCenter[1] + HALO_BINARY_OFFSET.y],
          [mergeCenter[0] + HALO_BINARY_OFFSET.x, mergeCenter[1] - HALO_BINARY_OFFSET.y],
        ];
      } else {
        // n > 2 fallback: distribute evenly around the merge center on a small
        // circle so each focal still arrives at a distinct binary slot.
        const r = HALO_BINARY_OFFSET.x;
        binaryTargets = originalFocalWorlds.map((_, i) => {
          const a = (i / n) * Math.PI * 2;
          return [mergeCenter[0] + Math.cos(a) * r, mergeCenter[1] + Math.sin(a) * r];
        });
      }
    }

    if (scene.focalStars?.length) {
      const focalIds = new Set(scene.focalStars.map(s => s.id));
      scene.focalStars.forEach((star, i) => {
        const original = originalFocalWorlds ? originalFocalWorlds[i] : starWorldFromScene(scene, star);
        let wx = original[0];
        let wy = original[1];
        if (isMultiGrab && binaryTargets && mergeT > 0) {
          const [tx, ty] = binaryTargets[i];
          wx = lerp(wx, tx, mergeT);
          wy = lerp(wy, ty, mergeT);
        }
        const size = sizeFor(Number(star.cost || 100)) * focalScale;
        // Focal perks render at full opacity scaled by split (so they fade
        // in along with the cluster marker fading out).
        interiorPerkNodes.push(
          placeCameraStar(wx, wy, star.cost || 100, "#fff", size, split),
        );

        // Motion arrows for multi-grab focals as they slide toward the merge
        // center (animation.js:361-369). Only render while the slide is
        // visibly in progress AND the focal hasn't already closed the gap.
        if (isMultiGrab && mergeCenter && mergeT > 0.05 && mergeT < 0.9) {
          const dx = mergeCenter[0] - wx;
          const dy = mergeCenter[1] - wy;
          const dist = Math.hypot(dx, dy);
          if (dist > 6) {
            const nx = dx / dist;
            const ny = dy / dist;
            const trailOp = 0.7 * (1 - mergeT);
            motionArrowNodes.push(svgEl("line", {
              x1: (wx + nx * 12).toFixed(2),
              y1: (wy + ny * 12).toFixed(2),
              x2: (wx + nx * 22).toFixed(2),
              y2: (wy + ny * 22).toFixed(2),
              stroke: "white",
              "stroke-width": "1",
              "stroke-linecap": "round",
              opacity: trailOp.toFixed(3),
            }));
          }
        }
      });
      for (const star of scene.ambientStars || []) {
        if (focalIds.has(star.id)) continue;
        const [wx, wy] = starWorldFromScene(scene, star);
        const size = sizeFor(Number(star.cost || 100));
        interiorPerkNodes.push(
          placeCameraStar(wx, wy, star.cost || 100, color, size, nonFocalInteriorOpacity(t, false)),
        );
      }
    } else if (isMiss && scene.missCandidate) {
      const [wx, wy] = starWorldFromScene(scene, scene.missCandidate);
      const size = sizeFor(Number(scene.missCandidate.cost || 100)) * focalScale;
      interiorPerkNodes.push(
        placeCameraStar(wx, wy, scene.missCandidate.cost || 100, color, size, nonFocalInteriorOpacity(t, true)),
      );
    }

    // ---- shared shrinking halo (hit-only) ----
    // Single-focal: starts at the jump perk-radius and tightens onto the focal.
    // Multi-grab: starts at half the original focal-pair distance + 16, shrinks
    // to 14 as the focals fuse. Miss explicitly skips the halo.
    if (!isMiss && scene.focalStars?.length) {
      const auraP = haloAuraProgress(t);
      if (auraP > 0.04) {
        let auraCx = null;
        let auraCy = null;
        let initialR = 0;
        let finalR = 0;
        let shrinkT = 0;
        if (isMultiGrab && mergeCenter && originalFocalWorlds) {
          auraCx = mergeCenter[0];
          auraCy = mergeCenter[1];
          // halfDist uses ORIGINAL wireframe positions (not the moving focals)
          // so the halo's starting size reflects the spread before the slide.
          let halfDist;
          if (originalFocalWorlds.length === 2) {
            const [p0, p1] = originalFocalWorlds;
            halfDist = Math.hypot(p0[0] - p1[0], p0[1] - p1[1]) / 2;
          } else {
            // n>2: use the max distance from the centroid as the spread proxy.
            halfDist = originalFocalWorlds.reduce((acc, p) => {
              return Math.max(acc, Math.hypot(p[0] - mergeCenter[0], p[1] - mergeCenter[1]));
            }, 0);
          }
          initialR = halfDist + 16;
          finalR = 14;
          shrinkT = mergeT;
        } else {
          // Single-focal hit. Halo encompasses the jump siblings initially,
          // tightening onto the focal as it scales up.
          const focal = focalWorldFromScene(scene);
          auraCx = focal[0];
          auraCy = focal[1];
          const focalCost = Number(scene.focalStars[0].cost || 100);
          initialR = JUMP_RADIUS_WORLD * 0.85;
          finalR = sizeFor(focalCost) * focalScale * 0.40;
          shrinkT = easeInOutCubic(auraP);
        }
        if (auraCx != null) {
          const radius = lerp(initialR, finalR, shrinkT);
          const auraOp = lerp(0.18, 0.58, auraP);
          haloNode = svgEl("circle", {
            cx: auraCx.toFixed(2),
            cy: auraCy.toFixed(2),
            r: radius.toFixed(2),
            fill: "none",
            stroke: color,
            "stroke-width": "1.4",
            "vector-effect": "non-scaling-stroke",
            opacity: auraOp.toFixed(3),
          });
        }
      }
    }

    // ---- multi-grab flash burst (animation.js:237-238, 412-415) ----
    // Two pulsing concentric circles. Radii expand with flash intensity so the
    // burst reads as a punchy expand-then-fade rather than a fixed flicker.
    // `flashRaw` is the 0..1 envelope; `multiGrabFlashOpacity` returns the
    // pre-scaled-by-0.32 opacity factor — divide back to recover the envelope.
    if (isMultiGrab && mergeCenter) {
      const flash = multiGrabFlashOpacity(t);
      if (flash > 0.005) {
        const flashRaw = flash / 0.32;
        const outerR = 28 + flashRaw * 14;
        const innerR = 14 + flashRaw * 8;
        flashNodes.push(svgEl("circle", {
          cx: mergeCenter[0].toFixed(2),
          cy: mergeCenter[1].toFixed(2),
          r: outerR.toFixed(2),
          fill: "white",
          opacity: (flash * 0.5).toFixed(3),
        }));
        flashNodes.push(svgEl("circle", {
          cx: mergeCenter[0].toFixed(2),
          cy: mergeCenter[1].toFixed(2),
          r: innerR.toFixed(2),
          fill: "white",
          opacity: flash.toFixed(3),
        }));
      }
    }
  }

  // ---------- beam (Phase 4) ----------
  // Forge reach beam — rises from below the viewport up to the focal perk.
  // Returns { defs: [...], group } or null when invisible.
  const beam = renderBeam(scene, t, view);

  // ---------- spotlight overlay (Phase 5) ----------
  // Two oversized rects centered on the focal: an accent-colored glow + a
  // radial dark vignette with a transparent hole. Drawn last so it sits above
  // everything, including the beam (the beam still reads through the modest
  // glow + the spotlight hole).
  const spotlight = renderSpotlight(scene, t, view);

  // ---------- assemble SVG ----------
  const defs = svgEl("defs", {},
    getCameraSymbolDefs(),
    blur > 0.4
      ? svgEl("filter", { id: "cam-motion-blur", x: "-20%", y: "-20%", width: "140%", height: "140%" },
        svgEl("feGaussianBlur", { stdDeviation: blur.toFixed(2) }),
      )
      : null,
    ...(beam?.defs ?? []),
    ...(spotlight?.defs ?? []),
  );

  // Blur group wraps silhouette + vertex pins + ALL cluster markers (both
  // focal and non-focal). Interior perks stay outside the blur so they read
  // crisp as they emerge.
  const blurGroupProps = blur > 0.4 ? { filter: "url(#cam-motion-blur)" } : {};
  // Stand-in silhouettes ride at ~0.45/0.62 ≈ 0.726 of the normal opacity so
  // the dashes don't read as a brighter outline; the silhOp curve still drives
  // the fade-in/out timing.
  const silhScale = isStandIn ? 0.726 : 1;
  const blurGroup = svgEl("g", blurGroupProps,
    svgEl("g", { opacity: (silhOp * silhScale).toFixed(3) }, ...silhouettePolylines),
    svgEl("g", { opacity: pinOp.toFixed(3) }, ...vertexPins),
    svgEl("g", { opacity: nonFocalClusterOp.toFixed(3) }, ...nonFocalMarkers),
    svgEl("g", { opacity: focalClusterOp.toFixed(3) }, ...focalMarkerNodes),
  );

  // Interior group order (back → front per the design README): focal+ambient
  // perk markers, then multi-grab motion arrows, then the multi-grab flash
  // burst, then the shared halo ring (on top so it reads as the "drawing-in"
  // boundary, but at the modest 0.18-0.58 opacity the beam still rises through).
  const interiorGroup = svgEl("g", { class: "interior-perks" },
    ...interiorPerkNodes,
    ...motionArrowNodes,
    ...flashNodes,
    haloNode,
  );

  // Z-order back→front: defs → blur group → interior perks → beam → spotlight.
  return el("div", {
    class: "sky-camera",
    style: { opacity: cameraOpacity.toFixed(3) },
  },
    svgEl("svg", {
      viewBox,
      preserveAspectRatio: "xMidYMid meet",
    },
      defs,
      blurGroup,
      interiorGroup,
      beam?.group ?? null,
      spotlight?.group ?? null,
    ),
  );
}

// Phase 5 — spotlight vignette overlay. Two camera-spanning rects: an
// accent-colored radial glow + a dark vignette with a transparent inner hole.
// Geometry mirrors `animation.js:524-551`. Returns `{ defs, group }` or null
// when invisible (p < 0.03).
function renderSpotlight(scene, t, view) {
  const p = spotlightProgress(t);
  if (p < 0.03) return null;

  const focal = focalWorldFromScene(scene);
  const hue = scene?.hue ?? 196;
  const accent = `oklch(0.82 0.14 ${hue})`;

  const radius = lerp(220, 64, p);
  const darkOp = lerp(0, 0.74, p);
  const glowOp = lerp(0, 0.12, p);

  // Oversize the rects by 200 world units on each side relative to the camera
  // viewBox so the gradient covers any subpixel slop near the edges.
  const x = view.cx - view.w / 2 - 200;
  const y = view.cy - view.h / 2 - 200;
  const w = view.w + 400;
  const h = view.h + 400;

  const defs = [
    svgEl("radialGradient", {
      id: "spot-glow-grad",
      cx: focal[0].toFixed(2),
      cy: focal[1].toFixed(2),
      r: (radius * 1.15).toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": accent, "stop-opacity": glowOp.toFixed(3) }),
      svgEl("stop", { offset: "1", "stop-color": accent, "stop-opacity": "0" }),
    ),
    svgEl("radialGradient", {
      id: "spot-dark-grad",
      cx: focal[0].toFixed(2),
      cy: focal[1].toFixed(2),
      r: radius.toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": "black", "stop-opacity": "0" }),
      svgEl("stop", { offset: "0.55", "stop-color": "black", "stop-opacity": "0" }),
      svgEl("stop", { offset: "1", "stop-color": "black", "stop-opacity": darkOp.toFixed(3) }),
    ),
  ];

  const group = svgEl("g", { class: "cam-spotlight" },
    svgEl("rect", {
      x: x.toFixed(2), y: y.toFixed(2),
      width: w.toFixed(2), height: h.toFixed(2),
      fill: "url(#spot-glow-grad)",
    }),
    svgEl("rect", {
      x: x.toFixed(2), y: y.toFixed(2),
      width: w.toFixed(2), height: h.toFixed(2),
      fill: "url(#spot-dark-grad)",
    }),
  );

  return { defs, group };
}

// Phase 4 — forge reach beam. 4 layers: outer cone (color-tinted gauss-blurred
// gradient), inner core (whiter, tighter), rising particle motes, apex bloom.
// Geometry and curves mirror `animation.js:432-522` and the design README §
// "The Beam". Returns `{ defs, group }` for the camera SVG to splice in, or
// `null` when the beam isn't visible yet.
function renderBeam(scene, t, view) {
  const op = beamOpacity(t);
  const outcome = scene?.branch === "miss" ? "miss" : "hit";
  const reach = beamReach(t, outcome);
  if (op < 0.005 || reach < 0.001) return null;

  const focal = focalWorldFromScene(scene);
  const hue = scene?.hue ?? 196;
  const color = `oklch(0.82 0.14 ${hue})`;
  const coreColor = `oklch(0.95 0.06 ${hue})`;

  // Beam coordinates: base 30 world units below the camera bottom (off-frame
  // origin), apex lerps from base up to focal.y as reach goes 0 → 1.
  const bottomY = view.cy + view.h / 2 + 30;
  const apexY = lerp(bottomY, focal[1], reach);
  const beamLen = Math.max(1, bottomY - apexY);

  // Apex always tapers to a true point (width 0) regardless of reach. The
  // prototype's `lerp(4, 0, reach)` only landed at zero at full reach (hit);
  // on a miss the beam stalls at reach=0.78, leaving a ~0.88-wide flat top
  // where the gradient is brightest — a visible hard edge stamping out the
  // "beam stops before the mote" visual. With apex=0 the polygon's tip is a
  // single point that the gaussian blur dissolves into the void at any
  // reach state, matching the design intent ("Apex tapers to a true point …
  // so the gaussian blur dissolves the tip into the void on misses").
  const apexW = 0;
  const baseW = 72;
  const coreApexW = 0;
  const coreBaseW = 22;

  const outerPts = [
    [focal[0] - apexW, apexY],
    [focal[0] + apexW, apexY],
    [focal[0] + baseW, bottomY],
    [focal[0] - baseW, bottomY],
  ].map(p => `${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(" ");
  const corePts = [
    [focal[0] - coreApexW, apexY],
    [focal[0] + coreApexW, apexY],
    [focal[0] + coreBaseW, bottomY],
    [focal[0] - coreBaseW, bottomY],
  ].map(p => `${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(" ");

  // Particle motes — fixed seeded x-jitter, phase cycles with t so they
  // continuously stream upward. sin-curve alpha so they emerge from the base
  // and dissolve near the apex.
  const cycleSpeed = 2.6;
  const particleCount = 14;
  const particles = [];
  for (let i = 0; i < particleCount; i += 1) {
    const seed = (i * 73 + 11) % 100;
    const phaseOffset = ((seed / 100) + i / particleCount) % 1;
    // Safe-positive modulo guards against any negative seed/offset combos.
    const ph = ((((t * cycleSpeed) + phaseOffset) % 1) + 1) % 1;
    const py = bottomY - ph * beamLen;
    const widthHere = lerp(baseW, apexW, ph) * 0.7;
    const xJ = ((seed * 1.618) % 1) - 0.5;
    const px = focal[0] + xJ * widthHere;
    const alpha = Math.sin(ph * Math.PI) * 0.55 * op;
    if (alpha < 0.04) continue;
    const psize = 0.7 + (seed % 7) / 7 * 1.0;
    particles.push(svgEl("circle", {
      cx: px.toFixed(2),
      cy: py.toFixed(2),
      r: psize.toFixed(2),
      fill: "#fff",
      opacity: alpha.toFixed(3),
    }));
  }

  // Apex bloom — soft pool of light at the apex. Miss stays dim/tight (no
  // successful lock); hit blooms wider as reach completes.
  const isMiss = outcome === "miss";
  const bloomR = isMiss ? lerp(4, 9, reach) : lerp(8, 26, reach);
  const bloomOp = (isMiss ? 0.25 : 0.7) * reach * op;
  const bloomVisualR = bloomR * 1.6;

  const defs = [
    svgEl("filter", { id: "beam-outer-blur", x: "-30%", y: "-10%", width: "160%", height: "120%" },
      svgEl("feGaussianBlur", { stdDeviation: "6" }),
    ),
    svgEl("filter", { id: "beam-inner-blur", x: "-20%", y: "-10%", width: "140%", height: "120%" },
      svgEl("feGaussianBlur", { stdDeviation: "2.4" }),
    ),
    svgEl("linearGradient", {
      id: "beam-outer-grad",
      x1: "0", y1: apexY.toFixed(2), x2: "0", y2: bottomY.toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": color, "stop-opacity": (0.52 * op).toFixed(3) }),
      svgEl("stop", { offset: "0.45", "stop-color": color, "stop-opacity": (0.20 * op).toFixed(3) }),
      svgEl("stop", { offset: "1", "stop-color": color, "stop-opacity": "0" }),
    ),
    svgEl("linearGradient", {
      id: "beam-inner-grad",
      x1: "0", y1: apexY.toFixed(2), x2: "0", y2: bottomY.toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": coreColor, "stop-opacity": (0.78 * op).toFixed(3) }),
      svgEl("stop", { offset: "0.55", "stop-color": coreColor, "stop-opacity": (0.30 * op).toFixed(3) }),
      svgEl("stop", { offset: "1", "stop-color": coreColor, "stop-opacity": "0" }),
    ),
    svgEl("radialGradient", {
      id: "beam-bloom-grad",
      cx: focal[0].toFixed(2),
      cy: apexY.toFixed(2),
      r: bloomVisualR.toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": "#fff", "stop-opacity": (bloomOp * 0.85).toFixed(3) }),
      svgEl("stop", { offset: "0.45", "stop-color": color, "stop-opacity": (bloomOp * 0.45).toFixed(3) }),
      svgEl("stop", { offset: "1", "stop-color": color, "stop-opacity": "0" }),
    ),
  ];

  const group = svgEl("g", { class: "cam-beam" },
    svgEl("polygon", { points: outerPts, fill: "url(#beam-outer-grad)", filter: "url(#beam-outer-blur)" }),
    svgEl("polygon", { points: corePts, fill: "url(#beam-inner-grad)", filter: "url(#beam-inner-blur)" }),
    ...particles,
    svgEl("circle", {
      cx: focal[0].toFixed(2),
      cy: apexY.toFixed(2),
      r: bloomVisualR.toFixed(2),
      fill: "url(#beam-bloom-grad)",
    }),
  );

  return { defs, group };
}

// Build the shared `<symbol>` defs block, one per cost tier (100/200/400/
// 600/800). Mirrors `design/.../animation.js:54-78`. Each symbol is the
// recipe-driven diffraction star at canonical -50..50 viewBox; instance via
// `<use href="#dm-N" x="-50" y="-50" width="100" height="100" />` on a
// wrapper group that handles translate/scale/color.
//
// One shared gradient `#cam-ray-grad` is declared at the head of the defs
// (animation.js does the same — every symbol references it by id).
//
// The returned element is cached in `_cameraSymbolDefsTemplate` and cloned per
// render — without caching this would rebuild ~150 SVG nodes every frame
// (~9000 createElementNS calls/sec during animation). The contents are
// static (no t-dependent attributes), so cloning is safe.
let _cameraSymbolDefsTemplate = null;
function getCameraSymbolDefs() {
  if (!_cameraSymbolDefsTemplate) _cameraSymbolDefsTemplate = buildCameraSymbolDefs();
  return _cameraSymbolDefsTemplate.cloneNode(true);
}
function buildCameraSymbolDefs() {
  const grad = svgEl("linearGradient", { id: "cam-ray-grad", x1: "0", y1: "0", x2: "1", y2: "0" },
    svgEl("stop", { offset: "0", "stop-color": "transparent" }),
    svgEl("stop", { offset: "0.48", "stop-color": "#fff", "stop-opacity": "0.58" }),
    svgEl("stop", { offset: "0.50", "stop-color": "#fff", "stop-opacity": "0.92" }),
    svgEl("stop", { offset: "0.52", "stop-color": "#fff", "stop-opacity": "0.58" }),
    svgEl("stop", { offset: "1", "stop-color": "transparent" }),
  );

  const symbols = [100, 200, 400, 600, 800].map(cost => {
    const recipe = recipeFor(cost);
    const rays = (count, len, w, offset = 0) => Array.from({ length: count }, (_, i) => {
      const angle = (360 / count) * i + offset + ((i % 2) ? recipe.jitter : -recipe.jitter);
      return svgEl("rect", {
        x: String(-len),
        y: String(-w / 2),
        width: String(len * 2),
        height: String(w),
        rx: String(w / 2),
        fill: "url(#cam-ray-grad)",
        transform: `rotate(${angle.toFixed(2)})`,
      });
    });
    return svgEl("symbol", { id: `dm-${cost}`, viewBox: "-50 -50 100 100", overflow: "visible" },
      svgEl("g", { style: "filter:drop-shadow(0 0 0.6px #fff) drop-shadow(0 0 3px currentColor)" },
        svgEl("g", { opacity: "0.68", style: "mix-blend-mode:screen" },
          ...rays(recipe.major, recipe.length, recipe.width),
        ),
        svgEl("g", { opacity: "0.32", style: "mix-blend-mode:screen" },
          ...rays(recipe.minor, recipe.minorLength, recipe.minorWidth, 360 / (recipe.major * 2)),
        ),
        svgEl("circle", { r: "2.2", fill: "currentColor", opacity: "0.20" }),
        svgEl("circle", { r: "1.4", fill: "#fff" }),
      ),
    );
  });

  return svgEl("g", {}, grad, ...symbols);
}

// Instance a shared diffraction-star symbol at world coord (x, y) with the
// given color/size/opacity. The `<use>` MUST carry x/y/width/height — without
// them the symbol stretches to fit the outer SVG viewport and the wrapper's
// transform misaligns the star (see animation.js:82-86).
function placeCameraStar(x, y, cost, color, visualSize, opacity) {
  const scale = visualSize / 100;
  const id = cost >= 800 ? "dm-800"
    : cost >= 600 ? "dm-600"
    : cost >= 400 ? "dm-400"
    : cost >= 200 ? "dm-200"
    : "dm-100";
  return svgEl("g", {
    transform: `translate(${x.toFixed(2)},${y.toFixed(2)}) scale(${scale.toFixed(3)})`,
    style: `color:${color}`,
    opacity: opacity.toFixed(3),
  },
    svgEl("use", { href: `#${id}`, x: "-50", y: "-50", width: "100", height: "100" }),
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
    el("span", {}, el("span", { class: "perk-name", text: perkDisplayLabel(perk) }), el("span", { class: "perk-source", text: `${roll.constellation || "-"} · ${perk.jump || roll.jump || "-"} · ch ${roll.chapter_num}` })),
    el("span", { class: `perk-cost ${free ? "free" : ""}`, text: free ? "FREE" : `${perk.cost || 0} CP` }),
  );
}

function renderConstellationBars() {
  const chapter = chapterAtWord(app.wordPos);
  const progressByName = new Map((chapter.constellation_progress || []).map(row => [row.name, row]));
  const constellationNames = app.data.constellations.map(c => c.name);
  return el("div", { class: "panel panel-cut detail-panel" },
    el("div", { class: "panel-title" }, el("span", { class: "pip" }), " Constellation progress"),
    el("div", { class: "body" },
      el("div", { class: "constellation-bars" },
        constellationNames.map(name => {
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

// Rendered diameter (in world units, at camera scale 1.0) of a perk mote keyed
// on its cost. Used by the cinematic roll-focus phases — distinct from the
// paid-count sizing in the scrubber's `diffractionMarker`, which intentionally
// scales by paid count rather than cost.
function sizeFor(cost) {
  if (cost >= 800) return 96;
  if (cost >= 400) return 78;
  if (cost >= 200) return 64;
  return 54;
}

// Build the screen-fixed background starfield SVG. Drawn once at app bootstrap
// (see mountBackgroundStarfield); never rebuilt during playback so the dots
// stay stable across frames and "infinitely distant" — they must not be
// camera-relative.
function buildBackgroundStarfield() {
  const STAR_COUNT = 220;
  const VIEW_W = 1600;
  const VIEW_H = 1000;
  let seed = 71;
  const random = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };

  const svg = svgEl("svg", {
    class: "background-starfield",
    viewBox: `0 0 ${VIEW_W} ${VIEW_H}`,
    preserveAspectRatio: "xMidYMid slice",
    "aria-hidden": "true",
    focusable: "false",
  });
  for (let i = 0; i < STAR_COUNT; i += 1) {
    const cx = random() * VIEW_W;
    const cy = random() * VIEW_H;
    const r = 0.5 + random() * 1.0;     // radius in [0.5, 1.5]
    const opacity = 0.18 + random() * 0.42; // opacity in [0.18, 0.60]
    const dim = random() > 0.6;
    svg.appendChild(svgEl("circle", {
      cx: cx.toFixed(2),
      cy: cy.toFixed(2),
      r: r.toFixed(2),
      fill: dim ? "rgba(154, 215, 223, 1)" : "rgba(232, 253, 255, 1)",
      opacity: opacity.toFixed(3),
    }));
  }
  return svg;
}

let backgroundStarfieldMounted = false;
function mountBackgroundStarfield() {
  if (backgroundStarfieldMounted) return;
  // Sits as a screen-fixed sibling behind .viewport. Hosting on document.body
  // keeps it untouched by render()'s root-clearing pass.
  const layer = buildBackgroundStarfield();
  document.body.appendChild(layer);
  backgroundStarfieldMounted = true;
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

// Module-level click delegation. Render() rebuilds the entire DOM tree on
// every frame (including the 60fps cinematic-anim ticks), so per-button
// onClick handlers attached during a render can be silently destroyed
// between the user's mousedown and mouseup — the browser then refuses to
// fire `click`. Routing the click through a stable document.body listener
// fixes that for any control flagged with data-action. Keyboard activation
// (Enter/Space on a focused button) still fires `click` natively, so it
// works through the same path without needing keyboard handling here.
document.body.addEventListener("click", event => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  if (action === "toggle-playback") {
    togglePlayback();
    event.preventDefault();
  } else if (action === "reset-bookmark") {
    app.playing = false;
    if (app.focusAnim) clearFocusAnim();
    setWordPos(0);
    event.preventDefault();
  } else if (action === "set-on-roll-behavior") {
    const value = target.dataset.onRollBehavior;
    if (ON_ROLL_BEHAVIORS.includes(value)) {
      app.onRollBehavior = value;
      store(LS_ON_ROLL_BEHAVIOR, value);
      // Switching to `quick` mid-firing should clear any running cinematic
      // so the scrubber resumes flowing immediately.
      if (value === "quick" && app.focusAnim) clearFocusAnim();
      render();
    }
    event.preventDefault();
  }
});

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

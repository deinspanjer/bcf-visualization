import {
  dataVersionDescription,
  dataVersionOptionLabel,
  dataVersionLabel,
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
const LS_ZOOM = "bcf:timeline:zoom"; // desktop continuous zoom — distinct from LS_MOBILE_TIMELINE_ZOOM ("bcf:timeline-zoom"); do not merge
const LS_MODE = "bcf:mode";
const LS_ON_ROLL_BEHAVIOR = "bcf:on-roll-behavior";
const LS_ROLL_LOCATION = "bcf:roll-location";
const LS_FIELD_LOG_HIDDEN = "bcf:field-log:hidden";
const LS_MOBILE_TIMELINE_ZOOM = "bcf:timeline-zoom"; // mobile quantized zoom (1/2/4/8) — hyphen-separated, distinct from LS_ZOOM ("bcf:timeline:zoom"); do not merge
const LS_TAP_TO_PAUSE = "bcf:tap-to-pause";
const LS_HAPTICS = "bcf:haptics";
const LS_HELP_SEEN = "bcf:help-seen";
const LS_STORAGE_VERSION = "bcf:preview-port-storage-version";
const STORAGE_VERSION = "3";
const MOBILE_TIMELINE_ZOOM_CHOICES = ["1", "2", "4", "8"];

// Single source of truth for the mobile breakpoint: character-identical to the
// @media query at web/mobile.css:11 (D-06). Never hand-roll a second width check.
//
// The landscape clause is height-based, not width-based. It used to be
// `(max-width: 900px)`, inherited from the frozen portrait-banner rule at
// style.css:360 — a threshold that predates large phones. Measured on a real
// iPhone (Safari 18.5) during the Phase 3 gate: landscape is 956x390, so the
// 900px ceiling failed and the whole landscape layout silently fell through to
// the desktop shell. CI never caught it because every test viewport used
// 844x390, which fits under 900.
//
// Height separates the devices by the dimension that actually differs: phones
// in landscape are ~390-440 tall, tablets 768-1024. That stays correct as
// phones get wider, where any width ceiling goes stale again.
//
// style.css:360 keeps the old query and is deliberately NOT edited (it is
// frozen, and Phase 4 deletes it outright). It scopes only
// `.portrait-banner.is-visible`, an element that renders solely inside the
// desktop shell — which no longer mounts at these viewports — so the
// divergence has no runtime effect.
const MOBILE_LAYOUT_QUERY = "(orientation: landscape) and (max-height: 500px), (orientation: portrait) and (max-width: 1100px)";
const MOBILE_MQ = window.matchMedia(MOBILE_LAYOUT_QUERY);
const PORTRAIT_MQ = window.matchMedia("(orientation: portrait)");

function detectLayoutMode() {
  if (!MOBILE_MQ.matches) return "desktop";
  return PORTRAIT_MQ.matches ? "portrait" : "landscape";
}
const DEFAULT_WORD_POS = 450_000;
const DEFAULT_SPEED = 5_000;
const DEFAULT_ZOOM = 2.75;
const DEFAULT_ON_ROLL_BEHAVIOR = "cinematic";
const ON_ROLL_BEHAVIORS = ["cinematic", "pause", "quick"];
const ROLL_LOCATIONS = ["predicted", "curated"];
const DEFAULT_ROLL_LOCATION = "predicted";
// The single allow-list for app.mode, shared by the init read and setMode's
// write-side guard (T-02-12) — "detail" is singular, matching the live
// LS_MODE storage contract; never "details" (the prototype's spelling).
const MODE_CHOICES = ["playthrough", "detail"];
const DEFAULT_MODE = "playthrough";
// The one surface stack (Settings/About/Help) a portrait reader can have
// open at a time (MOBP-05) — openMobileSurface/closeMobileSurface below are
// the only writers of app.mobileSurface.
const MOBILE_SURFACES = ["settings", "info", "help"];

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
  selectedPackageMeta: null,
  mode: readStoredChoice(LS_MODE, MODE_CHOICES, DEFAULT_MODE),
  wordPos: readStoredNumber(LS_BOOKMARK, DEFAULT_WORD_POS),
  playing: false,
  speed: readStoredNumber(LS_SPEED, DEFAULT_SPEED),
  zoom: clamp(readStoredNumber(LS_ZOOM, DEFAULT_ZOOM), 0.5, 6),
  onRollBehavior: readStoredChoice(LS_ON_ROLL_BEHAVIOR, ON_ROLL_BEHAVIORS, DEFAULT_ON_ROLL_BEHAVIOR),
  rollLocation: readStoredChoice(LS_ROLL_LOCATION, ROLL_LOCATIONS, DEFAULT_ROLL_LOCATION),
  fieldLogHidden: readStoredBoolean(LS_FIELD_LOG_HIDDEN, false),
  layoutMode: detectLayoutMode(),
  helpOpen: false,
  settingsOpen: false,
  chromeHidden: false,
  // Phase 3 (D-34/RESEARCH Pattern 4): the landscape chrome auto-hide idle
  // timer's setTimeout handle. Lives on `app`, not `app.dom` (which render()
  // blanks every structural rebuild) and not a module-level closure (which
  // would survive a landscape->portrait->landscape round trip without being
  // clearable) — same reasoning already documented below for
  // mobileSurfaceFocusTrapTeardown. Cleared unconditionally in
  // attachMobileGestures()'s teardown block, before any re-attach.
  mobileChromeHideTimer: null,
  tapToPause: readStoredBoolean(LS_TAP_TO_PAUSE, true),
  haptics: readStoredBoolean(LS_HAPTICS, true),
  helpSeen: readStoredBoolean(LS_HELP_SEEN, false),
  mobileTimelineZoom: Number(readStoredChoice(LS_MOBILE_TIMELINE_ZOOM, MOBILE_TIMELINE_ZOOM_CHOICES, "1")),
  mobileGestureTeardown: null,
  // Phase 2 (D-17/D-18): portrait-only gesture teardown handles, kept separate
  // from mobileGestureTeardown (the Phase 1 diagnostic probe's slot) so
  // re-attaching one never drops the other's teardown.
  mobileSkyTeardown: null,
  mobileRailTeardown: null,
  // Phase 2 Plan 3 (MOBP-04): the rail's measured pixel width (default
  // mirrors the prototype's useState(350) fallback before the first
  // ResizeObserver callback fires), the cached cluster bins computed from
  // it (app.mobileRailBins, recomputed only on structural render/zoom
  // change/resize — never on a playback frame, D-18), and the observer
  // handle itself (defensive-teardown discipline matching the gesture
  // slots above).
  mobileRailWidth: 350,
  // Phase 3 (D-36/RESEARCH Pitfall 6): which layout's ResizeObserver last
  // measured mobileRailWidth, so a stale portrait/landscape measurement is
  // never used to bin the OTHER layout's differently-sized scrub track for
  // one frame after a rotation. null until a measurement lands (Plan 02's
  // ResizeObserver writes it); see mobileScrubWidthDefaultForLayout().
  mobileRailWidthLayout: null,
  mobileRailBins: [],
  mobileRailResizeObserver: null,
  // Auto-pan offset frozen for the duration of one rail drag (null when no
  // drag is in flight). See the onScrub callback for why it must not be
  // recomputed per move.
  mobileScrubPanPct: null,
  // Session-only (never persisted): the first-run sky tap hint mounts once
  // per page load, tracked here rather than localStorage since it's a
  // per-session affordance, not a durable preference.
  mobileSkyHintShown: false,
  // Phase 2 Plan 4 (MOBP-05): the one surface stack. mobileSurface is null
  // or one of MOBILE_SURFACES; mobileSurfaceOpener is the data-action
  // string of the button that opened it (NOT a node reference — render()
  // rebuilds the whole portrait DOM on every structural render, so a raw
  // node would already be detached by the time closeMobileSurface() needs
  // it) — closeMobileSurface() re-resolves a live element by that selector
  // to restore focus there (D-16). mobileSurfaceFocusTrapTeardown lives on
  // `app` (not app.dom, which render() resets) so it survives to be invoked
  // defensively before the next surface mounts. mobileHelpAutoOpened is
  // session-only (never persisted) — it guards the first-run auto-open
  // against re-firing on a later structural render within the same page
  // load.
  mobileSurface: null,
  mobileSurfaceOpener: null,
  mobileSurfaceFocusTrapTeardown: null,
  mobileHelpAutoOpened: false,
  rollFilter: "all",
  rollSort: "roll",
  raf: null,
  lastFrame: 0,
  dom: {},
  carousel: {
    knowledgeIndex: null,
    visibleSlots: new Map(),
  },
  frameKeys: {
    narrative: null,
    skyCamera: null,
    mobileChip: null,
    mobileFocal: null,
    detail: {},
  },
  bookmarkPersistTimer: null,
  bookmarkLastPersistMs: 0,
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
    if (!app.playing) updatePlaybackFrame();
    return;
  }
  // Avoid double-rendering while tickPlayback is already driving frames.
  if (!app.playing) updatePlaybackFrame();
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
    persistBookmarkSoon();
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

function recordStructuralRender() {
  const stats = window.__bcfRenderStats;
  if (stats && typeof stats.structuralRenders === "number") {
    stats.structuralRenders += 1;
  }
}

function persistBookmarkNow() {
  if (app.bookmarkPersistTimer != null) {
    clearTimeout(app.bookmarkPersistTimer);
    app.bookmarkPersistTimer = null;
  }
  store(LS_BOOKMARK, app.wordPos);
  app.bookmarkLastPersistMs = performance.now();
}

function persistBookmarkSoon() {
  if (!app.data) return;
  const now = performance.now();
  if (now - app.bookmarkLastPersistMs >= 500) {
    persistBookmarkNow();
    return;
  }
  if (app.bookmarkPersistTimer != null) return;
  app.bookmarkPersistTimer = setTimeout(() => {
    app.bookmarkPersistTimer = null;
    persistBookmarkNow();
  }, Math.max(0, 500 - (now - app.bookmarkLastPersistMs)));
}

function migratePreviewStorage() {
  try {
    if (localStorage.getItem(LS_STORAGE_VERSION) === STORAGE_VERSION) return;
    for (const key of [
      LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR,
      LS_ROLL_LOCATION, LS_FIELD_LOG_HIDDEN,
      LS_MOBILE_TIMELINE_ZOOM, LS_TAP_TO_PAUSE, LS_HAPTICS, LS_HELP_SEEN,
    ]) {
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
    if (match) return { base: `../${match.path}`, packageId: match.package_id, packageMeta: match, defaultId };
    return { base: DATA_BASE, packageId: null, packageMeta: null, defaultId };
  }
  const defaultPackage = packages.find(pkg => pkg.package_id === defaultId);
  if (defaultPackage) {
    return { base: `../${defaultPackage.path}`, packageId: defaultPackage.package_id, packageMeta: defaultPackage, defaultId };
  }
  return { base: DATA_BASE, packageId: null, packageMeta: null, defaultId };
}

async function loadRuntime() {
  app.packageIndex = await loadPackageIndex();
  const selected = selectPackage(app.packageIndex);
  app.selectedPackageId = selected.packageId;
  app.selectedPackageMeta = selected.packageMeta;

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
    packageMeta: selected.packageMeta || manifest,
    story,
    wireframes: bundle.constellation_wireframes,
    constellations,
    conByName,
    jumpWireframeByKey,
    clusterAnchors: buildClusterAnchors(bundle.constellation_wireframes),
    predictedRolls,
    predictedRollsMeta: bundle.predicted_rolls_meta,
  };
  rebuildRollLocationCaches();
  app.wordPos = clamp(app.wordPos, 0, story.total_words);
  mountSharedDiffractionDefs();
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
        predicted_ordinal: rawRoll.predicted_ordinal ?? null,
        predicted_label: rawRoll.predicted_label ?? null,
        source_ordinal: rawRoll.source_ordinal ?? null,
        source_label: rawRoll.source_label ?? null,
        roll_ordinal: rawRoll.roll_ordinal ?? null,
        roll_label: rawRoll.roll_label ?? null,
        chapter_ordinal: rawRoll.chapter_ordinal ?? null,
        chapter_label: rawRoll.chapter_label ?? null,
        association_source: rawRoll.association_source || "none",
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

// rollStepFrom(wordPos, dir): the sky swipe-step target, one roll at a time.
// Derives the current index from lastRollAtWord's result rather than a
// second binary search / roll-index lookup (no-parallel-implementations) —
// lastRollAtWord IS the single roll-lookup semantic in the codebase. dir is
// +1 (forward) or -1 (backward); the result clamps into [0, rolls.length-1]
// so repeated steps past either end hold at the first/last roll instead of
// throwing or wrapping. Returns null when the story has no rolls at all.
function rollStepFrom(wordPos, dir) {
  const rolls = app.data.story.rolls;
  if (!rolls.length) return null;
  const current = lastRollAtWord(wordPos);
  const currentIndex = current ? rolls.indexOf(current) : -1;
  const nextIndex = clamp(currentIndex + dir, 0, rolls.length - 1);
  return rolls[nextIndex];
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

function rebuildRollLocationCaches() {
  app.carousel.knowledgeIndex = app.data ? buildConstellationKnowledgeIndex(app.data.story.rolls) : null;
  app.carousel.visibleSlots = new Map();
}

function formatRollLabel(roll) {
  if (!roll) return "";
  const chRef = roll.roll_sequence_in_chapter != null ? `ch ${roll.chapter_num} #${roll.roll_sequence_in_chapter}` : `ch ${roll.chapter_num}`;
  return roll.roll_label ? `${roll.roll_label} · ${chRef}` : chRef;
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
  persistBookmarkNow();
  updatePlaybackFrame();
}

function setMode(mode) {
  // T-02-12: write-side allow-list guard mirroring setRollLocation's — an
  // out-of-list value (e.g. the prototype's plural "details") must never
  // reach storage, or the next reload would silently revert to the default.
  if (!MODE_CHOICES.includes(mode)) return;
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
    rebuildRollLocationCaches();
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
  // current roll, clear that lock so playback can resume past the roll.
  // Without this the lock would re-grab on the very next render. The roll's
  // firing window is still open, so we don't re-trigger the cinematic for
  // the same roll — see startFocusAnim trigger logic.
  releasePausedFocusLock();
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
  updatePlaybackFrame();
}

function stopPlayback() {
  app.playing = false;
  if (app.raf) cancelAnimationFrame(app.raf);
  app.raf = null;
  persistBookmarkNow();
  updatePlaybackFrame();
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
  ) {
    releasePausedFocusLock();
    if (!app.playing) startPlayback();
    else updatePlaybackFrame();  // keep playing; next tick sees the lock released
    // Escaping a held cinematic always ends in a playing state (both
    // branches above), so the landscape auto-hide window re-arms here too
    // (D-28) — this early return must cover the same ground as the
    // ordinary exit below, not leave a hole in the "only while playing"
    // gate.
    resetMobileChromeHideTimer();
    return;
  }
  if (app.playing) {
    stopPlayback();
    // D-28: pausing reveals chrome and holds it revealed. Reveal first,
    // then reset — resetMobileChromeHideTimer()'s own app.playing gate
    // turns the reset into a pure clear (no new window arms) now that
    // app.playing is false.
    revealMobileChrome();
    resetMobileChromeHideTimer();
  } else {
    startPlayback();
    resetMobileChromeHideTimer();
  }
}

function releasePausedFocusLock() {
  if (!app.focusAnim || app.focusAnim.behavior !== "pause") return false;
  app.focusAnim = {
    ...app.focusAnim,
    behavior: "cinematic",
    startMs: performance.now() - app.focusAnim.durationMs,
  };
  return true;
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
  // In both locked cases we still update the frame to keep the cinematic camera
  // advancing, but we skip the wordPos write so the scrubber stays parked.
  if (focusAnimIsLocking()) {
    updatePlaybackFrame();
    app.raf = requestAnimationFrame(tickPlayback);
    return;
  }
  const next = app.wordPos + app.speed * dt;
  if (next >= app.data.story.total_words) {
    app.wordPos = app.data.story.total_words;
    persistBookmarkNow();
    app.playing = false;
    updatePlaybackFrame();
    return;
  }
  app.wordPos = Math.round(next);
  persistBookmarkSoon();
  updatePlaybackFrame();
  app.raf = requestAnimationFrame(tickPlayback);
}

function render() {
  const root = document.getElementById("root");
  clear(root);
  recordStructuralRender();
  app.dom = {};
  app.frameKeys = { narrative: null, skyCamera: null, mobileChip: null, mobileFocal: null, mobileActiveDot: null, mobileFieldLog: null, mobileCinemaScrub: null, detail: {} };
  app.carousel.visibleSlots = new Map();
  if (app.error) {
    root.append(renderLoadError(app.error));
    return;
  }
  if (!app.data) {
    root.append(renderLoading());
    return;
  }
  // Phase 3: the D-12 interim landscape fallback (renderAppShell() for
  // layoutMode === "landscape") is retired — landscape gets its own arm,
  // renderMobileLandscape(), exactly like portrait's D-12 arm. Only
  // layoutMode === "desktop" still appends renderAppShell().
  root.append(
    app.layoutMode === "portrait" ? renderMobilePortrait()
    : app.layoutMode === "landscape" ? renderMobileLandscape()
    : renderAppShell(),
  );
  cachePlaybackDomRefs();
  updatePlaybackFrame();
  if (app.layoutMode !== "desktop") {
    root.append(el("div", {
      class: "mobile-gesture-probe",
      "aria-hidden": "true",
      // z-index pinned to the max 32-bit signed int so the portrait DOM
      // (which now renders real, stacked, pointer-events:auto content) can
      // never steal this diagnostic probe's hit target (Phase 1 tests drive
      // it at PHONE_PORTRAIT, F-01).
      style: "position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0;z-index:2147483647;",
    }));
    attachMobileGestureProbes();
    // Phase 3 (D-34/Pitfall 3): ONE gesture-attach lifecycle and ONE focus-
    // trap re-attach serve BOTH mobile layouts — this whole block (both
    // calls) moved from portrait-only to every non-desktop layout in a
    // single edit, so a landscape flyout traps keyboard focus exactly like
    // portrait's does, and never silently stays portrait-only while
    // gesture-attach alone gets generalized.
    attachMobileGestures();
    // D-16: the focus trap re-attaches to whichever surface node this
    // render pass just built (or tears down if none is open) — never
    // left pointing at a node the last clear(root) already detached.
    if (app.mobileSurface) {
      trapMobileSurfaceFocus(document.querySelector(".mobile-flyout, .mobile-help-overlay"));
    } else {
      teardownMobileSurfaceFocusTrap();
    }
  }
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
    return el("span", { class: "data-version", text: dataVersionLabel(app.data.pkg) });
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
      el("span", { text: dataVersionLabel(app.data.packageMeta || app.data.pkg) }),
      el("span", { text: dataVersionDescription(app.data.packageMeta || app.data.pkg, app.selectedPackageId === (app.packageIndex?.default_package_id || app.selectedPackageId)) }),
      renderPackageSelector(),
    ),
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
      style: { left: "0", transform: `translateX(${(app.wordPos / total) * stackPx}px)` },
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

function playthroughFrameState({ syncFocus = true } = {}) {
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
  if (syncFocus && firing && lastRoll && cinematicEligible) {
    const uid = String(lastRoll.uid);
    if (!app.focusAnim || app.focusAnim.rollUid !== uid) {
      startFocusAnim(lastRoll, app.onRollBehavior);
    }
  } else if (syncFocus && app.focusAnim) {
    clearFocusAnim();
  }

  // The sky camera only renders when we've actually started a focus
  // animation — trigger-event rolls and `quick` mode keep the carousel
  // visible without a cinematic handoff.
  const cinematicActive = !!app.focusAnim && firing && lastRoll;
  const scene = cinematicActive ? focusScene(lastRoll, app.data) : null;
  const focusT = currentFocusAnimT();
  return { chapter, lastRoll, firing, cinematicActive, scene, focusT };
}

function renderPlaythrough() {
  const frame = playthroughFrameState();
  return el("div", { class: `playthrough ${app.fieldLogHidden ? "field-log-hidden" : ""}` },
    el("div", { class: "viewport" },
      renderCarousel(frame.scene ? frame.focusT : null, frame.firing && frame.cinematicActive),
      renderViewportFrame(),
      el("div", { class: "sky-camera-layer" },
        frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,
      ),
    ),
    el("div", { class: "narrative-mount" },
      !app.fieldLogHidden ? renderNarrativeReadout(frame.firing ? frame.lastRoll : null, frame.chapter) : null,
    ),
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
  const model = carouselFrameModel(focusT, firingCinematic);
  return el("div", { class: "carousel-strip", style: model.stripStyle },
    model.slots.map(slot => createCarouselSlot(slot)),
  );
}

function carouselFrameModel(focusT = null, firingCinematic = false) {
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
    return { stripStyle: stripStyle(`translateX(${-cardHalf}px)`), slots: [] };
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
  const knowledgeIndex = app.carousel.knowledgeIndex || buildConstellationKnowledgeIndex(rolls);

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
    slots.push({ uid: String(roll.uid), roll, con, active, flank, outlineVisible, leftPx: cardPx, hidden: firingCinematic && active });
  }
  return { stripStyle: stripStyle(`translateX(${-(playheadPx + cardHalf)}px)`), slots };
}

function createCarouselSlot(slot) {
  const node = el("div", {
    class: "carousel-slot",
    "data-roll-uid": slot.uid,
  }, slot.con
    ? renderConstellationCard(slot.con, slot.active, slot.flank, slot.outlineVisible)
    : renderUnresolvedCard(slot.active, slot.flank));
  applyCarouselSlotState(node, slot);
  return node;
}

function applyCarouselSlotState(node, slot) {
  node.style.left = `${slot.leftPx}px`;
  node.style.opacity = slot.hidden ? "0" : "";
  const card = node.querySelector(".const-card");
  if (!card) return;
  card.classList.toggle("is-active", slot.active);
  card.classList.toggle("is-flank", slot.flank);
  card.classList.toggle("is-firing", slot.hidden);
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
  const glowBaseW = baseW * 1.55;
  const glowPts = [
    [focal[0], apexY],
    [focal[0], apexY],
    [focal[0] + glowBaseW, bottomY],
    [focal[0] - glowBaseW, bottomY],
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
    svgEl("linearGradient", {
      id: "beam-glow-grad",
      x1: "0", y1: apexY.toFixed(2), x2: "0", y2: bottomY.toFixed(2),
      gradientUnits: "userSpaceOnUse",
    },
      svgEl("stop", { offset: "0", "stop-color": color, "stop-opacity": (0.18 * op).toFixed(3) }),
      svgEl("stop", { offset: "0.55", "stop-color": color, "stop-opacity": (0.10 * op).toFixed(3) }),
      svgEl("stop", { offset: "1", "stop-color": color, "stop-opacity": "0" }),
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
    svgEl("polygon", { points: glowPts, fill: "url(#beam-glow-grad)" }),
    svgEl("polygon", { points: outerPts, fill: "url(#beam-outer-grad)" }),
    svgEl("polygon", { points: corePts, fill: "url(#beam-inner-grad)" }),
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
      el("span", { class: "no-log-detail", text: roll ? `${roll.roll_label || "roll"} · ch ${roll.chapter_num}` : `ch ${chapter.chapter_num} · the Forge is between reaches` }),
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
      el("span", { class: "roll-id", text: roll.roll_label || roll.chapter_label || "--" }),
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
  return el("div", { id: "selected-chapter-panel", class: "panel panel-cut detail-panel" },
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
  const items = recentAcquisitionItems(app.wordPos);
  return el("div", { id: "recent-acquisitions-panel", class: "panel panel-cut detail-panel" },
    el("div", { class: "panel-title" }, el("span", { class: "pip" }), " Most recent acquisitions"),
    el("div", { class: "body" },
      items.length ? el("ul", { class: "perk-list" }, items.slice(0, 14).map(item => perkListItem(item.perk, item.roll, item.free))) : el("p", { class: "empty-copy", text: "No motes acquired yet." }),
    ),
  );
}

function recentAcquisitionItems(wordPos) {
  const items = [];
  for (const roll of recentRolls(wordPos, 20).filter(r => r.outcome === "hit")) {
    for (const perk of paidRollPerks(roll)) items.push({ perk, roll, free: false });
    for (const perk of roll.free_perks || []) items.push({ perk, roll, free: true });
    if (items.length >= 14) break;
  }
  return items;
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
  return el("div", { id: "constellation-bars-panel", class: "panel panel-cut detail-panel" },
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
  const recipe = recipeFor(cost);
  const rays = (count, length, width, offset = 0) => Array.from({ length: count }, (_, index) => {
    const angle = (360 / count) * index + offset + (index % 2 ? recipe.jitter : -recipe.jitter);
    return svgEl("rect", { x: -length, y: -width / 2, width: length * 2, height: width, rx: width / 2, fill: "url(#diffraction-ray-grad)", transform: `rotate(${angle.toFixed(2)})` });
  });
  return svgEl("svg", {
    class: "diffraction-star",
    viewBox: "-50 -50 100 100",
    "aria-hidden": "true",
    focusable: "false",
    style: `position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:${pixelSize}px;height:${pixelSize}px;color:${color};overflow:visible;opacity:.76;pointer-events:none`,
  },
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

let sharedDiffractionDefsMounted = false;
function mountSharedDiffractionDefs() {
  if (sharedDiffractionDefsMounted || document.getElementById("diffraction-ray-grad")) return;
  const defs = svgEl("svg", {
    id: "diffraction-marker-defs",
    width: "0",
    height: "0",
    "aria-hidden": "true",
    focusable: "false",
    style: "position:absolute;width:0;height:0;overflow:hidden",
  },
    svgEl("defs", {},
      svgEl("linearGradient", { id: "diffraction-ray-grad", x1: "0", y1: "0", x2: "1", y2: "0" },
        svgEl("stop", { offset: "0", "stop-color": "transparent" }),
        svgEl("stop", { offset: "0.48", "stop-color": "#fff", "stop-opacity": "0.58" }),
        svgEl("stop", { offset: "0.50", "stop-color": "#fff", "stop-opacity": "0.92" }),
        svgEl("stop", { offset: "0.52", "stop-color": "#fff", "stop-opacity": "0.58" }),
        svgEl("stop", { offset: "1", "stop-color": "transparent" }),
      ),
    ),
  );
  document.body.appendChild(defs);
  sharedDiffractionDefsMounted = true;
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

// Mobile surface-dock icons (Plan 02-04) — ported verbatim from
// design/mobile-ux/prototype/panels.jsx's GearIcon/InfoIcon/HelpIcon
// (same viewBox/path data), sized to the compact 18px the prototype uses.
function mobileGearIcon() {
  return svgEl(
    "svg",
    { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.6", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svgEl("circle", { cx: "12", cy: "12", r: "3" }),
    svgEl("path", { d: "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" }),
  );
}

function mobileInfoIcon() {
  return svgEl(
    "svg",
    { width: 18, height: 18, viewBox: "0 0 18 18", fill: "none", stroke: "currentColor", "stroke-width": "1.3", "aria-hidden": "true" },
    svgEl("circle", { cx: "9", cy: "9", r: "7" }),
    svgEl("path", { d: "M9 8v4M9 5.5v.5", "stroke-linecap": "round" }),
  );
}

function mobileHelpIcon() {
  return svgEl(
    "svg",
    { width: 18, height: 18, viewBox: "0 0 18 18", fill: "none", stroke: "currentColor", "stroke-width": "1.4", "aria-hidden": "true" },
    svgEl("circle", { cx: "9", cy: "9", r: "7" }),
    svgEl("path", { d: "M7 7a2 2 0 1 1 3 1.7c-.7.4-1 .8-1 1.5M9 12.5v.5", "stroke-linecap": "round" }),
  );
}

function cachePlaybackDomRefs() {
  app.dom = {
    scrubberScroller: document.querySelector(".scrubber-scroller"),
    scrubberStack: document.querySelector(".scrubber-stack"),
    playhead: document.querySelector("#scrubber-playhead"),
    readoutChapter: document.querySelector(".scrubber-readout .readout-chapter"),
    readoutTitle: document.querySelector(".scrubber-readout .readout-title"),
    readoutMeta: document.querySelector(".scrubber-readout .readout-meta"),
    statStrip: document.querySelector(".stat-strip"),
    playPause: document.querySelector("#play-pause"),
    playthrough: document.querySelector(".playthrough"),
    viewport: document.querySelector(".playthrough .viewport"),
    carouselStrip: document.querySelector(".carousel-strip"),
    skyCameraLayer: document.querySelector(".sky-camera-layer"),
    narrativeMount: document.querySelector(".narrative-mount"),
    detail: document.querySelector(".detail"),
    selectedChapterPanel: document.querySelector("#selected-chapter-panel"),
    recentAcquisitionsPanel: document.querySelector("#recent-acquisitions-panel"),
    constellationBarsPanel: document.querySelector("#constellation-bars-panel"),
    rollLogPanel: document.querySelector("#detail-roll-log-panel"),
  };
  if (app.layoutMode === "portrait") {
    // Portrait-only refs (D-18) — appended to the same app.dom object so
    // updateMobilePortraitFrame() can mutate text/style without rebuilding
    // the rail's lanes every frame. Desktop refs above stay untouched.
    app.dom.mobileSky = document.querySelector(".mobile-sky");
    app.dom.mobileSkyCameraLayer = document.querySelector(".mobile-sky-camera-layer");
    app.dom.mobileFocalLabel = document.querySelector(".mobile-focal-label");
    app.dom.mobileDockMeta = document.querySelector(".mobile-dock-meta");
    app.dom.mobileDockTitle = document.querySelector(".mobile-dock-title");
    app.dom.mobileFab = document.querySelector(".mobile-fab-play");
    app.dom.mobileRail = document.querySelector(".mobile-rail");
    app.dom.mobileRailInner = document.querySelector(".mobile-rail-inner");
    app.dom.mobileRailRollsLane = document.querySelector(".mobile-lane-rolls");
    app.dom.mobilePlayhead = document.querySelector(".mobile-playhead");
    app.dom.mobileActiveDot = document.querySelector(".mobile-roll-dot.active");
    app.dom.mobileTopCluster = document.querySelector(".mobile-top-cluster");
    app.dom.mobileChipRow = document.querySelector(".mobile-chip-row");
    app.dom.mobileHintRow = document.querySelector(".mobile-hint-row");
  } else if (app.layoutMode === "landscape") {
    // Landscape-only refs (D-18/D-26) — a distinct branch from portrait's
    // above (never collapsed into one `!== "desktop"` block: the ref sets
    // genuinely differ). mobileSky/mobileSkyCameraLayer/mobileFocalLabel/
    // mobileTopCluster/mobileChipRow use the SAME selectors as portrait
    // (D-35's shared sky helper) — safe because only one layout is ever
    // mounted, so exactly one of these two branches ever queries the DOM.
    app.dom.mobileSky = document.querySelector(".mobile-sky");
    app.dom.mobileSkyCameraLayer = document.querySelector(".mobile-sky-camera-layer");
    app.dom.mobileFocalLabel = document.querySelector(".mobile-focal-label");
    app.dom.mobileTopCluster = document.querySelector(".mobile-top-cluster");
    app.dom.mobileChipRow = document.querySelector(".mobile-chip-row");
    app.dom.mobileFieldLog = document.querySelector(".mobile-field-log");
    app.dom.mobileFieldLogHeader = document.querySelector(".mobile-field-log-header");
    app.dom.mobileFieldLogHeaderCount = document.querySelector(".mobile-field-log-header .count");
    app.dom.mobileFieldLogList = document.querySelector(".mobile-field-log-list");
    app.dom.mobileCinemaScrub = document.querySelector(".mobile-cinema-scrub");
    app.dom.mobileCinemaScrubTrack = document.querySelector(".mobile-cinema-scrub-track");
    app.dom.mobileCinemaScrubInner = document.querySelector(".mobile-cinema-scrub-inner");
    app.dom.mobileCinemaScrubProgress = document.querySelector(".mobile-cinema-scrub-progress");
    app.dom.mobileCinemaScrubThumb = document.querySelector(".mobile-cinema-scrub-thumb");
    app.dom.mobileCinemaScrubFab = document.querySelector(".mobile-cinema-scrub-fab");
    app.dom.mobileCinemaScrubCount = document.querySelector(".mobile-cinema-scrub-count");
    app.dom.mobileDockStatus = document.querySelector(".mobile-dock-status");
  }
  app.carousel.visibleSlots = new Map(
    [...document.querySelectorAll(".carousel-slot[data-roll-uid]")]
      .map(slot => [slot.dataset.rollUid, slot]),
  );
}

function updatePlaybackFrame() {
  if (!app.data) return;
  // D-18/T-02-01: portrait has no #scrubber-playhead, so this early return
  // MUST land before the `!app.dom?.playhead` gate below — otherwise the
  // very first portrait frame recurses into render() forever (RESEARCH
  // Pitfall 2). Landscape has no #scrubber-playhead either (Phase 3), so its
  // early return needs the same ordering. Desktop is byte-identical past
  // this point.
  if (app.layoutMode === "portrait") {
    updateMobilePortraitFrame();
    return;
  }
  if (app.layoutMode === "landscape") {
    updateMobileLandscapeFrame();
    return;
  }
  if (!app.dom?.playhead) {
    render();
    return;
  }
  updateScrubberFrame();
  updateStatStripFrame();
  updatePlaybackControlsFrame();
  if (app.mode === "playthrough") updatePlaythroughFrame();
  else if (app.mode === "detail") updateDetailFrame();
  centerScrubber();
}

function updateScrubberFrame() {
  const { playhead, scrubberStack, readoutChapter, readoutTitle, readoutMeta } = app.dom;
  if (!playhead || !scrubberStack) return;
  const story = app.data.story;
  const total = story.total_words || 1;
  const stackWidth = scrubberStack.getBoundingClientRect().width;
  const x = (app.wordPos / total) * stackWidth;
  playhead.style.left = "0";
  playhead.style.transform = `translateX(${x}px)`;
  playhead.setAttribute("aria-valuenow", String(app.wordPos));

  const currentChapter = chapterAtWord(app.wordPos);
  if (readoutChapter) readoutChapter.textContent = `ch ${currentChapter.chapter_num} · ${currentChapter.pov}`;
  if (readoutTitle) readoutTitle.textContent = currentChapter.title;
  if (readoutMeta) {
    const metaText = `${currentChapter.publish_date || "undated"} · word ${formatWords(app.wordPos)} / ${formatWords(story.total_words)}`
      + (currentChapter.banked_cp_at_end != null ? ` · ${currentChapter.banked_cp_at_end} CP banked` : "");
    if (readoutMeta.firstChild?.nodeType === Node.TEXT_NODE) readoutMeta.firstChild.nodeValue = metaText;
    else readoutMeta.textContent = metaText;
  }
}

function updateStatStripFrame() {
  const statStrip = app.dom.statStrip;
  if (!statStrip) return;
  const next = renderStatStrip();
  statStrip.replaceChildren(...[...next.childNodes]);
}

function updatePlaybackControlsFrame() {
  const playPause = app.dom.playPause;
  if (!playPause) return;
  const label = app.playing ? "Pause" : "Play";
  playPause.setAttribute("aria-label", label);
  playPause.title = `${label} (space)`;
  playPause.textContent = app.playing ? "❚❚" : "▶";
}

function updatePlaythroughFrame() {
  const frame = playthroughFrameState();
  if (app.dom.playthrough) {
    app.dom.playthrough.classList.toggle("field-log-hidden", app.fieldLogHidden);
  }
  updateCarouselFrame(frame.scene ? frame.focusT : null, frame.firing && frame.cinematicActive);
  const skyCameraKey = frame.scene ? `scene:${frame.lastRoll?.uid || ""}` : "none";
  if (app.dom.skyCameraLayer && (frame.scene || app.frameKeys.skyCamera !== skyCameraKey)) {
    app.dom.skyCameraLayer.replaceChildren(
      ...(frame.scene ? [renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT)] : []),
    );
    app.frameKeys.skyCamera = skyCameraKey;
  }
  const narrativeRollUid = frame.firing ? (frame.lastRoll?.uid || "none") : "none";
  const recentRollUid = frame.lastRoll?.uid || "none";
  const narrativeKey = app.fieldLogHidden
    ? "hidden"
    : `${frame.chapter.chapter_num}|${narrativeRollUid}|${recentRollUid}`;
  if (app.dom.narrativeMount && app.frameKeys.narrative !== narrativeKey) {
    app.dom.narrativeMount.replaceChildren(
      ...(!app.fieldLogHidden ? [renderNarrativeReadout(frame.firing ? frame.lastRoll : null, frame.chapter)] : []),
    );
    app.frameKeys.narrative = narrativeKey;
  }
}

function updateDetailFrame() {
  const detail = app.dom.detail;
  if (!detail) return;
  const keys = detailFrameKeys();
  updateDetailPanel("selectedChapterPanel", "#selected-chapter-panel", keys.selectedChapter, renderSelectedChapter);
  updateDetailPanel("recentAcquisitionsPanel", "#recent-acquisitions-panel", keys.recentAcquisitions, renderRecentAcquisitions);
  updateDetailPanel("constellationBarsPanel", "#constellation-bars-panel", keys.constellationBars, renderConstellationBars);
  updateDetailPanel("rollLogPanel", "#detail-roll-log-panel", keys.rollLog, renderRollLog);
}

function updateDetailPanel(domKey, selector, key, renderPanel) {
  app.frameKeys.detail = app.frameKeys.detail || {};
  if (app.frameKeys.detail[domKey] === key && app.dom[domKey]?.isConnected) return;
  const current = app.dom[domKey] || document.querySelector(selector);
  const next = renderPanel();
  if (current) current.replaceWith(next);
  else app.dom.detail?.appendChild(next);
  app.dom[domKey] = next;
  app.frameKeys.detail[domKey] = key;
}

function detailFrameKeys() {
  const chapter = chapterAtWord(app.wordPos);
  const chapterKey = chapter?.chapter_num || "";
  const progressKey = (chapter.constellation_progress || [])
    .map(row => `${row.name}:${row.discovered ?? row.count ?? 0}/${row.total ?? 0}:${row.discovered_pct ?? 0}`)
    .join("|");
  const recentKey = recentAcquisitionItems(app.wordPos)
    .slice(0, 14)
    .map(item => `${rollIdentity(item.roll)}:${perkDisplayLabel(item.perk)}:${item.free ? "free" : "paid"}`)
    .join("|");
  const rows = buildRollLogRows(app.data.story.rolls, app.wordPos, {
    filter: app.rollFilter,
    sort: app.rollSort,
  }).slice(0, 250);
  const rollLogKey = [
    app.rollFilter,
    app.rollSort,
    app.rollLocation,
    rows.map(row => [
      rollIdentity(row.roll),
      row.clickWord,
      row.outcome,
      row.paidCost,
      row.availableCp ?? "",
      row.names.join("~"),
    ].join(":")).join("|"),
  ].join("||");
  return {
    selectedChapter: chapterKey,
    recentAcquisitions: recentKey,
    constellationBars: `${chapterKey}|${progressKey}`,
    rollLog: rollLogKey,
  };
}

function rollIdentity(roll) {
  return String(roll?.uid ?? roll?.roll_label ?? roll?.word_position ?? "");
}

function updateCarouselFrame(focusT = null, firingCinematic = false) {
  const strip = app.dom.carouselStrip;
  if (!strip) return;
  const model = carouselFrameModel(focusT, firingCinematic);
  strip.style.transform = model.stripStyle.transform || "";
  strip.style.opacity = model.stripStyle.opacity || "";
  const nextUids = new Set(model.slots.map(slot => slot.uid));
  for (const [uid, node] of app.carousel.visibleSlots) {
    if (!nextUids.has(uid)) {
      node.remove();
      app.carousel.visibleSlots.delete(uid);
    }
  }
  for (const slotModel of model.slots) {
    let slot = app.carousel.visibleSlots.get(slotModel.uid);
    if (!slot) {
      slot = createCarouselSlot(slotModel);
      app.carousel.visibleSlots.set(slotModel.uid, slot);
    } else {
      applyCarouselSlotState(slot, slotModel);
    }
    strip.appendChild(slot);
  }
}

function centerScrubber() {
  const scroller = app.dom.scrubberScroller;
  const stack = app.dom.scrubberStack;
  if (!scroller || !stack || !app.data) return;
  const x = (app.wordPos / Math.max(1, app.data.story.total_words)) * stack.getBoundingClientRect().width;
  const target = clamp(x - scroller.clientWidth / 2, 0, Math.max(0, stack.scrollWidth - scroller.clientWidth));
  if (Math.abs(scroller.scrollLeft - target) < 1) return;
  scroller.scrollLeft = target;
}

// ── Mobile UX ─────────────────────────────────────────────────────────────
// Phase 1 plumbing (INTEGRATION_PLAN.md §0.4): layout-mode detection, the
// window.__bcfPrefs bridge for the verbatim mobile-gestures.js port, the
// bcf:* preference setters Phase 2's Settings UI will call, and the
// per-render gesture attach lifecycle (D-06, D-07, D-09, D-11).

// rAF-coalesced layout-mode recompute. A discrete layout transition is the
// one sanctioned full-render trigger; resize/orientation event storms
// collapse into a single check per frame. (The ~100ms iOS re-settle re-check
// is intentionally NOT added until a real device shows the flap.)
let layoutRaf = null;
function onLayoutMaybeChanged() {
  if (layoutRaf != null) return;
  layoutRaf = requestAnimationFrame(() => {
    layoutRaf = null;
    const next = detectLayoutMode();
    if (next === app.layoutMode) return;
    app.layoutMode = next;
    window.__bcfLayoutMode = next;
    // Phase 3 (RESEARCH Pitfall 6/CONTEXT A2): reset the width-guard BEFORE
    // render() so mobileScrubWidthDefaultForLayout() supplies THIS layout's
    // default for the very first frame, instead of one frame rendering with
    // the outgoing layout's stale ResizeObserver measurement (or the shared
    // default) mis-binning the new track's width.
    app.mobileRailWidthLayout = null;
    render();
    // D-31: rotating into landscape counts as activity — the reader sees
    // the controls they just rotated into, and the cinema view still
    // appears for someone who then simply watches. This must run AFTER
    // render(), because the cinema-scrub DOM ref
    // (app.dom.mobileCinemaScrub, read by revealMobileChrome() and armed by
    // resetMobileChromeHideTimer()) does not exist until cachePlaybackDomRefs()
    // has run inside render() above. No setTimeout/debounce/pointer-state
    // check is added here or anywhere else in this function — an ignored or
    // deferred rotation reads to the reader as a freeze (D-22); the rAF
    // coalescing above is the whole of the sanctioned debouncing.
    if (next === "landscape") {
      revealMobileChrome();
      resetMobileChromeHideTimer();
    }
  });
}
MOBILE_MQ.addEventListener("change", onLayoutMaybeChanged);
PORTRAIT_MQ.addEventListener("change", onLayoutMaybeChanged);
window.addEventListener("orientationchange", onLayoutMaybeChanged);
window.__bcfLayoutMode = app.layoutMode;

// Bridge for mobile-gestures.js's haptic() guard (reads window.__bcfPrefs?.haptics)
// and a read surface for tests. Keeps the gesture module byte-identical to the
// prototype (D-11: haptics stay decorative-only).
Object.defineProperty(window, "__bcfPrefs", {
  get: () => ({
    haptics: app.haptics,
    tapToPause: app.tapToPause,
    helpSeen: app.helpSeen,
    mobileTimelineZoom: app.mobileTimelineZoom,
  }),
});

// Preference setters — the MOBF-04 written-on-change contract Phase 2's
// Settings UI calls. Each updates app state and persists via store().
function setTapToPause(value) {
  app.tapToPause = Boolean(value);
  store(LS_TAP_TO_PAUSE, app.tapToPause);
}
function setHaptics(value) {
  app.haptics = Boolean(value);
  store(LS_HAPTICS, app.haptics);
}
function setMobileTimelineZoom(value) {
  if (![1, 2, 4, 8].includes(value)) return; // allow-list; ignore anything else
  app.mobileTimelineZoom = value;
  store(LS_MOBILE_TIMELINE_ZOOM, value);
  // A zoom change is a sanctioned structural render (like the dock speed
  // cycle) — the rail's inner width AND its bins (pxWidth = railWidth *
  // zoom) both depend on it, so recompute bins before the rebuild rather
  // than leaving stale bins from the previous zoom on screen for one frame.
  recomputeMobileRailBins();
  render();
}
function markHelpSeen() {
  app.helpSeen = true;
  store(LS_HELP_SEEN, true);
}

// ── Surface stack: Settings / About / Help (Plan 02-04, MOBP-05) ───────────
// Exactly one of MOBILE_SURFACES (or none) is ever open. openMobileSurface
// is the only place that pushes a history sentinel; closeMobileSurface is
// the only place that consumes one — every close route (backdrop tap, close
// button, back gesture) funnels through it exactly once (T-02-14).

// openMobileSurface(kind, triggerEl): closes whatever's open (in memory only
// — no history.back(), since the new sentinel below replaces it), sets both
// fields, pushes exactly one sentinel, then renders. triggerEl is
// remembered so closeMobileSurface() can restore focus there (D-16) — but
// render() unconditionally clears and rebuilds the ENTIRE portrait DOM tree
// on every structural render (no per-node diffing anywhere in this app), so
// triggerEl itself will already be a detached node by the time a later
// close happens. app.mobileSurfaceOpener therefore stores triggerEl's
// data-action string (a stable identifier for "the button that opens this
// surface"), not the node — closeMobileSurface re-resolves a live element
// by that selector AFTER its own render() rebuild, rather than calling
// .focus() on a stale reference that would silently do nothing.
function openMobileSurface(kind, triggerEl) {
  if (!MOBILE_SURFACES.includes(kind)) return;
  // Pressing the control that opened a surface closes it again. Without this
  // the second press re-opened the same surface AND pushed a second history
  // sentinel, so escaping by back-gesture took as many presses as taps.
  if (app.mobileSurface === kind) {
    closeMobileSurface();
    return;
  }
  // Swapping Settings <-> About reuses the sentinel already on the stack, so
  // exactly one is outstanding while any surface is open — one back press
  // always closes, whatever route got you here.
  const alreadyOpen = app.mobileSurface !== null;
  app.mobileSurface = kind;
  app.mobileSurfaceOpener = triggerEl?.dataset?.action || null;
  if (!alreadyOpen) history.pushState({ bcfMobileSurface: kind }, "");
  render();
}

// closeMobileSurface({ fromPopstate }): a no-op when nothing is open, so a
// popstate arriving after an already-closed surface (or a stray back
// keypress) never double-fires. Consumes the sentinel with history.back()
// unless the close itself originated FROM a popstate (that navigation
// already consumed it) — this is what keeps history.length unchanged across
// every close route.
function closeMobileSurface({ fromPopstate = false } = {}) {
  if (!app.mobileSurface) return;
  const openerAction = app.mobileSurfaceOpener;
  app.mobileSurface = null;
  app.mobileSurfaceOpener = null;
  if (!fromPopstate) history.back();
  render();
  if (openerAction) {
    const opener = document.querySelector(`[data-action="${openerAction}"]`);
    if (opener) opener.focus();
  }
}

// A single module-level popstate listener closes the topmost surface when
// one is open — this is how the phone's own back gesture dismisses a
// flyout instead of leaving the app (D-16).
window.addEventListener("popstate", () => {
  if (app.mobileSurface) closeMobileSurface({ fromPopstate: true });
});

// trapMobileSurfaceFocus(surfaceEl): tears down any prior trap first
// (defensive, matching the gesture-teardown convention), then — if a
// surface is mounted — moves focus to its first focusable element and
// installs a focusin listener (redirects focus back in if it escapes) plus
// a keydown listener (wraps Tab/Shift+Tab at the first/last focusable).
// Teardown lives on `app`, not app.dom (render() resets app.dom every call).
const MOBILE_FOCUSABLE_SELECTOR = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

function mobileSurfaceFocusables(surfaceEl) {
  return [...surfaceEl.querySelectorAll(MOBILE_FOCUSABLE_SELECTOR)]
    .filter(node => !node.disabled && node.offsetParent !== null);
}

function teardownMobileSurfaceFocusTrap() {
  if (typeof app.mobileSurfaceFocusTrapTeardown === "function") {
    app.mobileSurfaceFocusTrapTeardown();
  }
  app.mobileSurfaceFocusTrapTeardown = null;
}

function trapMobileSurfaceFocus(surfaceEl) {
  teardownMobileSurfaceFocusTrap();
  if (!surfaceEl) return;
  const initial = mobileSurfaceFocusables(surfaceEl)[0];
  if (initial) initial.focus();
  const onFocusIn = event => {
    if (surfaceEl.contains(event.target)) return;
    const first = mobileSurfaceFocusables(surfaceEl)[0];
    if (first) first.focus();
  };
  const onKeyDown = event => {
    if (event.key !== "Tab") return;
    const items = mobileSurfaceFocusables(surfaceEl);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  document.addEventListener("focusin", onFocusIn);
  document.addEventListener("keydown", onKeyDown);
  app.mobileSurfaceFocusTrapTeardown = () => {
    document.removeEventListener("focusin", onFocusIn);
    document.removeEventListener("keydown", onKeyDown);
  };
}

// binRolls/binSize/panOffsetForPlayhead/mobileInnerFraction are read-only
// exposures of the SAME functions the rail's render/scrub paths call — this
// is exposure of the single implementation for test assertions, never a
// second math path (no-parallel-implementations).
window.__bcfMobile = {
  setTapToPause,
  setHaptics,
  setMobileTimelineZoom,
  markHelpSeen,
  binRolls,
  binSize,
  panOffsetForPlayhead,
  mobileInnerFraction,
  // setMode's write-side allow-list guard (T-02-12) is otherwise only
  // reachable through the Settings UI's own allow-listed buttons — exposed
  // here (like the setters above) so the guard itself can be asserted
  // directly against an out-of-allow-list value.
  setMode,
};

// Dock speed control (MOBP-02/UI-SPEC "Settings — Speed options"). Every
// rung's value is an existing option of the frozen desktop speed <select>
// ([1000, 2500, 5000, 10000, 25000, 50000, 100000]), so a speed chosen on a
// phone can never leave that control rendering blank. The rung LABEL is the
// UI-SPEC's canonical value string ("0.5"/"1"/"2"/"4" — same convention the
// prototype's own Settings speed radio group uses, design/mobile-ux/
// prototype/panels.jsx), not the display glyph; mobileSpeedButtonLabel()
// below maps "0.5" to the "½" glyph the prototype's app.jsx also renders,
// for the dock button's text only. The 4x label maps to the 25000 rung (the
// nearest existing rung at or above 4 x 5000) — this approximation is on
// the Phase B gate agenda (F-04).
const MOBILE_SPEED_RUNGS = [["0.5", 2500], ["1", 5000], ["2", 10000], ["4", 25000]];

// mobileSpeedMultiplier(): the label of the rung whose value equals the
// live app.speed, or null when the current speed came from the desktop
// control and matches no rung.
function mobileSpeedMultiplier() {
  const rung = MOBILE_SPEED_RUNGS.find(([, value]) => value === app.speed);
  return rung ? rung[0] : null;
}

// setMobileSpeedMultiplier(label): looks the label up in the allow-listed
// rung table (ignoring anything else), assigns app.speed to that rung's
// words-per-second value, persists through the SAME LS_SPEED path the
// desktop <select> uses (no second persistence route), and renders — a
// control change is a sanctioned structural render, unlike a gesture.
function setMobileSpeedMultiplier(label) {
  const rung = MOBILE_SPEED_RUNGS.find(([rungLabel]) => rungLabel === label);
  if (!rung) return;
  app.speed = rung[1];
  store(LS_SPEED, app.speed);
  render();
}

// Dock speed button's display text: "{glyph}×" when the current speed
// matches a rung (the "0.5" rung reads "½", matching the prototype's own
// speedLabel convention), else a raw words/sec readout for an
// out-of-rung speed set from the desktop control.
function mobileSpeedButtonLabel() {
  const rungLabel = mobileSpeedMultiplier();
  if (rungLabel == null) return `${formatWords(app.speed)}w/s`;
  return `${rungLabel === "0.5" ? "½" : rungLabel}×`;
}

// Diagnostic counter mirroring recordStructuralRender(): increments only when
// the test harness pre-injected window.__bcfGestureStats; production no-op.
function recordGestureEvent(kind) {
  const stats = window.__bcfGestureStats;
  if (stats && typeof stats[kind] === "number") {
    stats[kind] += 1;
  }
}

// Per-render gesture attach lifecycle (D-07): called only from inside the
// render pass, after the probe element is mounted — never from the matchMedia
// handler, and no gesture callback ever triggers a structural render. The
// diagnostic callbacks ARE the Phase 1 attach point; Phase 2 renderers pass
// production callbacks through this exact convention. Teardown lives on
// `app` (NOT app.dom, which render() resets) so it survives to be invoked
// defensively before re-attach.
function attachMobileGestureProbes() {
  if (typeof app.mobileGestureTeardown === "function") {
    app.mobileGestureTeardown();
    app.mobileGestureTeardown = null;
  }
  const probe = document.querySelector(".mobile-gesture-probe");
  if (!probe || typeof window.attachSkyGestures !== "function") return;
  app.mobileGestureTeardown = window.attachSkyGestures(probe, {
    onTap: () => recordGestureEvent("taps"),
    onDoubleTap: () => recordGestureEvent("doubleTaps"),
    onSwipeStep: () => recordGestureEvent("swipeSteps"),
    onSwipeEnd: () => recordGestureEvent("swipeEnds"),
  });
  recordGestureEvent("attaches");
}

// ── Portrait C layout (Phase 2, D-12/D-13/D-17/D-18) ────────────────────────
// Real sky + always-visible mini-rail dock. Duplicates markup over the
// shared model (plan §7) — never edits the frozen desktop renderers it
// calls (renderViewportFrame, renderSkyCamera, playthroughFrameState).

// Verbatim port of prototype/scrubber.jsx panOffsetForPlayhead (algorithm
// unchanged): the auto-pan transform that keeps the playhead visible once
// the mini-rail's zoomed-in content would otherwise scroll it off-screen.
function panOffsetForPlayhead(playheadPctRaw, zoom) {
  if (zoom <= 1) return 0;
  const wantedPct = playheadPctRaw * zoom - 50;
  const maxPct = (zoom - 1) * 100;
  return Math.max(0, Math.min(maxPct, wantedPct));
}

// Verbatim port of prototype/scrubber.jsx fractionFromPointer (algorithm
// unchanged): resolves a fraction of the INNER (zoomed) content from a raw
// pointer event against the rail element's bounding box.
function fractionFromPointer(el, e, zoom, panPct) {
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0) return 0;
  const xFracView = (e.clientX - rect.left) / rect.width;
  const innerFrac = (xFracView + panPct / 100) / zoom;
  return Math.max(0, Math.min(1, innerFrac));
}

// The single viewport-fraction -> inner-content-fraction conversion shared
// by the rail's onScrub callback (attachRailScrub already resolves the
// viewport fraction from the pointer event) and later plans. Never
// duplicate this math a second time (no-parallel-implementations).
function mobileInnerFraction(viewportFraction, zoom, panPct) {
  return Math.max(0, Math.min(1, (viewportFraction + panPct / 100) / zoom));
}

// ── Cluster binning (MOBP-04, 02-03-PLAN.md) ────────────────────────────────
// Verbatim port of design/mobile-ux/prototype/scrubber.jsx's binRolls/
// finalizeBin/binSize (algorithm unchanged) — the ONLY change is the field
// accessor: the live schema is roll.word_position/roll.outcome, not the
// prototype's camelCase wordPosition. Never invent a second cluster-merge
// implementation alongside this one.
const MIN_DOT_SPACING_PX = 5;

function binRolls(rolls, totalWords, pxWidth, minPx = MIN_DOT_SPACING_PX) {
  if (!rolls.length || pxWidth <= 0) return [];
  const minWords = (minPx / pxWidth) * totalWords;
  const bins = [];
  let cur = null;
  for (const r of rolls) {
    if (!cur || r.word_position - cur.firstWord > minWords) {
      if (cur) bins.push(finalizeBin(cur));
      cur = { firstWord: r.word_position, rolls: [r], outcomes: {} };
      cur.outcomes[r.outcome] = 1;
    } else {
      cur.rolls.push(r);
      cur.outcomes[r.outcome] = (cur.outcomes[r.outcome] || 0) + 1;
    }
  }
  if (cur) bins.push(finalizeBin(cur));
  return bins;
}

function finalizeBin(bin) {
  // Midpoint word for visual placement; carry the dominant outcome.
  const last = bin.rolls[bin.rolls.length - 1];
  bin.midWord = (bin.firstWord + last.word_position) / 2;
  const e = bin.outcomes;
  if ((e.hit || 0) >= (e.miss || 0) && (e.hit || 0) >= (e.unknown || 0)) bin.dominant = "hit";
  else if ((e.miss || 0) >= (e.unknown || 0)) bin.dominant = "miss";
  else bin.dominant = "unknown";
  return bin;
}

function binSize(bin) {
  if (bin.rolls.length === 1) return 6;
  return Math.min(14, 5 + Math.round(Math.sqrt(bin.rolls.length) * 1.6));
}

// recomputeMobileRailBins(): reads the rail's current pixel width
// (app.mobileRailWidth, kept current by the ResizeObserver installed in
// attachMobilePortraitGestures) and caches the resulting bins on
// app.mobileRailBins. Call ONLY from: the structural render (renderMobile-
// Portrait), renderMobileLandscape() (Phase 3 — the fourth sanctioned call
// site, same discipline), the zoom setter (setMobileTimelineZoom), and the
// rail's ResizeObserver callback — never from updateMobilePortraitFrame() or
// updateMobileLandscapeFrame() (D-18: bins recompute on render/zoom/resize,
// never on a playback frame).
function recomputeMobileRailBins() {
  if (!app.data) {
    app.mobileRailBins = [];
    return;
  }
  const story = app.data.story;
  app.mobileRailBins = binRolls(
    story.rolls,
    story.total_words || 1,
    app.mobileRailWidth * app.mobileTimelineZoom,
  );
}

// mobileScrubWidthDefaultForLayout() (Phase 3, RESEARCH Pitfall 6/CONTEXT
// A2): app.mobileRailWidth and app.mobileRailBins stay SHARED across both
// mobile layouts — exactly one layout is ever mounted, so a second pair of
// fields would just be dead weight. But a stale portrait measurement (the
// 350 default, or a prior real measurement) must never mis-bin the
// narrower, floating landscape cinema-scrub track for one frame right after
// a rotation, and vice versa. app.mobileRailWidthLayout records which
// layout's ResizeObserver last wrote a real measurement; when it doesn't
// match the CURRENT layout, this returns a layout-appropriate default
// instead of the other layout's stale number (200 for landscape — the
// prototype's own cinema-scrub fallback; 350 for portrait, unchanged from
// Phase 2). Once a layout's ResizeObserver measures and writes
// app.mobileRailWidthLayout = app.layoutMode, this returns the live
// measurement unchanged until the layout changes again.
function mobileScrubWidthDefaultForLayout() {
  if (app.mobileRailWidthLayout === app.layoutMode) return app.mobileRailWidth;
  return app.layoutMode === "landscape" ? 200 : 350;
}

// renderMobileRailBinEl(bin, total): a single `.mobile-roll-bin` marker,
// colour-keyed on the bin's dominant outcome, with a `.count` child only
// once the bin holds more than one roll AND is large enough to hold the
// digits (prototype's `size >= 10` rule).
function renderMobileRailBinEl(bin, total) {
  const size = binSize(bin);
  const isMulti = bin.rolls.length > 1;
  return el("div", {
    class: `mobile-roll-bin ${bin.dominant}`,
    style: { left: `${(bin.midWord / total) * 100}%`, width: `${size}px`, height: `${size}px` },
  }, isMulti && size >= 10 ? el("span", { class: "count", text: String(bin.rolls.length) }) : null);
}

// renderMobileRailRollsLaneChildren(): the rolls lane's full child set — POV
// bands, cached cluster bins (app.mobileRailBins, never recomputed here),
// and the active roll's own marker drawn last so it always paints above the
// bins. Shared by the initial structural build (renderMobileScrubber) and
// the rail ResizeObserver's partial rebuild — never a third copy of this
// markup.
function renderMobileRailRollsLaneChildren() {
  const story = app.data.story;
  const total = story.total_words || 1;
  const bands = story.chapters.map(chapter => el("div", {
    class: `mobile-pov-band ${chapter.pov === "Joe" ? "mc" : chapter.pov === "Aisha" ? "aisha" : "other"}`,
    style: {
      left: `${(chapter.word_start / total) * 100}%`,
      width: `${Math.max(0.02, ((chapter.word_end - chapter.word_start) / total) * 100)}%`,
    },
  }));
  const bins = (app.mobileRailBins || []).map(bin => renderMobileRailBinEl(bin, total));
  const activeRoll = lastRollAtWord(app.wordPos);
  const activeDot = activeRoll
    ? el("div", {
      class: "mobile-roll-dot active",
      style: { left: `${(activeRoll.word_position / total) * 100}%` },
    })
    : null;
  return [...bands, ...bins, activeDot].filter(Boolean);
}

// maybeAutoOpenHelp(): the first-run welcome (MOBP-05). Runs at the TOP of
// renderMobilePortrait(), before any node is built, so the surface it opens
// is reflected in THIS SAME render pass — it must never call
// openMobileSurface() or render() itself (either would recurse into the
// render pass currently building this exact frame, breaking both the
// portrait-crossing render count and the attach-count assertions the
// plumbing/desktop-smoke suites already pin down).
function maybeAutoOpenHelp() {
  if (!app.data || app.helpSeen || app.mobileHelpAutoOpened) return;
  app.mobileHelpAutoOpened = true;
  app.mobileSurface = "help";
  app.mobileSurfaceOpener = null;
  history.pushState({ bcfMobileSurface: "help" }, "");
}

// renderMobileSkyRegion(frame) (Phase 3, D-35): the sky markup common to
// BOTH mobile layouts — viewport frame corners, the cinematic camera layer,
// the focal label, the tap hint, and the Settings/About/Help mount points.
// Extracted verbatim from renderMobilePortrait()'s former inline sky block
// so it exists in exactly ONE place; each caller wraps the returned array in
// its own `.mobile-sky mobile-sky-surface` container with layout-specific
// sizing (portrait: 60% height stack; landscape: ~75% width flex sibling of
// the rail). Never duplicate this block a second time — D-35's justification
// is that duplicating would mean fixing the tap hint, focal label and camera
// layer twice.
function renderMobileSkyRegion(frame) {
  return [
    renderViewportFrame(),
    el("div", { class: "mobile-sky-camera-layer" },
      frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,
    ),
    renderMobileFocalLabel(frame),
    renderMobileSkyTapHint(),
    // D-19: the Help overlay is scoped to the sky region (not the whole
    // mobile surface) so the dock/rail — including the play button a
    // first-run empty-storage load must still be able to click — stays
    // visible and operable while it's open.
    app.mobileSurface === "help" ? renderMobileHelpOverlay() : null,
    // Settings/About mount here too, under the same D-19 rationale as Help.
    // They previously mounted as the last child of .mobile-app with a fixed
    // `bottom: 152px`, which assumed the prototype's shorter dock: on a real
    // iPhone (440x760) the dock is 304px tall and its transport row sits
    // 112-166px from the bottom, so a 152px anchor landed inside that band
    // and the buttons — z-index 10 against the flyout's 9 — painted through
    // the panel. Scoping the surfaces to the sky removes the collision
    // structurally instead of re-tuning the constant, and keeps the dock
    // operable while a surface is open (the backdrop no longer covers it).
    // D-33 reuses this same scoping for landscape's Settings/About.
    renderMobileSurface(),
  ];
}

// renderMobilePortrait(): the D-12 portrait arm of render(). Root
// `.mobile-app` holds the top chip cluster, the real sky (D-13 — never the
// prototype's procedural placeholder) with its cinematic camera and focal
// label, and the dock (transport row + mini-rail + hint row).
function renderMobilePortrait() {
  maybeAutoOpenHelp();
  const frame = playthroughFrameState();
  // Phase 3/RESEARCH Pitfall 6: guard against a stale landscape measurement
  // (or the other layout's default) surviving a rotation into portrait — see
  // mobileScrubWidthDefaultForLayout(). A no-op once a portrait
  // ResizeObserver measurement has already landed this session.
  app.mobileRailWidth = mobileScrubWidthDefaultForLayout();
  // Structural render is one of the four sanctioned call sites for bin
  // recomputation (D-18) — never inside updateMobilePortraitFrame().
  recomputeMobileRailBins();
  return el("div", { class: "mobile-app" },
    renderMobileTopCluster(),
    el("div", { class: "mobile-sky mobile-sky-surface" },
      ...renderMobileSkyRegion(frame),
    ),
    el("div", { class: "mobile-dock" },
      el("div", { class: "mobile-dock-transport" },
        el("button", {
          class: "mobile-fab-play",
          type: "button",
          "data-action": "toggle-playback",
          "aria-label": app.playing ? "Pause" : "Play",
          title: app.playing ? "Pause (space)" : "Play (space)",
          text: app.playing ? "❚❚" : "▶",
        }),
        el("div", { class: "mobile-dock-now" },
          el("div", { class: "mobile-dock-meta readout-meta", text: mobileDockMetaText() }),
          el("div", { class: "mobile-dock-title", text: frame.chapter?.title || "—" }),
        ),
        el("button", {
          class: "mobile-icon-btn compact",
          type: "button",
          "data-action": "mobile-cycle-speed",
          "aria-label": "Playback speed",
          title: "Cycle playback speed",
          text: mobileSpeedButtonLabel(),
        }),
        el("button", {
          class: `mobile-icon-btn compact${app.mobileSurface === "settings" ? " is-active" : ""}`,
          type: "button",
          "data-action": "mobile-open-settings",
          "aria-label": "Settings",
          title: "Settings",
        }, mobileGearIcon()),
        el("button", {
          class: `mobile-icon-btn compact${app.mobileSurface === "info" ? " is-active" : ""}`,
          type: "button",
          "data-action": "mobile-open-info",
          "aria-label": "About",
          title: "About this visualization",
        }, mobileInfoIcon()),
      ),
      renderMobileScrubber(),
      renderMobileHintRow(),
    ),
    renderMobileSurfaceBackdrop(),
  );
}

// renderMobileSurface(): the exclusive Settings/About stack — returns null
// when neither is open, or the backdrop + flyout pair when one is. Mounted
// inside .mobile-sky (D-19), the same containing block as the Help overlay,
// so a flyout can never geometrically collide with the dock and the backdrop
// never covers the transport controls.
function renderMobileSurface() {
  if (app.mobileSurface === "settings") return renderMobileSettingsFlyout();
  if (app.mobileSurface === "info") return renderMobileInfoFlyout();
  return null;
}

// The dismiss backdrop stays a child of .mobile-app, NOT of .mobile-sky. It
// has to span the whole surface: scoping it to the sky shrank the
// tap-outside-to-close target to a thin strip and left the dock — the
// natural place to tap next, right where the opening button is — with no
// backdrop at all, so a flyout became impossible to dismiss by tapping out.
// Only the panel itself needs to live in the sky (to avoid the dock overlap).
function renderMobileSurfaceBackdrop() {
  if (!app.mobileSurface || app.mobileSurface === "help") return null;
  return el("div", { class: "mobile-flyout-backdrop", "data-action": "mobile-close-surface" });
}

// mobileSeg(value, options, onSelect): a `.mobile-seg` segmented control —
// options is an array of [value, label] pairs. Shared by every Settings
// group whose options commit through a plain setter call (View mode, Speed,
// Timeline zoom); the On-roll group instead wires its buttons through the
// existing set-on-roll-behavior data-action delegation directly (see
// renderMobileSettingsFlyout) so it reuses that handler's own allow-list and
// running-cinematic-clear logic rather than a second setter path.
function mobileSeg(value, options, onSelect) {
  return el("div", { class: "mobile-seg", role: "group" },
    options.map(([v, label]) => el("button", {
      type: "button",
      class: value === v ? "is-active" : "",
      "aria-pressed": value === v,
      onClick: () => onSelect(v),
      text: label,
    })),
  );
}

function mobileSettingsGroup(label, ...children) {
  return el("div", { class: "mobile-group" },
    el("div", { class: "mobile-group-label", text: label }),
    ...children,
  );
}

function mobileComfortRow(label, value, onToggle) {
  return el("div", { class: "mobile-row" },
    el("span", { text: label }),
    el("button", { type: "button", class: "mobile-row-val", onClick: onToggle, text: value ? "On" : "Off" }),
  );
}

// renderMobileSettingsFlyout(): every control routes through an existing
// shared setter/delegated action — never a direct localStorage write
// (T-02-12). Group order is locked (MOBP-05 ordering edge): View mode, On
// roll, Speed, Timeline zoom, Comfort.
function renderMobileSettingsFlyout() {
  return el("div", { class: "mobile-flyout", role: "dialog", "aria-label": "Settings" },
    el("h4", { text: "Settings" }),
    el("div", { class: "mobile-flyout-divider" }),
    mobileSettingsGroup(
      "View mode",
      mobileSeg(
        app.mode,
        [["playthrough", "Playthrough"], ["detail", "Details"]],
        setMode,
      ),
    ),
    mobileSettingsGroup(
      "On roll",
      el("div", { class: "mobile-seg", role: "group" },
        [["cinematic", "Cinematic"], ["quick", "Skip"], ["pause", "Pause"]].map(([v, label]) => el("button", {
          type: "button",
          class: app.onRollBehavior === v ? "is-active" : "",
          "aria-pressed": app.onRollBehavior === v,
          "data-action": "set-on-roll-behavior",
          "data-on-roll-behavior": v,
          text: label,
        })),
      ),
    ),
    mobileSettingsGroup(
      "Speed",
      mobileSeg(
        mobileSpeedMultiplier(),
        [["0.5", "½×"], ["1", "1×"], ["2", "2×"], ["4", "4×"]],
        setMobileSpeedMultiplier,
      ),
    ),
    mobileSettingsGroup(
      "Timeline zoom",
      mobileSeg(
        String(app.mobileTimelineZoom),
        [["1", "1×"], ["2", "2×"], ["4", "4×"], ["8", "8×"]],
        value => window.__bcfMobile.setMobileTimelineZoom(Number(value)),
      ),
    ),
    mobileSettingsGroup(
      "Comfort",
      mobileComfortRow("Tap sky to pause", app.tapToPause, () => { setTapToPause(!app.tapToPause); render(); }),
      mobileComfortRow("Haptics", app.haptics, () => { setHaptics(!app.haptics); render(); }),
    ),
  );
}

// renderMobileInfoFlyout(): story credit, the live STORY_LINKS constant
// (never the prototype's hard-coded URLs — T-02-13/prohibition), and live
// dataset counts read straight off app.data.story.
function renderMobileInfoFlyout() {
  const story = app.data.story;
  return el("div", { class: "mobile-flyout", role: "dialog", "aria-label": "About" },
    el("h4", { text: "About this visualization" }),
    el("h2", { text: "Brockton's Celestial Forge" }),
    el("div", { class: "mobile-flyout-credit" },
      "Worm × Jumpchain crossover by ", el("b", { text: "LordRoustabout" }),
    ),
    el("div", { class: "mobile-flyout-divider" }),
    mobileSettingsGroup(
      "Read the source",
      el("div", { class: "mobile-source-row" },
        STORY_LINKS.map(link => el("a", {
          href: link.href,
          target: "_blank",
          rel: "noopener noreferrer",
          text: `${link.label} ↗`,
        })),
      ),
    ),
    mobileSettingsGroup(
      "Dataset",
      el("div", { class: "mobile-flyout-dataset" },
        el("div", { text: `${story.rolls.length} rolls · ${story.chapters.length} chapters` }),
        el("div", { class: "muted", text: `${formatWords(story.total_words)} words` }),
      ),
    ),
    el("button", {
      type: "button",
      class: "mobile-full-btn",
      onClick: event => openMobileSurface("help", event.currentTarget),
    }, el("span", { text: "Gestures & help" }), el("span", { text: "↗" })),
  );
}

// The seven locked "How to play" gesture rows (UI-SPEC Copywriting
// Contract) — icon glyph + bold lead-in + description, verbatim.
const MOBILE_HELP_GESTURE_ROWS = [
  ["👆", "Tap sky", "pause / resume."],
  ["👆👆", "Double-tap sky", "snap to live edge."],
  ["👈👉", "Swipe sky", "scrub by roll (haptic on each)."],
  ["↔", "Drag scrubber", "direct scrub by word."],
  ["🔄", "Rotate", "switches portrait ↔ landscape; state persists."],
  ["⚙", "Settings", "speed, on-roll behavior, comfort."],
  ["ⓘ", "About", "story credits, source links, gestures."],
];

// renderMobileHelpOverlay(): mounted inside .mobile-sky (D-19), never a
// full-portrait overlay. Both the close button and the CTA dismiss through
// the same markHelpSeen() + closeMobileSurface() pair.
function renderMobileHelpOverlay() {
  const dismiss = () => { markHelpSeen(); closeMobileSurface(); };
  return el("div", { class: "mobile-help-overlay", role: "dialog", "aria-label": "Help" },
    el("header", {},
      el("div", {},
        el("div", { class: "label", text: "Help & credits" }),
        el("h1", { text: "Reading on mobile" }),
      ),
      el("button", { type: "button", class: "mobile-help-close", "aria-label": "Close", onClick: dismiss, text: "×" }),
    ),
    // The body scrolls; the header and the CTA below it do not. Scoped to the
    // sky region (D-19), the content is taller than the available height on
    // every phone-sized viewport, so a CTA in normal flow scrolls out of sight
    // and first-run users cannot see how to dismiss.
    el("div", { class: "mobile-help-body" },
    el("div", { class: "mobile-credit-block" },
      el("div", { class: "title", text: "Brockton's Celestial Forge" }),
      el("div", { class: "by" }, "by ", el("b", { text: "LordRoustabout" }), " · Worm × Jumpchain"),
      el("div", { class: "mobile-source-row" },
        STORY_LINKS.map(link => el("a", {
          href: link.href,
          target: "_blank",
          rel: "noopener noreferrer",
          text: `${link.label} ↗`,
        })),
      ),
    ),
    el("h3", { text: "How to play" }),
    el("div", { class: "mobile-help-gestures" },
      MOBILE_HELP_GESTURE_ROWS.map(([icon, lead, rest]) => [
        el("span", { class: "ico", text: icon }),
        el("span", {}, el("b", { text: lead }), ` — ${rest}`),
      ]),
    ),
    el("h3", { text: "Heads-up" }),
    el("div", { class: "mobile-help-headsup" },
      "Your bookmark, speed, and preferences survive a refresh — pick up where you left off. Haptics and tap-to-pause can be disabled in Settings → Comfort.",
    ),
    ),
    el("button", { type: "button", class: "mobile-got-it", onClick: dismiss, text: "Got it — read on" }),
  );
}

function mobileDockMetaText() {
  const total = app.data.story.total_words || 1;
  return `${formatWords(app.wordPos)} / ${formatWords(total)} words · ${Math.round((app.wordPos / total) * 100)}%`;
}

// The top chip cluster (MOBP-01). Absolutely positioned 12px inset from the
// sky's top/left/right (its containing block is `.mobile-app`, which the
// prototype's `.app` equivalent gives `position: relative`). The 44x44 help
// button (Plan 02-04) fills the slot Plan 02-01 reserved as an empty
// spacer, at the same footprint, so the layout never shifted when it
// landed.
function renderMobileTopCluster() {
  const roll = lastRollAtWord(app.wordPos);
  return el("div", { class: "mobile-top-cluster" },
    el("div", { class: "mobile-chip-row" },
      el("div", { class: "mobile-chip", text: mobileChChipText() }),
      roll ? el("div", { class: "mobile-chip amber", text: mobileAmberChipText(roll) }) : null,
    ),
    el("button", {
      class: `mobile-icon-btn${app.mobileSurface === "help" ? " is-active" : ""}`,
      type: "button",
      "data-action": "mobile-open-help",
      "aria-label": "Help",
      title: "Gestures & help",
    }, mobileHelpIcon()),
  );
}

function mobileChChipText() {
  // Defensive optional-chain: chapterAtWord() returns undefined when
  // app.data.story.chapters is empty (UI-SPEC partial-data row) — never
  // let that surface as a literal "undefined" in the chip.
  const chNum = chapterAtWord(app.wordPos)?.chapter_num ?? "—";
  // Phase 3 UI-SPEC Typography table: landscape's top chip omits the word
  // count segment (a real, intentional content difference from portrait's
  // `CH {num} · {words}w`, not a truncation bug — prototype layouts.jsx:69).
  // Branching inside this shared helper (rather than a flag passed from
  // renderMobileTopCluster()) means updateMobileTopClusterFrame() picks the
  // correct variant up for free in both layouts.
  if (app.layoutMode === "landscape") return `CH ${chNum}`;
  return `CH ${chNum} · ${formatWords(app.wordPos)}w`;
}

function mobileAmberChipText(roll) {
  return `◢ ${roll.roll_label || "R—"}`;
}

// The sky's focal label (MOBP-01/UI-SPEC Display role). Renders only while
// the cinematic is firing on a real roll — structurally absent otherwise,
// never a blanked placeholder.
function renderMobileFocalLabel(frame) {
  if (!(frame.firing && frame.lastRoll)) return null;
  const roll = frame.lastRoll;
  const isHit = roll.outcome === "hit";
  const kicker = roll.constellation || "—";
  let name;
  if (isHit) {
    const principal = paidRollPerks(roll)[0] ?? (roll.free_perks || [])[0];
    name = perkDisplayLabel(principal) || roll.rolled_perk_name || roll.constellation || "—";
  } else {
    name = "Miss";
  }
  const sub = isHit
    ? `${rollTotalCost(roll)} CP · ch ${roll.chapter_num}`
    : `miss ${roll.miss_cost_estimate ?? "?"} · ch ${roll.chapter_num}`;
  return el("div", { class: "mobile-focal-label" },
    el("div", { class: "kicker", text: kicker }),
    el("div", { class: "name", text: name }),
    el("div", { class: "sub", text: sub }),
  );
}

// First-run tap-sky-to-pause affordance (UI-SPEC Copywriting Contract).
// Mounts at most once per page session — app.mobileSkyHintShown is set the
// moment it mounts, so a later structural re-render (e.g. a speed-cycle
// click) never remounts it. Absent entirely when tap-to-pause is off, since
// there's nothing to teach the reader about tapping the sky in that case.
function renderMobileSkyTapHint() {
  if (!app.tapToPause || app.mobileSkyHintShown) return null;
  app.mobileSkyHintShown = true;
  return el("div", { class: "mobile-sky-tap-hint", "aria-hidden": "true", text: "tap sky to pause" });
}

// Hint row (locked copy, UI-SPEC Copywriting Contract). Left span is
// static; the right span's zoom segment is omitted entirely at 1x.
function renderMobileHintRow() {
  const chapter = chapterAtWord(app.wordPos);
  return el("div", { class: "mobile-hint-row" },
    el("span", { text: "tap rail → jump · drag → scrub" }),
    el("span", { text: mobileHintRowRightText(chapter) }),
  );
}

function mobileHintRowRightText(chapter) {
  const zoomPart = app.mobileTimelineZoom > 1 ? `${app.mobileTimelineZoom}× zoom · ` : "";
  return `${zoomPart}${chapter?.pov || "Joe"} POV`;
}

// renderMobileScrubber(): the mini-rail. Rolls lane is cluster-binned
// (MOBP-04) via renderMobileRailRollsLaneChildren(), read from the LIVE
// schema (word_position/outcome/word_start/word_end/chapter_num/pov), never
// the prototype's camelCase names.
function renderMobileScrubber() {
  const story = app.data.story;
  const total = story.total_words || 1;
  const playheadPctRaw = (app.wordPos / total) * 100;
  const zoom = app.mobileTimelineZoom;
  const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
  return el("div", { class: "mobile-rail mobile-rail-surface" },
    el("div", {
      class: "mobile-rail-inner",
      style: { width: `${zoom * 100}%`, transform: `translateX(-${panPct}%)` },
    },
      el("div", { class: "mobile-lane mobile-lane-chapters" },
        story.chapters.map(chapter => el("div", {
          class: `mobile-ch-tick ${Number(chapter.chapter_num) % 10 === 0 || chapter.chapter_num === "1" ? "major" : ""}`,
          style: { left: `${(chapter.word_start / total) * 100}%` },
        })),
      ),
      el("div", { class: "mobile-lane mobile-lane-rolls" },
        renderMobileRailRollsLaneChildren(),
      ),
      el("div", { class: "mobile-playhead", style: { left: `${playheadPctRaw}%` } }),
    ),
  );
}

// updateMobileSkyCameraFrame(frame) (Phase 3): the sky camera key-diff
// shared by BOTH mobile layouts' incremental tiers (D-35 — the shared sky
// region means the shared sky-camera update logic lives once too, never
// pasted twice). Identical logic, identical app.frameKeys.skyCamera field,
// previously inlined in updateMobilePortraitFrame() only.
function updateMobileSkyCameraFrame(frame) {
  const skyCameraKey = frame.scene ? `scene:${frame.lastRoll?.uid || ""}` : "none";
  if (app.dom.mobileSkyCameraLayer && (frame.scene || app.frameKeys.skyCamera !== skyCameraKey)) {
    app.dom.mobileSkyCameraLayer.replaceChildren(
      ...(frame.scene ? [renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT)] : []),
    );
    app.frameKeys.skyCamera = skyCameraKey;
  }
}

// updateMobilePortraitFrame(): the D-18 incremental tier for portrait,
// mirroring updatePlaythroughFrame's key-diff shape. Mutates text/style
// only — never rebuilds the rail's lanes here (that only happens on
// structural render, zoom change, or rail resize — 02-03-PLAN.md).
function updateMobilePortraitFrame() {
  const frame = playthroughFrameState();
  updateMobileSkyCameraFrame(frame);
  if (app.dom.mobileFab) {
    const label = app.playing ? "Pause" : "Play";
    app.dom.mobileFab.setAttribute("aria-label", label);
    app.dom.mobileFab.title = `${label} (space)`;
    app.dom.mobileFab.textContent = app.playing ? "❚❚" : "▶";
  }
  if (app.dom.mobileDockMeta) app.dom.mobileDockMeta.textContent = mobileDockMetaText();
  if (app.dom.mobileDockTitle) app.dom.mobileDockTitle.textContent = frame.chapter?.title || "—";

  updateMobileTopClusterFrame();
  updateMobileFocalLabelFrame(frame);
  updateMobileHintRowFrame(frame);
  updateMobileActiveDotFrame();

  const total = app.data.story.total_words || 1;
  const playheadPctRaw = (app.wordPos / total) * 100;
  if (app.dom.mobilePlayhead) app.dom.mobilePlayhead.style.left = `${playheadPctRaw}%`;
  if (app.dom.mobileRailInner) {
    const panPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
    app.dom.mobileRailInner.style.transform = `translateX(-${panPct}%)`;
  }
}

// The active roll's own marker (MOBP-04) is a style.left write keyed on the
// active roll's uid — moving it as playback/scrub advances never rebuilds
// the rolls lane (the bins stay untouched, D-18). A presence change (no
// active roll yet <-> an active roll now) is the same append/remove-once
// pattern as updateMobileFocalLabelFrame, not a lane rebuild.
function updateMobileActiveDotFrame() {
  const rollsLane = app.dom.mobileRailRollsLane;
  if (!rollsLane) return;
  const total = app.data.story.total_words || 1;
  const activeRoll = lastRollAtWord(app.wordPos);
  const key = activeRoll ? String(activeRoll.uid) : "none";
  const pct = activeRoll ? (activeRoll.word_position / total) * 100 : 0;
  if (app.frameKeys.mobileActiveDot !== key) {
    if (app.dom.mobileActiveDot) app.dom.mobileActiveDot.remove();
    const next = activeRoll ? el("div", { class: "mobile-roll-dot active", style: { left: `${pct}%` } }) : null;
    if (next) rollsLane.appendChild(next);
    app.dom.mobileActiveDot = next;
    app.frameKeys.mobileActiveDot = key;
  } else if (app.dom.mobileActiveDot) {
    app.dom.mobileActiveDot.style.left = `${pct}%`;
  }
}

// The CH chip's word count updates every frame; the amber roll chip is a
// structural presence change keyed on the active roll's uid (or "none") —
// replaceChildren fires only when that key changes, never every frame.
function updateMobileTopClusterFrame() {
  const chipRow = app.dom.mobileChipRow;
  if (!chipRow) return;
  const roll = lastRollAtWord(app.wordPos);
  const key = roll ? String(roll.uid) : "none";
  if (app.frameKeys.mobileChip !== key) {
    chipRow.replaceChildren(
      el("div", { class: "mobile-chip", text: mobileChChipText() }),
      roll ? el("div", { class: "mobile-chip amber", text: mobileAmberChipText(roll) }) : null,
    );
    app.frameKeys.mobileChip = key;
  } else if (chipRow.firstElementChild) {
    chipRow.firstElementChild.textContent = mobileChChipText();
  }
}

// The focal label is a structural presence change keyed on firing + roll
// uid (or "none") — appended/removed from the sky only when that key
// changes, never rebuilt every frame.
function updateMobileFocalLabelFrame(frame) {
  const sky = app.dom.mobileSky;
  if (!sky) return;
  const active = frame.firing && frame.lastRoll;
  const key = active ? String(frame.lastRoll.uid) : "none";
  if (app.frameKeys.mobileFocal === key) return;
  if (app.dom.mobileFocalLabel) app.dom.mobileFocalLabel.remove();
  const next = active ? renderMobileFocalLabel(frame) : null;
  if (next) sky.appendChild(next);
  app.dom.mobileFocalLabel = next;
  app.frameKeys.mobileFocal = key;
}

// Hint row: the left span is static; only the right span's zoom/POV text
// depends on scrubber position, so only it needs an every-frame textContent
// write.
function updateMobileHintRowFrame(frame) {
  const hintRow = app.dom.mobileHintRow;
  if (!hintRow) return;
  const rightSpan = hintRow.lastElementChild;
  if (rightSpan) rightSpan.textContent = mobileHintRowRightText(frame.chapter);
}

// ── Landscape layout (Phase 3, D-20..D-36) ──────────────────────────────
// Retires the D-12 interim landscape fallback (renderAppShell()). Sky at
// ~75% width (renderMobileSkyRegion, D-35 — shared with portrait) beside a
// 224px right rail (field log over a Settings/About control dock), wired
// through the SAME render -> cache-refs -> incremental-update tier portrait
// uses (D-18). The field log's ONLY data call is recentRolls(wordPos, count)
// (D-24) — never renderNarrativeReadout/renderRecentRolls, which are §0.2
// frozen and carry desktop sizing/scroll assumptions.

// mobileFieldLogRows(): the D-24 model seam, read once per structural/
// incremental pass. recentRolls() returns NEWEST-FIRST, so `live` (the most
// recent roll at or before the playhead) is element 0; `recent` slices it
// off the head (the prototype's own de-dup — the live roll never appears
// twice) so the field-log list holds only the OLDER of the up-to-6 rows.
function mobileFieldLogRows() {
  const rows = recentRolls(app.wordPos, 6);
  const live = rows.length ? rows[0] : null;
  const recent = rows.slice(live ? 1 : 0);
  const total = app.data.story.rolls.length;
  const idx = live ? app.data.story.rolls.indexOf(live) : -1;
  return { live, recent, idx, total };
}

// mobileFieldLogPrincipalName(roll): the SAME principal-perk expression
// renderMobileFocalLabel() uses for a hit roll, generalized with the same
// fallback chain for a miss/unknown roll (whose purchased_perks/free_perks
// are empty, so this falls straight through to roll.constellation, then an
// em-dash) — never a second perk-name-resolution implementation.
function mobileFieldLogPrincipalName(roll) {
  const principal = paidRollPerks(roll)[0] ?? (roll.free_perks || [])[0];
  return perkDisplayLabel(principal) || roll.rolled_perk_name || roll.constellation || "—";
}

// mobileFieldLogQuoteText(roll)/mobileTruncate(s, n) (D-27): the live-roll
// card's truncated evidence quote. mobileFieldLogQuoteText reads the first
// evidence quote's `text` field (confirmed against derive_roll_facts.py's
// _evidence_quotes payload shape) or "" when absent; mobileTruncate mirrors
// the prototype's own truncate(s, n) helper verbatim.
function mobileFieldLogQuoteText(roll) {
  return roll.evidence_quotes?.[0]?.text || "";
}

function mobileTruncate(s, n) {
  if (s.length <= n) return s;
  return `${s.slice(0, n - 1).trim()}…`;
}

// mobileFieldLogSubChildren(roll): the live card's `.sub` node children —
// jump, a middle-dot separator only when BOTH a jump and a quote exist, and
// the truncated quote wrapped in straight double quotes inside an `em` node.
// Every text fragment flows through el()'s `text` prop (textContent), never
// string-concatenated markup (T-03-01) — a quote containing tag-looking
// characters renders as literal characters, never parsed HTML.
function mobileFieldLogSubChildren(roll) {
  const quote = mobileFieldLogQuoteText(roll);
  const truncated = quote ? mobileTruncate(quote, 100) : "";
  const children = [];
  if (roll.jump) children.push(roll.jump);
  if (roll.jump && truncated) children.push(" · ");
  if (truncated) children.push(el("em", { text: `"${truncated}"` }));
  return children;
}

// renderMobileFieldLogChildren(rows): the field-log list's full child set —
// the live-roll card first (structurally ABSENT, never a blanked
// placeholder, when no roll has fired at or before the playhead), then one
// `.mobile-field-log-entry` per row in `recent`. Shared by the initial
// structural build (renderMobileFieldLog) and the incremental update
// (updateMobileFieldLogFrame) — never a third copy of this markup.
function renderMobileFieldLogChildren(rows) {
  const { live, recent } = rows;
  const liveCard = live ? el("div", { class: "mobile-field-log-live" },
    el("div", { class: "row1" },
      el("span", { text: `◢ ROLL ${live.roll_label || "R—"} · ${live.outcome}` }),
      el("span", { text: live.outcome === "hit" ? `${rollTotalCost(live)} CP` : "—" }),
    ),
    el("div", { class: "name", text: mobileFieldLogPrincipalName(live) }),
    el("div", { class: "sub" }, ...mobileFieldLogSubChildren(live)),
  ) : null;
  const entries = recent.map(r => el("div", { class: "mobile-field-log-entry" },
    el("div", { class: "row1" },
      el("span", { text: `Ch ${r.chapter_num}` }),
      el("span", { text: r.outcome === "hit" ? `${rollTotalCost(r)} CP` : r.outcome }),
    ),
    el("div", { class: "name", text: mobileFieldLogPrincipalName(r) }),
  ));
  return [liveCard, ...entries].filter(Boolean);
}

// renderMobileFieldLog(): `.mobile-field-log` — header (`Field Log ·
// {constellation}` left, `{idx+1} of {total}` right, both em-dash/0-safe for
// an unknown constellation or a zero-roll story) over the list.
function renderMobileFieldLog() {
  const rows = mobileFieldLogRows();
  return el("div", { class: "mobile-field-log" },
    el("h3", { class: "mobile-field-log-header" },
      el("span", { text: `Field Log · ${rows.live?.constellation || "—"}` }),
      el("span", { class: "count", text: `${rows.idx + 1} of ${rows.total}` }),
    ),
    el("div", { class: "mobile-field-log-list" }, renderMobileFieldLogChildren(rows)),
  );
}

// renderMobileLandscapeSidebar(frame): `.mobile-sidebar` — the field log
// (top 2/3) over the control dock (bottom 1/3: Settings/About quick actions
// + a speed/mode/POV status row). Settings/About commit through the SAME
// module-level data-action delegation portrait's dock buttons use — no new
// click handler.
function renderMobileLandscapeSidebar(frame) {
  const controlDock = el("div", { class: "mobile-control-dock" },
    el("div", { class: "mobile-dock-quick-actions" },
      el("div", { class: "mobile-group-label", text: "Quick actions" }),
      el("div", { class: "mobile-dock-grid" },
        el("button", {
          class: `mobile-dock-btn${app.mobileSurface === "settings" ? " is-active" : ""}`,
          type: "button",
          "data-action": "mobile-open-settings",
          "aria-label": "Settings",
        }, mobileGearIcon(), el("span", { text: "Settings" })),
        el("button", {
          class: `mobile-dock-btn${app.mobileSurface === "info" ? " is-active" : ""}`,
          type: "button",
          "data-action": "mobile-open-info",
          "aria-label": "About",
        }, mobileInfoIcon(), el("span", { text: "About" })),
      ),
    ),
    el("div", { class: "mobile-dock-status" },
      el("span", { text: `${mobileSpeedMultiplier() ?? "—"}× · ${app.mode}` }),
      el("span", { class: "val", text: `${frame.chapter?.pov || "Joe"} POV` }),
    ),
  );
  return el("div", { class: "mobile-sidebar" }, renderMobileFieldLog(), controlDock);
}

// renderMobileCinemaScrubTrackChildren(): the baseline rail, the raw-
// playhead-percentage progress bar, one `.mobile-cinema-scrub-roll` marker
// per CACHED bin in app.mobileRailBins (never a second binning call — reuses
// the exact bins renderMobileLandscape()/the ResizeObserver already
// computed), and the thumb last so it always paints above the markers.
function renderMobileCinemaScrubTrackChildren() {
  const story = app.data.story;
  const total = story.total_words || 1;
  const playheadPctRaw = (app.wordPos / total) * 100;
  const rail = el("div", { class: "mobile-cinema-scrub-rail" });
  const progress = el("div", { class: "mobile-cinema-scrub-progress", style: { width: `${playheadPctRaw}%` } });
  const rolls = (app.mobileRailBins || []).map(bin => el("div", {
    class: `mobile-cinema-scrub-roll ${bin.dominant}`,
    style: { left: `${(bin.midWord / total) * 100}%` },
  }));
  const thumb = el("div", { class: "mobile-cinema-scrub-thumb", style: { left: `${playheadPctRaw}%` } });
  return [rail, progress, ...rolls, thumb];
}

// renderMobileCinemaScrub(): `.mobile-cinema-scrub` — the floating play/
// pause FAB, the roll-count readout, and the scrub track. Structure only —
// Plan 02 attaches the drag (attachRailScrub, D-17's single scrub input
// path) and the auto-hide chrome behavior; the play button commits through
// the SAME module-level `data-action="toggle-playback"` delegation the
// portrait FAB uses, no new click handler. `.mobile-rail-surface` (the
// existing touch-action:none gesture-surface utility) is applied directly
// to the track so Plan 02 never needs to write a second touch-action rule.
function renderMobileCinemaScrub() {
  const rows = mobileFieldLogRows();
  const story = app.data.story;
  const total = story.total_words || 1;
  const playheadPctRaw = (app.wordPos / total) * 100;
  const zoom = app.mobileTimelineZoom;
  const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
  return el("div", { class: "mobile-cinema-scrub" },
    el("button", {
      class: "mobile-cinema-scrub-fab",
      type: "button",
      "data-action": "toggle-playback",
      "aria-label": app.playing ? "Pause" : "Play",
      text: app.playing ? "❚❚" : "▶",
    }),
    el("span", { class: "mobile-cinema-scrub-count", text: `${rows.idx + 1} / ${rows.total}` }),
    el("div", { class: "mobile-cinema-scrub-track mobile-rail-surface" },
      el("div", {
        class: "mobile-cinema-scrub-inner",
        style: { width: `${zoom * 100}%`, transform: `translateX(-${panPct}%)` },
      },
        renderMobileCinemaScrubTrackChildren(),
      ),
    ),
  );
}

// renderMobileLandscape(): the Phase 3 landscape arm of render(), structural
// sibling of renderMobilePortrait() in the same order (maybeAutoOpenHelp ->
// frame state -> rail-width guard -> bin recompute -> root el()). Root
// `.mobile-app mobile-app-landscape` holds the landscape stage (shared sky +
// top chips + cinema-scrub, the containing block for their absolutely-
// positioned children) beside the sidebar, with the surface backdrop as the
// LAST child spanning the whole root — same D-19-derived shape Phase 2
// arrived at, so a backdrop tap dismisses over the whole surface including
// the rail.
function renderMobileLandscape() {
  maybeAutoOpenHelp();
  const frame = playthroughFrameState();
  // RESEARCH Pitfall 6/CONTEXT A2: guard against a stale portrait
  // measurement (or the shared default) mis-binning the narrower landscape
  // cinema-scrub track for one frame right after a rotation.
  app.mobileRailWidth = mobileScrubWidthDefaultForLayout();
  // Structural render is one of the four sanctioned call sites for bin
  // recomputation (D-18) — never inside updateMobileLandscapeFrame().
  recomputeMobileRailBins();
  return el("div", { class: "mobile-app mobile-app-landscape" },
    el("div", { class: "mobile-landscape-stage" },
      el("div", { class: "mobile-sky mobile-sky-surface mobile-sky-landscape" },
        ...renderMobileSkyRegion(frame),
      ),
      renderMobileTopCluster(),
      renderMobileCinemaScrub(),
    ),
    renderMobileLandscapeSidebar(frame),
    renderMobileSurfaceBackdrop(),
  );
}

// updateMobileFieldLogFrame() (D-18/D-26): the field log's incremental
// update, the memoized-key idiom desktop's updatePlaythroughFrame() already
// uses for its own field log (app.frameKeys.narrative). The key joins the
// live roll's uid (or a "none" sentinel) with the recent rolls' uids — only
// when it changes does replaceChildren() rebuild the list; the header's
// count/label spans and the cinema-scrub's count span get a plain
// textContent write every frame regardless (cheap, and correctness-critical:
// they must never show a stale constellation/count while the list itself
// hasn't changed key).
function updateMobileFieldLogFrame() {
  const rows = mobileFieldLogRows();
  const key = `${rows.live ? rows.live.uid : "none"}|${rows.recent.map(r => r.uid).join(",")}`;
  if (app.dom.mobileFieldLogList && app.frameKeys.mobileFieldLog !== key) {
    app.dom.mobileFieldLogList.replaceChildren(...renderMobileFieldLogChildren(rows));
    app.frameKeys.mobileFieldLog = key;
  }
  if (app.dom.mobileFieldLogHeader?.firstElementChild) {
    app.dom.mobileFieldLogHeader.firstElementChild.textContent = `Field Log · ${rows.live?.constellation || "—"}`;
  }
  if (app.dom.mobileFieldLogHeaderCount) {
    app.dom.mobileFieldLogHeaderCount.textContent = `${rows.idx + 1} of ${rows.total}`;
  }
  if (app.dom.mobileCinemaScrubCount) {
    app.dom.mobileCinemaScrubCount.textContent = `${rows.idx + 1} / ${rows.total}`;
  }
}

// updateMobileLandscapeFrame() (D-18/D-26): the landscape incremental tier,
// mirroring updateMobilePortraitFrame()'s shape. Mutates text/style only —
// never rebuilds the cinema-scrub track's markers here (bins only recompute
// on structural render/zoom change/resize, D-18).
function updateMobileLandscapeFrame() {
  const frame = playthroughFrameState();
  updateMobileSkyCameraFrame(frame);
  updateMobileTopClusterFrame();
  updateMobileFocalLabelFrame(frame);
  if (app.dom.mobileCinemaScrubFab) {
    const label = app.playing ? "Pause" : "Play";
    app.dom.mobileCinemaScrubFab.setAttribute("aria-label", label);
    app.dom.mobileCinemaScrubFab.textContent = app.playing ? "❚❚" : "▶";
  }
  if (app.dom.mobileDockStatus?.lastElementChild) {
    app.dom.mobileDockStatus.lastElementChild.textContent = `${frame.chapter?.pov || "Joe"} POV`;
  }
  const total = app.data.story.total_words || 1;
  const playheadPctRaw = (app.wordPos / total) * 100;
  if (app.dom.mobileCinemaScrubThumb) app.dom.mobileCinemaScrubThumb.style.left = `${playheadPctRaw}%`;
  if (app.dom.mobileCinemaScrubProgress) app.dom.mobileCinemaScrubProgress.style.width = `${playheadPctRaw}%`;
  if (app.dom.mobileCinemaScrubInner) {
    const panPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
    app.dom.mobileCinemaScrubInner.style.transform = `translateX(-${panPct}%)`;
  }
  updateMobileFieldLogFrame();
}

// mobileScrubSurfaceEl() (Phase 3, D-34): the ONE place the scrub-drag
// surface selector lives — portrait's mini-rail vs. landscape's floating
// cinema-scrub track. NEVER query .mobile-rail for landscape: that class is
// portrait's mini-rail, and the landscape sidebar is deliberately named
// .mobile-sidebar precisely so the two "rail" concepts can never be
// conflated (03-PATTERNS.md's "rail vs rail" naming-collision warning).
function mobileScrubSurfaceEl() {
  return app.layoutMode === "landscape"
    ? document.querySelector(".mobile-cinema-scrub-track")
    : document.querySelector(".mobile-rail");
}

// rebuildMobileCinemaScrubTrack() (Phase 3, D-18/D-34): the landscape
// counterpart of the ResizeObserver's portrait rolls-lane rebuild below —
// replaces the cinema-scrub track's roll markers with the freshly-binned
// set and re-caches the progress/thumb refs from the fresh children, so the
// per-frame style writes in updateMobileLandscapeFrame() never target a
// node this rebuild just detached.
function rebuildMobileCinemaScrubTrack() {
  const inner = app.dom.mobileCinemaScrubInner;
  if (!inner) return;
  inner.replaceChildren(...renderMobileCinemaScrubTrackChildren());
  app.dom.mobileCinemaScrubProgress = inner.querySelector(".mobile-cinema-scrub-progress");
  app.dom.mobileCinemaScrubThumb = inner.querySelector(".mobile-cinema-scrub-thumb");
}

// revealMobileChrome() (Phase 3, D-29/D-30): sets app.chromeHidden false and
// removes the hidden-state class from the cached cinema-scrub node — the
// scrub is the ONLY thing auto-hide ever hides; the top chips and the rail
// stay visible so the field log stays readable (D-29). Performs no timer
// work of its own so callers stay explicit about whether the idle window
// should re-arm. Never calls render() — a structural render would tear down
// and reattach every gesture listener.
function revealMobileChrome() {
  app.chromeHidden = false;
  app.dom.mobileCinemaScrub?.classList.remove("is-hidden");
}

// resetMobileChromeHideTimer() (Phase 3, MOBL-02, RESEARCH Pattern 4): the
// landscape chrome auto-hide idle-timer lifecycle. Always clears the
// outstanding handle first, then — ONLY while landscape AND playing AND no
// surface is open (D-28) — arms a fresh window that hides the scrub via a
// class mutation on the cached DOM ref, never via render(). Called from
// every discrete gesture-callback body below (the only sanctioned "any
// touch happened" signal, since web/mobile-gestures.js is frozen and cannot
// gain an onDown hook) and from togglePlayback()'s exits. Do NOT call this
// from updateMobileLandscapeFrame() or key it on a wordPos comparison:
// wordPos changes on every rAF tick during playback, so that keying (the
// prototype's own reference bug) would re-arm the timer ~60 times a second
// and the 4000ms window could never elapse (RESEARCH Pitfall 1) — if a
// manual pass ever shows the scrub failing to fade during unattended
// playback, this comment is the first thing to check.
function resetMobileChromeHideTimer() {
  clearTimeout(app.mobileChromeHideTimer);
  app.mobileChromeHideTimer = null;
  if (app.layoutMode === "landscape" && app.playing && !app.mobileSurface) {
    app.mobileChromeHideTimer = setTimeout(() => {
      app.chromeHidden = true;
      // Optional chain: T-03-06 mitigation — a timer that outlives its
      // owning layout/DOM must be a silent no-op, never a throw.
      app.dom.mobileCinemaScrub?.classList.add("is-hidden");
    }, window.GestureConstants?.CHROME_AUTOHIDE ?? 4000);
  }
}

// attachMobileGestures() (Phase 3, D-34 — renamed/generalized from
// attachMobilePortraitGestures): the SINGLE gesture-attach lifecycle for
// BOTH mobile layouts. Mirrors attachMobileGestureProbes's lifecycle exactly
// (teardown stored on `app`, invoked defensively before re-attach, called
// only from inside the render pass). Uses the mobileSkyTeardown/
// mobileRailTeardown/mobileRailResizeObserver/mobileChromeHideTimer slots —
// never app.mobileGestureTeardown, which the Phase 1 probe owns. Every slot
// is torn down unconditionally before the mobileSurface guard below so a
// stale listener/timer never survives an overlay opening/closing between
// renders or a layout transition away from landscape. Rail/cinema-scrub
// scrub commits through the existing setWordPos path only (D-17): a single
// scrub input, never a second raw pointer-listener override.
//
// The ONE hard branch point is the sky's onTap callback (D-30's reveal-vs-
// pause ordering only exists in landscape) and mobileScrubSurfaceEl()'s
// selector — every other callback body is identical for both layouts.
function attachMobileGestures() {
  if (typeof app.mobileSkyTeardown === "function") {
    app.mobileSkyTeardown();
    app.mobileSkyTeardown = null;
  }
  if (typeof app.mobileRailTeardown === "function") {
    app.mobileRailTeardown();
    app.mobileRailTeardown = null;
  }
  // A structural render tears the rail listeners down mid-drag without ever
  // firing onScrubEnd, so drop any frozen pan here too — otherwise the next
  // drag would inherit a stale offset from the abandoned one.
  app.mobileScrubPanPct = null;
  // Defensive teardown discipline (same as the two gesture slots above):
  // disconnect any prior rail ResizeObserver before a re-attach ever
  // installs a new one, so a stale observer from a previous render can
  // never pile up alongside the current one.
  if (app.mobileRailResizeObserver) {
    app.mobileRailResizeObserver.disconnect();
    app.mobileRailResizeObserver = null;
  }
  // Phase 3 (Pattern 4/T-03-06): a stale auto-hide timer must never survive
  // a re-attach or a layout transition away from landscape — cleared
  // unconditionally, in the same position as the three teardown calls above.
  clearTimeout(app.mobileChromeHideTimer);
  app.mobileChromeHideTimer = null;
  // An open overlay (Settings/About/Help, Plan 02-04) owns input while
  // shown — a tap landing on the sky underneath it must never bubble into a
  // pause toggle, so neither gesture surface attaches while it's open.
  if (app.mobileSurface) return;

  const skyEl = document.querySelector(".mobile-sky");
  if (skyEl && typeof window.attachSkyGestures === "function") {
    app.mobileSkyTeardown = window.attachSkyGestures(skyEl, {
      onTap: () => {
        // D-30: the first tap on hidden landscape chrome ALWAYS reveals it,
        // regardless of the tap-to-pause preference, and must never fall
        // through to togglePlayback() in the same invocation — hidden
        // chrome is never a trap. Evaluated FIRST, before the tap-to-pause
        // check below.
        if (app.layoutMode === "landscape" && app.chromeHidden) {
          revealMobileChrome();
          resetMobileChromeHideTimer();
          return;
        }
        // Tap is a no-op unless tap-to-pause is on — otherwise it toggles
        // playback through the shared setter, same as the FAB/spacebar path.
        if (!app.tapToPause) return;
        togglePlayback();
        resetMobileChromeHideTimer();
      },
      // Snap to the last roll at or before the CURRENT playhead and resume —
      // never app.data.story.rolls.at(-1), which would teleport the reader
      // to the end of the story (RESEARCH Pitfall 4).
      onDoubleTap: () => {
        const target = lastRollAtWord(app.wordPos);
        if (target) setWordPos(target.word_position);
        if (!app.playing) togglePlayback();
        resetMobileChromeHideTimer();
      },
      // Swipe right (dir +1) is forward per INTEGRATION_PLAN.md §1's locked
      // decision; mobile-gestures.js already resolves dir from swipe
      // direction, so this callback only ever forwards it.
      onSwipeStep: dir => {
        const next = rollStepFrom(app.wordPos, dir);
        if (next) setWordPos(next.word_position);
        resetMobileChromeHideTimer();
      },
      onSwipeEnd: () => {
        persistBookmarkNow();
        resetMobileChromeHideTimer();
      },
    });
  }

  const scrubEl = mobileScrubSurfaceEl();
  if (scrubEl && typeof window.attachRailScrub === "function") {
    app.mobileRailTeardown = window.attachRailScrub(scrubEl, {
      onScrub: viewportFraction => {
        if (!app.data) return null;
        const total = app.data.story.total_words || 1;
        // Freeze the auto-pan offset for the whole drag, capturing it on the
        // first callback (pointerdown) and clearing it in onScrubEnd.
        // Recomputing per move feeds the position this drag just committed
        // back into the mapping: the content shifts under the stationary
        // finger, so the next move lands somewhere unrelated. Measured at 4x
        // on a Pixel 10 Pro XL, a monotonic rightward drag drove the playhead
        // 68k words BACKWARD before recovering. Auto-pan still applies to
        // playback and to taps — each tap is its own drag and re-captures.
        // The landscape cinema-scrub inherits this exact fix by
        // construction (same callback body, only the queried element
        // differs) rather than rediscovering the bug on a second device.
        if (app.mobileScrubPanPct == null) {
          const playheadPctRaw = (app.wordPos / total) * 100;
          app.mobileScrubPanPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
        }
        const innerFrac = mobileInnerFraction(viewportFraction, app.mobileTimelineZoom, app.mobileScrubPanPct);
        const target = Math.round(innerFrac * total);
        setWordPos(target);
        resetMobileChromeHideTimer();
        return lastRollAtWord(target);
      },
      onScrubEnd: () => {
        app.mobileScrubPanPct = null;
        persistBookmarkNow();
        resetMobileChromeHideTimer();
      },
    });
  }

  // Rail/cinema-scrub width observer (MOBP-04/D-18, generalized D-34): keeps
  // app.mobileRailWidth current and recomputes bins on resize — coalesced
  // through a single rAF, replacing ONLY the layout-appropriate "rolls lane"
  // markup, never calling render(). A resize is not a structural-presence
  // change; the rest of the DOM must stay untouched.
  if (scrubEl && typeof ResizeObserver === "function") {
    let rafId = null;
    const ro = new ResizeObserver(entries => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      app.mobileRailWidth = Math.max(50, cr.width);
      // Phase 3 (Pitfall 6/CONTEXT A2): record which layout this
      // measurement belongs to so a stale cross-layout width is never used
      // to bin the OTHER layout's differently-sized scrub track.
      app.mobileRailWidthLayout = app.layoutMode;
      if (rafId != null) return;
      rafId = requestAnimationFrame(() => {
        rafId = null;
        recomputeMobileRailBins();
        if (app.layoutMode === "landscape") {
          rebuildMobileCinemaScrubTrack();
        } else {
          const rollsLane = app.dom.mobileRailRollsLane;
          if (rollsLane) {
            rollsLane.replaceChildren(...renderMobileRailRollsLaneChildren());
            // The active dot is rebuilt along with the bins — re-cache the
            // ref so updateMobileActiveDotFrame() never writes into a node
            // this resize just detached from the DOM.
            app.dom.mobileActiveDot = rollsLane.querySelector(".mobile-roll-dot.active");
          }
        }
      });
    });
    ro.observe(scrubEl);
    app.mobileRailResizeObserver = ro;
  }
}

// Module-level click delegation keeps hot playback controls independent of
// whether a structural render or incremental frame update touched their DOM.
// Keyboard activation (Enter/Space on a focused button) still fires `click`
// natively, so it works through the same path without extra key handling here.
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
  } else if (action === "mobile-cycle-speed") {
    // Advances to the next rung, wrapping from the last back to the first;
    // starts from "1" when the current speed matches no rung (e.g. it was
    // set from the desktop <select> to a value outside the mobile rungs).
    const currentLabel = mobileSpeedMultiplier() ?? "1";
    const currentIndex = MOBILE_SPEED_RUNGS.findIndex(([label]) => label === currentLabel);
    const nextIndex = (currentIndex + 1) % MOBILE_SPEED_RUNGS.length;
    setMobileSpeedMultiplier(MOBILE_SPEED_RUNGS[nextIndex][0]);
    event.preventDefault();
  } else if (action === "mobile-open-settings") {
    openMobileSurface("settings", target);
    event.preventDefault();
  } else if (action === "mobile-open-info") {
    openMobileSurface("info", target);
    event.preventDefault();
  } else if (action === "mobile-open-help") {
    openMobileSurface("help", target);
    event.preventDefault();
  } else if (action === "mobile-close-surface") {
    closeMobileSurface();
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

window.addEventListener("pagehide", () => {
  if (app.data) persistBookmarkNow();
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden" && app.data) persistBookmarkNow();
  // D-02, mobile-only: hiding the page pauses playthrough with state intact;
  // no auto-resume on return to visible. Desktop path above is unchanged.
  if (document.visibilityState === "hidden" && app.layoutMode !== "desktop" && app.playing) {
    stopPlayback();
  }
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

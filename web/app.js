/* Brockton's Celestial Forge — DAW scrubber app
 *
 * Reads data/derived/chapter_facts.json and renders a multi-track
 * scrubber whose primary axis is total words read.
 *
 *   coordinate system
 *   ─────────────────
 *   Word axis runs from -PRE_ROLL_WORDS (lead-in band) through 0 (start
 *   of chapter 1) to TOTAL_WORDS (end of last chapter). Roll positions
 *   are approximated from `predicted_word_position_epub` (CP-words)
 *   mapped into total-word space via each chapter's cp/total ratio;
 *   close enough for visualization. Shadow trigger positions also come
 *   in CP-words and use the same mapping.
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
    label: "ch 91",
    title: "After this chapter, every other roll attempt is skipped. Joe still earns power at the same rate; the Forge just only checks for a connection at every other 100-point milestone.",
  },
  {
    chapter: "97",
    label: "ch 97",
    title: "Power accrues more slowly now (3,000 words per 100 points instead of 2,000), and after Joe acquires anything expensive, the Forge needs time to recover before he can earn anything new.",
  },
];

// localStorage keys (versioned).
const LS_BOOKMARK = "bcf:bookmark:word_position";
const LS_SPEED = "bcf:playback:speed:v2";
const LS_ZOOM = "bcf:timeline:zoom";
const LS_VERSION = "bcf:storage:version";
const STORAGE_VERSION = "3";   // bumped when pre-roll changed from 100k to 5k

// Pre-roll lead-in: empty band before chapter 1 word=0. Useful for
// animations to settle before content arrives.
const PRE_ROLL_WORDS = 5_000;
const DEFAULT_SPEED = 10;
const DEFAULT_ZOOM = 8;
const MIN_ZOOM = 1;
const MAX_ZOOM = 32;

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
      else if (k === "style" && typeof v === "object") Object.assign(e.style, v);
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
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function $(id) { return document.getElementById(id); }

// ---------- data loading -------------------------------------------------

async function loadJSON(name) {
  const r = await fetch(`${DATA_BASE}/${name}.json`);
  if (!r.ok) throw new Error(`failed to load ${name}: ${r.status}`);
  return r.json();
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
  const span = model.chapterSpans[model.idxOf.get(chapter.chapter_num)];
  if (roll.predicted_word_position_epub == null) {
    const chapterWidth = Math.max(1, span.end_word - span.start_word);
    const slot = (fallbackIndex + 1) / (fallbackTotal + 1);
    return span.start_word + chapterWidth * slot;
  }
  if (span.end_cp > span.start_cp) {
    const cpFrac = (roll.predicted_word_position_epub - span.start_cp) /
                   (span.end_cp - span.start_cp);
    return span.start_word + cpFrac * (span.end_word - span.start_word);
  }
  return (span.start_word + span.end_word) / 2;
}

function shadowWordRange(model, sp) {
  function cpToTotal(cpPos) {
    for (const span of model.chapterSpans) {
      if (cpPos >= span.start_cp && cpPos <= span.end_cp) {
        if (span.end_cp === span.start_cp) return span.start_word;
        const f = (cpPos - span.start_cp) / (span.end_cp - span.start_cp);
        return span.start_word + f * (span.end_word - span.start_word);
      }
    }
    return cpPos < 0 ? 0 : model.totalWords;
  }
  return [cpToTotal(sp.trigger_word_position_epub),
          cpToTotal(sp.shadow_end_word_position_epub)];
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

function clampZoom(z) {
  if (!Number.isFinite(z)) return DEFAULT_ZOOM;
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.round(z)));
}

function timelineWidthForZoom(zoom) {
  const container = $("scrubber-container");
  const baseWidth = container.clientWidth || container.getBoundingClientRect().width || 1;
  return Math.max(baseWidth, Math.round(baseWidth * clampZoom(zoom)));
}

function applyTimelineZoom(state, options = {}) {
  const zoom = clampZoom(state.zoom);
  state.zoom = zoom;
  const stack = $("track-stack");
  stack.style.width = `${timelineWidthForZoom(zoom)}px`;
  stack.dataset.zoomDetail = zoom >= 16 ? "exact" : zoom >= 8 ? "high" : zoom >= 4 ? "medium" : "low";
  $("timeline-zoom").value = String(zoom);
  $("zoom-readout").textContent = zoom === 1 ? "fit" : `${zoom}×`;
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

function renderRealWorldDateTrack(model) {
  const track = $("track-dates");
  const monthSeen = new Set();
  const daySeen = new Set();
  const firstYear = new Date(model.chapters[0].published_at).getFullYear();
  const lastYear = new Date(model.chapters[model.chapters.length - 1].published_at).getFullYear();
  for (let year = firstYear; year <= lastYear; year++) {
    const span = model.chapterSpans.find(s =>
      new Date(s.chapter.published_at).getFullYear() >= year);
    if (!span) continue;
    const date = span.chapter.published_at.slice(0, 10);
    track.appendChild(el("div", {
      class: "date-tick year",
      style: { left: `${pctOf(model, span.start_word).toFixed(4)}%` },
      title: `${year}: first chapter at or after Jan 1 is ch ${span.chapter.chapter_num}, published ${date}`,
    }));
    track.appendChild(el("div", {
      class: "date-label",
      text: String(year),
      style: { left: `${pctOf(model, span.start_word).toFixed(4)}%` },
    }));
  }

  for (const span of model.chapterSpans) {
    const date = span.chapter.published_at.slice(0, 10);
    const month = date.slice(0, 7);
    const left = `${pctOf(model, span.start_word).toFixed(4)}%`;
    if (!monthSeen.has(month)) {
      monthSeen.add(month);
      const monthLabel = new Date(span.chapter.published_at)
        .toLocaleString("en-US", { month: "short", year: "2-digit" });
      track.appendChild(el("div", {
        class: "date-tick month",
        style: { left },
        title: `${monthLabel}: first chapter is ch ${span.chapter.chapter_num}, published ${date}`,
      }));
      track.appendChild(el("div", {
        class: "date-label month-label",
        text: monthLabel,
        style: { left },
      }));
    }
    if (!daySeen.has(date)) {
      daySeen.add(date);
      track.appendChild(el("div", {
        class: "date-tick day",
        style: { left },
        title: `${date}: ch ${span.chapter.chapter_num} — ${span.chapter.full_title}`,
      }));
      track.appendChild(el("div", {
        class: "date-label day-label",
        text: date.slice(5),
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
    const tick = el("button", {
      type: "button",
      class: `chap-tick ${isMajor ? "major" : "minor"}`,
      style: { left: `${pctOf(model, span.start_word).toFixed(4)}%` },
      title: `ch ${chap.chapter_num} — ${chap.full_title} · published ${chap.published_at.slice(0, 10)} · last edited ${chap.last_edited_at || "unknown"}`,
      "data-chapter-num": chap.chapter_num,
    });
    tick._chapter = chap;
    tick._wordPos = span.start_word;
    track.appendChild(tick);
    if (isMajor) {
      track.appendChild(el("div", {
        class: "chap-label",
        text: chap.chapter_num,
        style: { left: `${pctOf(model, span.start_word).toFixed(4)}%` },
      }));
    }
  }
}

function renderShadowsTrack(model, facts) {
  const track = $("track-shadows");
  for (const sp of facts.shadow_periods) {
    const [a, b] = shadowWordRange(model, sp);
    const widthPct = Math.max(0.1, pctOf(model, b) - pctOf(model, a));
    track.appendChild(el("div", {
      class: "shadow-bar",
      style: { left: `${pctOf(model, a).toFixed(4)}%`,
               width: `${widthPct.toFixed(4)}%` },
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
      const dot = el("button", {
        type: "button",
        class: `roll-dot ${rollClass(r)}`,
        style: rollDotStyle(model, r, wp),
        "data-chapter-num": c.chapter_num,
        "data-roll-number": r.roll_number ?? "",
        title: rollDotTitle(r, c),
      });
      dot._roll = r;
      dot._chapter = c;
      dot._wordPos = wp;
      track.appendChild(dot);
      renderFreePerkCluster(track, model, r, c, wp);
    }
  }
}

function renderFreePerkCluster(track, model, roll, chapter, wordPos) {
  const freePerks = roll.free_perks || [];
  if (roll.outcome !== "hit" || freePerks.length === 0) return;

  freePerks.forEach((freePerk, idx) => {
    const dot = el("button", {
      type: "button",
      class: "roll-dot free-sibling",
      style: freePerkDotStyle(model, wordPos, freePerk, idx, freePerks.length),
      "data-chapter-num": chapter.chapter_num,
      "data-free-index": String(idx),
      title: freePerkTitle(freePerk, roll, chapter),
    });
    dot._roll = {
      outcome: "hit",
      constellation: freePerk.constellation || roll.constellation,
      purchased_perk_name: freePerk.name,
      purchased_perk_cost: 0,
      purchased_perk_jump: freePerk.jump,
      free_perks: [],
      evidence_kind: "free_sibling",
    };
    dot._chapter = chapter;
    dot._wordPos = wordPos;
    track.appendChild(dot);
  });
}

function rollClass(r) {
  if (r.evidence_kind === "untracked_acquisition") return "untracked";
  if (r.outcome === "hit") return "hit";
  if (r.outcome === "miss") return "miss";
  return "unknown";
}

function rollDotStyle(model, r, wp) {
  const size = rollDotSize(r);
  const color = rollDotColor(r);
  return {
    left: `${pctOf(model, wp).toFixed(4)}%`,
    width: `${size}px`,
    height: `${size}px`,
    marginLeft: `${-(size / 2)}px`,
    backgroundColor: color,
    borderColor: r.evidence_kind === "untracked_acquisition" ? color : "rgba(255, 255, 255, 0.7)",
  };
}

function freePerkDotStyle(model, wp, freePerk, idx, total) {
  const maxCols = 5;
  const colsInRow = Math.min(maxCols, total - Math.floor(idx / maxCols) * maxCols);
  const col = idx % maxCols;
  const row = Math.floor(idx / maxCols);
  const offset = (col - (colsInRow - 1) / 2) * 6;
  const color = CONSTELLATION_COLORS[freePerk.constellation] || "var(--hit)";
  return {
    left: `${pctOf(model, wp).toFixed(4)}%`,
    top: `${42 + row * 7}px`,
    width: "4px",
    height: "4px",
    marginLeft: `${offset - 2}px`,
    backgroundColor: color,
    borderColor: color,
  };
}

function rollDotColor(r) {
  if ((r.outcome === "hit" || r.evidence_kind === "untracked_acquisition") && r.constellation) {
    return CONSTELLATION_COLORS[r.constellation] || "var(--hit)";
  }
  return "var(--unknown)";
}

function rollDotSize(r) {
  const cost = Number(r.purchased_perk_cost);
  if (cost === 0) return 4;
  if (cost === 100) return 6;
  if (cost === 200) return 8;
  if (cost === 300) return 9;
  if (cost === 400) return 10;
  if (cost === 600) return 12;
  if (cost === 800) return 14;
  return r.outcome === "hit" ? 6 : 5;
}

function rollDotTitle(r, c) {
  const name = r.purchased_perk_name || r.outcome;
  const bits = [`ch ${c.chapter_num}`, name];
  if (r.constellation) bits.push(r.constellation);
  if (r.purchased_perk_cost != null) bits.push(`${r.purchased_perk_cost} CP`);
  return bits.join(" · ");
}

function freePerkTitle(freePerk, roll, chapter) {
  const bits = [`ch ${chapter.chapter_num}`, freePerk.name, "free with " + roll.purchased_perk_name];
  if (freePerk.constellation) bits.push(freePerk.constellation);
  if (freePerk.jump) bits.push(freePerk.jump);
  return bits.join(" · ");
}

function renderLegend() {
  const container = $("constellation-legend");
  clear(container);
  for (const name of CONSTELLATION_ORDER) {
    container.appendChild(el("span", {
      class: "swatch",
      style: { backgroundColor: CONSTELLATION_COLORS[name] },
    }));
    container.appendChild(el("span", { text: name }));
  }
}

function renderAxisTrack(model) {
  const track = $("track-axis");
  const step = 250_000;
  const major = 500_000;
  for (let w = 0; w <= model.totalWords; w += step) {
    track.appendChild(el("div", {
      class: "axis-tick",
      style: { left: `${pctOf(model, w).toFixed(4)}%` },
    }));
    if (w % major === 0) {
      track.appendChild(el("div", {
        class: "axis-label",
        text: w === 0 ? "0" : `${(w / 1000).toFixed(0)}k`,
        style: { left: `${pctOf(model, w).toFixed(4)}%` },
      }));
    }
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
  const constByCh = new Map();
  const constState = new Map(CONSTELLATION_ORDER.map(c => [c, 0]));
  for (const c of facts.chapters) {
    paid += c.paid_perks_gained;
    free += c.free_perks_gained;
    hits += c.hits_count;
    otherRolls += c.misses_count + c.unknowns_count;
    for (const r of c.rolls) {
      if (r.outcome === "hit" && r.constellation) {
        constState.set(r.constellation, (constState.get(r.constellation) || 0) + 1);
      }
      for (const freePerk of r.free_perks || []) {
        if (freePerk.constellation) {
          constState.set(freePerk.constellation, (constState.get(freePerk.constellation) || 0) + 1);
        }
      }
    }
    cumByCh.set(c.chapter_num, { paid, free, hits, otherRolls });
    constByCh.set(c.chapter_num, new Map(constState));
  }
  const constMax = Math.max(1, ...Array.from(constState.values()));
  return { cumByCh, constByCh, constMax };
}

function renderState(state) {
  const { model, facts, cumIdx, currentWord } = state;
  const inPreroll = currentWord < 0;
  const ch = chapterAtWord(model, currentWord);
  const idx = ch ? model.idxOf.get(ch.chapter_num) : -1;

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
  const constMap = (!inPreroll && ch)
    ? cumIdx.constByCh.get(ch.chapter_num)
    : new Map(CONSTELLATION_ORDER.map(c => [c, 0]));
  renderConstellations(constMap, cumIdx.constMax);
  renderRecent(state, ch, inPreroll);
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
    const name = r.purchased_perk_name || (r.outcome === "hit" ? "(unattributed)" : "—");
    const left = el("span", null, el("span", { class: "perk-name" }, name));
    if (r.free_perks.length) {
      left.appendChild(el("span", { class: "perk-source" },
        ` + ${r.free_perks.length} free`));
    }
    list.appendChild(el("li", null, left, tagEl));
  }
}

function renderConstellations(constMap, scaleMax) {
  const container = $("constellation-bars");
  clear(container);
  const max = Math.max(1, scaleMax);
  for (const name of CONSTELLATION_ORDER) {
    const count = constMap.get(name) || 0;
    const pct = (count / max) * 100;
    container.appendChild(el("span", { class: "const-name" }, name));
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
    container.appendChild(el("span", { class: "const-count" }, String(count)));
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
      if (r.outcome !== "hit" || !r.purchased_perk_name) continue;
      collected.push({ roll: r, chapter: c });
      if (collected.length >= 10) break;
    }
  }
  if (collected.length === 0) {
    list.appendChild(el("li", { class: "empty" },
      el("span", { class: "perk-name", style: { color: "var(--gray-3)" } },
        "No acquisitions yet.")));
    return;
  }
  for (const { roll, chapter } of collected) {
    const left = el("span", null,
      el("span", { class: "perk-name" }, roll.purchased_perk_name),
      el("span", { class: "perk-source" }, ` — ${roll.constellation || ""}`));
    list.appendChild(el("li", null,
      left,
      el("span", { class: "perk-cost" }, roll.constellation || "?"),
      el("span", { class: "perk-chapter" }, `ch ${chapter.chapter_num}`)));
  }
}

// ---------- tooltip on roll dots -----------------------------------------

function attachRollTooltip() {
  const tip = $("roll-tooltip");
  const track = $("track-rolls");

  function placeTooltip(e) {
    const pad = 10;
    const tipRect = tip.getBoundingClientRect();
    let x = e.clientX + 12;
    let y = e.clientY + 12;
    if (x + tipRect.width + pad > window.innerWidth) x = e.clientX - tipRect.width - 12;
    if (y + tipRect.height + pad > window.innerHeight) y = e.clientY - tipRect.height - 12;
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }
  function show(dot, e) {
    clear(tip);
    const r = dot._roll;
    const c = dot._chapter;
    const outcomeText = r.outcome === "hit" ? "hit" :
                        r.outcome === "miss" ? "miss" : "unknown";
    const titleText = r.purchased_perk_name || outcomeText.toUpperCase();
    tip.appendChild(el("div", { class: "tip-title" }, titleText));

    function row(label, value) {
      tip.appendChild(el("div", { class: "tip-row" },
        el("span", { class: "tip-label" }, label),
        " ", value));
    }
    row("chapter", `ch ${c.chapter_num} — ${c.full_title}`);
    row("outcome", outcomeText);
    if (r.constellation) row("constellation", r.constellation);
    if (r.purchased_perk_cost != null) row("cost", `${r.purchased_perk_cost} CP`);
    if (r.purchased_perk_jump) row("jump", r.purchased_perk_jump);
    row("evidence", r.evidence_kind);

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
  function hide() { tip.hidden = true; }

  track.addEventListener("mousemove", e => {
    const dot = e.target.closest(".roll-dot");
    if (!dot) return hide();
    show(dot, e);
  });
  track.addEventListener("mouseleave", hide);
  track.addEventListener("click", e => {
    const dot = e.target.closest(".roll-dot");
    if (!dot) return;
    const url = dot._chapter.post_url;
    if (url) window.open(url, "_blank", "noopener");
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
  function onPointerMove(e) {
    if (!dragging) return;
    const x = e.touches ? e.touches[0].clientX : e.clientX;
    setWord(state, wordFromClientX(x));
    e.preventDefault();
  }
  function onPointerUp() { dragging = false; document.body.style.userSelect = ""; }

  hit.addEventListener("mousedown", e => {
    if (e.target.closest(".roll-dot, .shadow-bar")) return;
    state.scrollFollow.pausedManualLock = false;
    dragging = true;
    document.body.style.userSelect = "none";
    setWord(state, wordFromClientX(e.clientX));
  });
  hit.addEventListener("touchstart", e => {
    if (e.target.closest(".roll-dot, .shadow-bar")) return;
    state.scrollFollow.pausedManualLock = false;
    dragging = true;
    setWord(state, wordFromClientX(e.touches[0].clientX));
  }, { passive: false });
  document.addEventListener("mousemove", onPointerMove);
  document.addEventListener("touchmove", onPointerMove, { passive: false });
  document.addEventListener("mouseup", onPointerUp);
  document.addEventListener("touchend", onPointerUp);

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
  track.addEventListener("click", e => {
    const tick = e.target.closest(".chap-tick");
    if (!tick) return;
    state.selectedChapterNum = tick.dataset.chapterNum;
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
    state.zoom = clampZoom(state.zoom - 1);
    applyTimelineZoom(state, { center: true });
  });
  zoomIn.addEventListener("click", () => {
    state.zoom = clampZoom(state.zoom + 1);
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
      zoom: clampZoom(parseFloat(localStorage.getItem(LS_ZOOM))),
    };
  } catch {
    return { word: NaN, speed: DEFAULT_SPEED, zoom: DEFAULT_ZOOM };
  }
}
function saveBookmark(w) { try { localStorage.setItem(LS_BOOKMARK, String(Math.round(w))); } catch {} }
function saveSpeed(s) { try { localStorage.setItem(LS_SPEED, String(s)); } catch {} }
function saveZoom(z) { try { localStorage.setItem(LS_ZOOM, String(clampZoom(z))); } catch {} }
function clearBookmark() { try { localStorage.removeItem(LS_BOOKMARK); } catch {} }

// ---------- bootstrap ----------------------------------------------------

(async () => {
  try {
    const facts = await loadJSON("chapter_facts");
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
    renderTracks(model, facts);
    applyTimelineZoom(state, { center: true });
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
        + "(e.g. python3 -m http.server) so data/derived/chapter_facts.json "
        + "is reachable."));
    clear(document.body);
    document.body.appendChild(errBox);
  }
})();

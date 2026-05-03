/* Brockton's Celestial Forge — scrubber app
 *
 * Loads data/derived/*.json (relative to this file's parent),
 * renders state through the currently-selected chapter index.
 *
 * No framework. Plain DOM, plain fetch, no build step.
 */

const DATA_BASE = "../data/derived";
const CONSTELLATION_ORDER = [
  "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
  "Clothing", "Magic", "Quality", "Size",
  "Resources and Durability", "Magitech", "Alchemy",
  "Capstone", "Personal Reality",
];

// ---------- data loading -------------------------------------------------

async function loadJSON(name) {
  const r = await fetch(`${DATA_BASE}/${name}.json`);
  if (!r.ok) throw new Error(`failed to load ${name}: ${r.status}`);
  return r.json();
}

async function loadAll() {
  const [chapters, rolls, obtained, perksCatalog] = await Promise.all([
    loadJSON("chapters"),
    loadJSON("rolls"),
    loadJSON("obtained_perks"),
    loadJSON("perks_catalog"),
  ]);
  return { chapters, rolls, obtained, perksCatalog };
}

// ---------- chapter ordering & indexing ---------------------------------

function sortKey(chapNum) {
  const [a, b] = chapNum.split(".");
  return [parseInt(a, 10), b ? parseInt(b, 10) : 0];
}

function chapCmp(a, b) {
  const ka = sortKey(a.chapter_num);
  const kb = sortKey(b.chapter_num);
  return ka[0] - kb[0] || ka[1] - kb[1];
}

// ---------- pre-aggregation: per-chapter cumulative state --------------

function buildIndex(data) {
  const chapters = data.chapters.chapters.slice().sort(chapCmp);
  const chapNums = chapters.map(c => c.chapter_num);
  const idxOf = new Map(chapNums.map((n, i) => [n, i]));

  // Index obtained perks by chapter.
  const acqByChap = new Map(chapNums.map(n => [n, []]));
  for (const p of data.obtained.perks) {
    if (acqByChap.has(p.chapter_num)) acqByChap.get(p.chapter_num).push(p);
  }
  // Within a chapter, preserve original sequence (epub_sequence is the
  // EPUB position; rows may share a sequence so we just keep the order
  // we read them in).

  // Index roll attempts (trigger/roll/miss) by chapter.
  const rollsByChap = new Map(chapNums.map(n => [n, []]));
  for (const r of data.rolls.rolls) {
    if (!rollsByChap.has(r.chapter_num)) continue;
    if (r.kind === "trigger" || r.kind === "roll" || r.kind === "miss") {
      rollsByChap.get(r.chapter_num).push(r);
    }
  }

  // Cumulative running totals at each chapter index.
  let words = 0, paid = 0, free = 0, rolls = 0, misses = 0;
  const cumByIdx = chapters.map((c, i) => {
    words += c.words_approx;
    const acqs = acqByChap.get(c.chapter_num) || [];
    for (const a of acqs) (a.free ? free++ : paid++);
    const rs = rollsByChap.get(c.chapter_num) || [];
    for (const r of rs) {
      if (r.kind === "miss") misses++;
      else rolls++;
    }
    return { words, paid, free, rolls, misses };
  });

  // Cumulative per-constellation count from rolls.json (only chapters 1-75
  // have constellation data; later chapters in obtained_perks lack a
  // direct constellation field, so we fall back to the catalog where
  // possible, else "Unknown").
  const catalogByName = new Map();
  for (const p of data.perksCatalog.perks) {
    if (!catalogByName.has(p.name)) catalogByName.set(p.name, p);
  }

  // Constellation-by-chapter accumulator.
  let constState = new Map(CONSTELLATION_ORDER.map(c => [c, 0]));
  const constByIdx = chapters.map(c => {
    // 1) From rolls.json (where constellation is known directly)
    const rs = rollsByChap.get(c.chapter_num) || [];
    for (const r of rs) {
      if (r.kind !== "trigger" && r.kind !== "roll") continue;
      const cn = r.constellation;
      if (!cn) continue;
      if (!constState.has(cn)) constState.set(cn, 0);
      constState.set(cn, constState.get(cn) + r.perks.length);
    }
    // 2) For chapters without rolls.json data (76+), look up each
    //    obtained perk in the catalog by name to find its constellation.
    if (rs.length === 0) {
      const acqs = acqByChap.get(c.chapter_num) || [];
      for (const a of acqs) {
        const m = catalogByName.get(a.perk_name);
        const cn = m ? m.constellation : null;
        if (cn) {
          if (!constState.has(cn)) constState.set(cn, 0);
          constState.set(cn, constState.get(cn) + 1);
        }
      }
    }
    return new Map(constState);
  });

  return { chapters, idxOf, acqByChap, rollsByChap, cumByIdx, constByIdx };
}

// ---------- rendering ---------------------------------------------------

function fmt(n)        { return Number(n).toLocaleString("en-US"); }
function fmtKWords(n)  {
  if (n < 1000) return `${n}`;
  if (n < 1_000_000) return `${(n / 1000).toFixed(0)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function renderReadout(c) {
  document.getElementById("readout-chapter").textContent = `ch ${c.chapter_num}`;
  document.getElementById("readout-title").textContent = c.title;
  document.getElementById("readout-date").textContent = c.publish_iso.slice(0, 10);
}

function renderCumulative(idx, cum, c) {
  document.getElementById("stat-chapters").textContent = fmt(idx + 1);
  document.getElementById("stat-words").textContent = fmtKWords(cum.words);
  document.getElementById("stat-perks-paid").textContent = fmt(cum.paid);
  document.getElementById("stat-perks-free").textContent = fmt(cum.free);
  document.getElementById("stat-rolls-attempts").textContent = fmt(cum.rolls + cum.misses);
  document.getElementById("stat-rolls-misses").textContent = fmt(cum.misses);

  const note = document.getElementById("cumulative-note");
  let hint = "";
  if (cum.rolls + cum.misses === 0) {
    hint = "Roll-by-roll detail only available for chapters 1-75.";
  } else if (sortKey(c.chapter_num)[0] > 75) {
    hint = "Roll counts above are partial — curator's roll log stops at chapter 75.";
  }
  note.textContent = hint;
}

function renderThisChapter(c, acqs, rolls) {
  const meta = document.getElementById("this-chapter-meta");
  const wordsApprox = c.words_text ? c.words_text : `${c.words_approx}`;
  const rollAttempts = rolls.length;
  const misses = rolls.filter(r => r.kind === "miss").length;
  const free = acqs.filter(a => a.free).length;
  const paid = acqs.length - free;
  meta.innerHTML =
    `<strong>${c.full_title}</strong> · ${wordsApprox} words · ` +
    `${paid} paid + ${free} free` +
    (rollAttempts ? ` · ${rollAttempts} roll attempts (${misses} miss${misses === 1 ? "" : "es"})` : "");

  const list = document.getElementById("this-chapter-perks");
  list.innerHTML = "";
  if (acqs.length === 0) {
    list.innerHTML = `<li class="empty"><span class="perk-name" style="color:var(--gray-3)">No acquisitions in this chapter.</span></li>`;
    return;
  }
  for (const a of acqs) {
    const cost = a.free
      ? `<span class="perk-cost free">${a.cost_text}</span>`
      : `<span class="perk-cost">${a.cost_text || a.cost}</span>`;
    list.insertAdjacentHTML("beforeend", `
      <li>
        <span><span class="perk-name">${escapeHTML(a.perk_name)}</span>
          <span class="perk-source"> — ${escapeHTML(a.jump || "")}</span></span>
        ${cost}
      </li>
    `);
  }
}

function renderConstellations(constMap) {
  const container = document.getElementById("constellation-bars");
  container.innerHTML = "";
  const max = Math.max(1, ...Array.from(constMap.values()));
  for (const name of CONSTELLATION_ORDER) {
    const count = constMap.get(name) || 0;
    const pct = (count / max) * 100;
    container.insertAdjacentHTML("beforeend", `
      <span class="const-name">${name}</span>
      <span class="const-bar-wrap" style="display:block; height:12px;">
        <span class="const-bar" style="display:block; width:${pct.toFixed(2)}%; height:100%;"></span>
      </span>
      <span class="const-count">${count}</span>
    `);
  }
}

function renderRecent(state) {
  const { idx, chapters, acqByChap } = state;
  const list = document.getElementById("recent-perks");
  list.innerHTML = "";
  // Walk backward from current chapter, collect acquisitions
  let collected = [];
  for (let i = idx; i >= 0 && collected.length < 12; i--) {
    const ch = chapters[i];
    const acqs = (acqByChap.get(ch.chapter_num) || []).slice().reverse();
    for (const a of acqs) {
      collected.push({ ...a, chapter_full_title: ch.full_title });
      if (collected.length >= 12) break;
    }
  }
  if (collected.length === 0) {
    list.innerHTML = `<li class="empty"><span class="perk-name" style="color:var(--gray-3)">No acquisitions yet.</span></li>`;
    return;
  }
  for (const a of collected) {
    const cost = a.free
      ? `<span class="perk-cost free">${a.cost_text}</span>`
      : `<span class="perk-cost">${a.cost_text || a.cost}</span>`;
    list.insertAdjacentHTML("beforeend", `
      <li>
        <span><span class="perk-name">${escapeHTML(a.perk_name)}</span>
          <span class="perk-source"> — ${escapeHTML(a.jump || "")}</span></span>
        ${cost}
        <span class="perk-chapter">ch ${escapeHTML(a.chapter_num)}</span>
      </li>
    `);
  }
}

function escapeHTML(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

// ---------- scrubber state ---------------------------------------------

function setRegimeMarkers(idx) {
  // Position the regime-change markers on the scrubber based on the
  // index of ch 91 and ch 97. Also set the CSS variables that drive
  // the gradient-band background of the track.
  const total = idx.chapters.length;
  const trackChildren = document.querySelectorAll(".regime-marker");
  for (const m of trackChildren) {
    const target = m.dataset.chapter;
    const i = idx.idxOf.get(target);
    if (i === undefined) {
      m.style.display = "none";
      continue;
    }
    const pct = ((i + 0.5) / total) * 100;
    m.style.left = `${pct}%`;
  }
  const i91 = idx.idxOf.get("91");
  const i97 = idx.idxOf.get("97");
  if (i91 !== undefined) {
    document.documentElement.style.setProperty(
      "--regime-2-start", ((i91 + 1) / total).toFixed(4)
    );
  }
  if (i97 !== undefined) {
    document.documentElement.style.setProperty(
      "--regime-3-start", ((i97 + 1) / total).toFixed(4)
    );
  }
}

function update(state, idx) {
  const total = state.chapters.length;
  if (idx < 0) idx = 0;
  if (idx >= total) idx = total - 1;
  state.idx = idx;

  const c = state.chapters[idx];
  const cum = state.cumByIdx[idx];
  const acqs = state.acqByChap.get(c.chapter_num) || [];
  const rolls = state.rollsByChap.get(c.chapter_num) || [];
  const constMap = state.constByIdx[idx];

  // Update knob position + aria
  const knob = document.getElementById("scrubber-knob");
  const fill = document.getElementById("scrubber-fill");
  const pct = ((idx + 0.5) / total) * 100;
  knob.style.left = `${pct}%`;
  fill.style.width = `${pct}%`;
  knob.setAttribute("aria-valuenow", String(idx + 1));
  knob.setAttribute("aria-valuetext", `chapter ${c.chapter_num}: ${c.title}`);

  renderReadout(c);
  renderCumulative(idx, cum, c);
  renderThisChapter(c, acqs, rolls);
  renderConstellations(constMap);
  renderRecent(state);
}

function attachScrubber(state) {
  const track = document.getElementById("scrubber-track");
  const knob = document.getElementById("scrubber-knob");
  const total = state.chapters.length;

  function idxFromClientX(x) {
    const rect = track.getBoundingClientRect();
    const rel = (x - rect.left) / rect.width;
    return Math.round(rel * total - 0.5);
  }

  let dragging = false;

  function onMove(e) {
    if (!dragging) return;
    const x = e.touches ? e.touches[0].clientX : e.clientX;
    update(state, idxFromClientX(x));
    e.preventDefault();
  }
  function onUp() {
    dragging = false;
    document.body.style.userSelect = "";
  }

  track.addEventListener("mousedown", e => {
    dragging = true;
    document.body.style.userSelect = "none";
    update(state, idxFromClientX(e.clientX));
  });
  track.addEventListener("touchstart", e => {
    dragging = true;
    update(state, idxFromClientX(e.touches[0].clientX));
  }, { passive: false });

  document.addEventListener("mousemove", onMove);
  document.addEventListener("touchmove", onMove, { passive: false });
  document.addEventListener("mouseup", onUp);
  document.addEventListener("touchend", onUp);

  // Keyboard
  knob.addEventListener("keydown", e => {
    let delta = 0;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -1;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = 1;
    else if (e.key === "PageDown") delta = -10;
    else if (e.key === "PageUp") delta = 10;
    else if (e.key === "Home") delta = -total;
    else if (e.key === "End") delta = total;
    else return;
    e.preventDefault();
    update(state, state.idx + delta);
  });

  // Initial render at the latest chapter so the user sees a populated UI.
  update(state, total - 1);
}

// ---------- bootstrap ---------------------------------------------------

(async () => {
  try {
    const data = await loadAll();
    const idx = buildIndex(data);
    setRegimeMarkers(idx);
    const state = { ...idx, idx: idx.chapters.length - 1 };
    attachScrubber(state);
  } catch (err) {
    console.error(err);
    document.body.innerHTML = `
      <div style="max-width:600px; margin:60px auto; padding:24px;
                  font-family:sans-serif; color:#b00;">
        <h1>Failed to load data</h1>
        <p>${escapeHTML(err.message)}</p>
        <p>Make sure you're serving this from the repo root over HTTP
           (e.g. <code>python3 -m http.server</code>) so the
           <code>data/derived/*.json</code> files are reachable.</p>
      </div>
    `;
  }
})();

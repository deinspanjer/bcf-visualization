/* =====================================================================
   BCF mobile prototype — main App.
   ===================================================================== */

const PREF_KEYS = {
  bookmark: "bcf:bookmark",
  speed: "bcf:speed",
  zoom: "bcf:timeline-zoom",
  mode: "bcf:mode",
  onRoll: "bcf:on-roll",
  tapToPause: "bcf:tap-to-pause",
  haptics: "bcf:haptics",
  helpSeen: "bcf:help-seen",
};

const DEFAULT_PREFS = {
  speed: 1,
  zoom: 1,
  mode: "playthrough",
  onRoll: "cinematic",
  tapToPause: true,
  haptics: true,
};

function loadPrefs() {
  const get = (k, fallback) => {
    try {
      const v = localStorage.getItem(k);
      return v == null ? fallback : v;
    } catch { return fallback; }
  };
  return {
    speed: Number(get(PREF_KEYS.speed, DEFAULT_PREFS.speed)) || 1,
    zoom: Number(get(PREF_KEYS.zoom, DEFAULT_PREFS.zoom)) || 1,
    mode: get(PREF_KEYS.mode, DEFAULT_PREFS.mode),
    onRoll: get(PREF_KEYS.onRoll, DEFAULT_PREFS.onRoll),
    tapToPause: get(PREF_KEYS.tapToPause, "true") === "true",
    haptics: get(PREF_KEYS.haptics, "true") === "true",
    helpSeen: get(PREF_KEYS.helpSeen, "false") === "true",
  };
}
function savePref(key, value) {
  try { localStorage.setItem(key, String(value)); } catch {}
}
function loadBookmark() {
  try {
    const v = Number(localStorage.getItem(PREF_KEYS.bookmark));
    return Number.isFinite(v) ? v : 0;
  } catch { return 0; }
}
function saveBookmark(v) {
  savePref(PREF_KEYS.bookmark, Math.round(v));
}

/* Word-position advancement: ~600 words per real second at 1× speed. */
const PLAY_RATE = 600;

function App() {
  const [data, setData] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [loadingStatus, setLoadingStatus] = React.useState("");

  const [wordPos, setWordPos] = React.useState(0);
  const wordPosRef = React.useRef(0);
  const [playing, setPlaying] = React.useState(false);
  const [prefs, setPrefsState] = React.useState(loadPrefs());
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [infoOpen, setInfoOpen] = React.useState(false);
  const [helpOpen, setHelpOpen] = React.useState(false);
  const [chromeHidden, setChromeHidden] = React.useState(false);
  const [isLandscape, setIsLandscape] = React.useState(window.matchMedia("(orientation: landscape)").matches);

  // Sync wordPosRef whenever wordPos changes
  React.useEffect(() => { wordPosRef.current = wordPos; }, [wordPos]);

  // Sync prefs globally so haptic() respects current setting
  React.useEffect(() => { window.__bcfPrefs = prefs; }, [prefs]);

  // Load data on mount
  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const d = await window.loadData(setLoadingStatus);
        if (!alive) return;
        setData(d);
        // Initial bookmark — clamp to total
        const bm = window.clamp(loadBookmark(), 0, d.totalWords - 1);
        setWordPos(bm);
        wordPosRef.current = bm;
        // Surface help on first run
        if (!prefs.helpSeen) setHelpOpen(true);
      } catch (err) {
        if (alive) setError(err.message || String(err));
      }
    })();
    return () => { alive = false; };
  }, []);

  // Orientation listener
  React.useEffect(() => {
    const mq = window.matchMedia("(orientation: landscape)");
    const update = () => setIsLandscape(mq.matches);
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);

  // Animation loop
  React.useEffect(() => {
    if (!playing || !data) return;
    let raf, last = performance.now();
    const tick = (now) => {
      const dt = now - last;
      last = now;
      const next = wordPosRef.current + (dt / 1000) * PLAY_RATE * prefs.speed;
      if (next >= data.totalWords - 1) {
        wordPosRef.current = data.totalWords - 1;
        setWordPos(data.totalWords - 1);
        setPlaying(false);
        saveBookmark(data.totalWords - 1);
        return;
      }
      wordPosRef.current = next;
      setWordPos(next);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, prefs.speed, data]);

  // Periodically persist bookmark
  React.useEffect(() => {
    const id = setInterval(() => saveBookmark(wordPosRef.current), 1500);
    return () => clearInterval(id);
  }, []);

  // Landscape chrome auto-hide
  React.useEffect(() => {
    if (!isLandscape || !playing) { setChromeHidden(false); return; }
    const id = setTimeout(() => setChromeHidden(true), window.GestureConstants.CHROME_AUTOHIDE);
    return () => clearTimeout(id);
  }, [isLandscape, playing, wordPos]);

  // Helpers
  const setPrefs = (patch) => {
    setPrefsState(p => {
      const next = { ...p, ...patch };
      if (patch.speed != null) savePref(PREF_KEYS.speed, next.speed);
      if (patch.zoom != null) savePref(PREF_KEYS.zoom, next.zoom);
      if (patch.mode != null) savePref(PREF_KEYS.mode, next.mode);
      if (patch.onRoll != null) savePref(PREF_KEYS.onRoll, next.onRoll);
      if (patch.tapToPause != null) savePref(PREF_KEYS.tapToPause, next.tapToPause);
      if (patch.haptics != null) savePref(PREF_KEYS.haptics, next.haptics);
      return next;
    });
  };

  const togglePlay = React.useCallback(() => setPlaying(p => !p), []);
  const scrubTo = React.useCallback((wp) => {
    if (!data) return;
    const v = window.clamp(wp, 0, data.totalWords - 1);
    wordPosRef.current = v; setWordPos(v);
  }, [data]);
  const scrubEnd = React.useCallback(() => { if (data) saveBookmark(wordPosRef.current); }, [data]);
  const cycleSpeed = React.useCallback(() => {
    const order = [0.5, 1, 2, 4];
    setPrefs({ speed: order[(order.indexOf(prefs.speed) + 1) % order.length] });
  }, [prefs.speed]);

  const onSky = React.useMemo(() => ({
    tap: () => {
      // Landscape chrome-hidden: first tap reveals, doesn't pause
      if (isLandscape && chromeHidden) { setChromeHidden(false); return; }
      if (!prefs.tapToPause) return;
      setPlaying(p => !p);
    },
    dblTap: () => {
      // Snap to live edge — the latest non-future roll position. In our
      // prototype, "live edge" is the data's most recent roll word.
      if (!data || !data.rolls.length) return;
      const lastRoll = data.rolls[data.rolls.length - 1];
      scrubTo(lastRoll.wordPosition);
      setPlaying(true);
    },
    swipeStep: (dir) => {
      // Jump ±1 roll based on current playhead
      if (!data) return;
      const idx = window.rollIndexAtOrBeforeWord(data, wordPosRef.current);
      const targetIdx = window.clamp(idx + dir, 0, data.rolls.length - 1);
      scrubTo(data.rolls[targetIdx].wordPosition);
    },
    swipeEnd: () => { saveBookmark(wordPosRef.current); },
  }), [data, prefs.tapToPause, isLandscape, chromeHidden, scrubTo]);

  // Loading / error states
  if (error) {
    return (
      <div className="app is-loading">
        <div className="loading-card">
          <div className="label">Forge curator</div>
          <div className="title">Couldn't load the story data</div>
          <div className="err">{error}</div>
          <div className="err" style={{ marginTop: 10, color: "var(--muted)" }}>
            Run the prototype from the project root so it can fetch <code>data/derived/visualization_facts.json</code>.
          </div>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="app is-loading">
        <div className="loading-card">
          <div className="label">Forge curator</div>
          <div className="title">Loading the catalog…</div>
          <div className="progress" />
          <div className="err" style={{ color: "var(--muted)" }}>{loadingStatus}</div>
        </div>
      </div>
    );
  }

  const activeRoll = window.activeRollAtWord(data, wordPos);
  const chapter = window.chapterAtWord(data, wordPos);

  const transport = {
    playing, toggle: togglePlay,
    chapter, scrubTo, scrubEnd, cycleSpeed,
    speedLabel: prefs.speed === 0.5 ? "½×" : `${prefs.speed}×`,
    openSettings: () => { setSettingsOpen(s => !s); setInfoOpen(false); },
  };

  return (
    <div className="app">
      {isLandscape
        ? <LandscapeF data={data} wordPos={wordPos} activeRoll={activeRoll}
                      prefs={prefs} transport={transport} onSky={onSky}
                      openHelp={() => setHelpOpen(true)}
                      chromeHidden={chromeHidden}
                      openSettings={() => { setSettingsOpen(s => !s); setInfoOpen(false); }}
                      openInfo={() => { setInfoOpen(s => !s); setSettingsOpen(false); }}
                      settingsOpen={settingsOpen} infoOpen={infoOpen}
                      zoom={prefs.zoom} />
        : <PortraitC data={data} wordPos={wordPos} activeRoll={activeRoll}
                     prefs={prefs} transport={transport} onSky={onSky}
                     openHelp={() => setHelpOpen(true)}
                     zoom={prefs.zoom} />
      }

      {settingsOpen && (
        <SettingsFlyout prefs={prefs} setPrefs={setPrefs}
                        onClose={() => setSettingsOpen(false)} />
      )}
      {infoOpen && (
        <InfoFlyout data={data}
                    onOpenHelp={() => { setInfoOpen(false); setHelpOpen(true); }}
                    onClose={() => setInfoOpen(false)} />
      )}
      {helpOpen && (
        <HelpOverlay data={data}
                     onDismiss={() => {
                       setHelpOpen(false);
                       if (!prefs.helpSeen) {
                         setPrefsState(p => ({ ...p, helpSeen: true }));
                         savePref(PREF_KEYS.helpSeen, true);
                       }
                     }} />
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);

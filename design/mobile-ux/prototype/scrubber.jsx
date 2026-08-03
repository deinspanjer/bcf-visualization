/* =====================================================================
   Scrubber components — both portrait MiniRail and landscape CinemaScrub.

   Two density-fighting strategies:
     1. ZOOM (1× / 2× / 4× / 8×) — widens the inner content; auto-pans to
        keep the playhead in view.
     2. BIN-MERGE — at any zoom, dots that would render closer than ~5px
        are collapsed into a single cluster marker whose size scales with
        roll count and whose colour is the dominant outcome. The active
        roll is always drawn as a separate, distinct cyan diamond.

   ===================================================================== */

const MIN_DOT_SPACING_PX = 5;

/* Build cluster bins from a flat rolls list. */
function binRolls(rolls, totalWords, pxWidth, minPx = MIN_DOT_SPACING_PX) {
  if (!rolls.length || pxWidth <= 0) return [];
  const minWords = (minPx / pxWidth) * totalWords;
  const bins = [];
  let cur = null;
  for (const r of rolls) {
    if (!cur || r.wordPosition - cur.firstWord > minWords) {
      if (cur) bins.push(finalizeBin(cur));
      cur = { firstWord: r.wordPosition, rolls: [r], outcomes: {} };
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
  // Midpoint word for visual placement; carry the dominant outcome
  const last = bin.rolls[bin.rolls.length - 1];
  bin.midWord = (bin.firstWord + last.wordPosition) / 2;
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

/* Compute the auto-pan transform that keeps the playhead visible. */
function panOffsetForPlayhead(playheadPctRaw, zoom) {
  // Without pan, playhead at fraction f would render at f * (zoom * 100%)
  // of the viewport. We want it at 50% of the viewport when possible,
  // clamping at the ends so we never reveal blank space.
  if (zoom <= 1) return 0;
  const wantedPct = playheadPctRaw * zoom - 50;
  const maxPct = (zoom - 1) * 100;
  return Math.max(0, Math.min(maxPct, wantedPct));
}

/* Resolve a fraction (of the inner content) from a pointer event. */
function fractionFromPointer(el, e, zoom, panPct) {
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0) return 0;
  const xFracView = (e.clientX - rect.left) / rect.width; // 0..1 in viewport
  const innerFrac = (xFracView + panPct / 100) / zoom;     // 0..1 in inner
  return Math.max(0, Math.min(1, innerFrac));
}

/* === Portrait C: multi-lane mini-rail =================================== */
function MiniRail({ data, wordPos, zoom, onScrub, onScrubEnd }) {
  const railRef = React.useRef(null);
  const [railWidth, setRailWidth] = React.useState(350);

  // Measure
  React.useEffect(() => {
    if (!railRef.current) return;
    const ro = new ResizeObserver(entries => {
      const cr = entries[0]?.contentRect;
      if (cr) setRailWidth(Math.max(50, cr.width));
    });
    ro.observe(railRef.current);
    return () => ro.disconnect();
  }, []);

  // Drag handler
  React.useEffect(() => {
    const el = railRef.current;
    if (!el) return;
    return window.attachRailScrub(el, {
      onScrub: (_f) => null, // we resolve manually so we can account for zoom
      onScrubEnd,
    });
  }, [onScrubEnd]);

  // Override the rail's built-in fraction-from-rect with a zoom-aware version
  React.useEffect(() => {
    const el = railRef.current;
    if (!el) return;
    const onPointer = (e) => {
      if (e.buttons === 0 && e.type !== "pointerdown") return;
      const playheadPctRaw = data.totalWords ? (wordPosRef.current / data.totalWords) * 100 : 0;
      const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
      const innerFrac = fractionFromPointer(el, e, zoom, panPct);
      const target = Math.round(innerFrac * data.totalWords);
      onScrub(target);
    };
    el.addEventListener("pointerdown", onPointer);
    el.addEventListener("pointermove", onPointer);
    return () => {
      el.removeEventListener("pointerdown", onPointer);
      el.removeEventListener("pointermove", onPointer);
    };
  }, [zoom, data, onScrub]);

  // Keep a ref of word position for the handler closure
  const wordPosRef = React.useRef(wordPos);
  wordPosRef.current = wordPos;

  const total = data.totalWords;
  const playheadPctRaw = (wordPos / total) * 100;
  const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
  const activeRoll = window.activeRollAtWord(data, wordPos);

  // Bin at current effective pixel width (railWidth * zoom)
  const bins = React.useMemo(
    () => binRolls(data.rolls, total, railWidth * zoom),
    [data.rolls, total, railWidth, zoom]
  );

  const innerStyle = {
    width: `${zoom * 100}%`,
    transform: `translateX(-${panPct}%)`,
    transition: "transform 220ms ease",
  };

  return (
    <div className="mini-rail" ref={railRef}>
      <div className="mini-rail-inner" style={innerStyle}>
        {/* Chapter ticks lane */}
        <div className="lane chapters">
          {data.chapters.map((c, i) => {
            const pct = (c.wordStart / total) * 100;
            const major = Number(c.num) % 10 === 0 || c.num === "1";
            return <div key={i} className={`ch-tick ${major ? "major" : ""}`} style={{ left: `${pct}%` }} />;
          })}
        </div>

        {/* Rolls + POV bands lane */}
        <div className="lane rolls">
          {data.chapters.map((c, i) => {
            const cls = c.pov === "Joe" ? "mc"
                      : c.pov === "Aisha" ? "aisha"
                      : "other";
            const left = (c.wordStart / total) * 100;
            const width = ((c.wordEnd - c.wordStart) / total) * 100;
            return <div key={i} className={`pov-band ${cls}`} style={{ left: `${left}%`, width: `${width}%` }} />;
          })}

          {/* Binned cluster dots */}
          {bins.map((bin, i) => {
            const pct = (bin.midWord / total) * 100;
            const size = binSize(bin);
            const isMulti = bin.rolls.length > 1;
            return (
              <div key={i}
                   className={`roll-bin ${bin.dominant}`}
                   style={{
                     left: `${pct}%`,
                     top: 8 + (15 - size) / 2,
                     width: size, height: size,
                     boxShadow: isMulti ? "0 0 4px rgba(0,0,0,0.4)" : "none",
                   }}>
                {isMulti && size >= 10 && (
                  <span className="count">{bin.rolls.length}</span>
                )}
              </div>
            );
          })}

          {/* Active roll always drawn as its own marker on top */}
          {activeRoll && (
            <div className="roll-dot active"
                 style={{ left: `${(activeRoll.wordPosition / total) * 100}%` }} />
          )}
        </div>

        {/* Axis lane */}
        <div className="lane axis">
          <div className="axis-bar" />
        </div>

        <div className="playhead" style={{ left: `${playheadPctRaw}%` }} />
      </div>
    </div>
  );
}

/* === Landscape F: compact cinema scrub pill =========================== */
function CinemaScrub({ data, wordPos, zoom, playing, onTogglePlay, onScrub, onScrubEnd, isHidden }) {
  const trackRef = React.useRef(null);
  const [trackWidth, setTrackWidth] = React.useState(200);

  React.useEffect(() => {
    if (!trackRef.current) return;
    const ro = new ResizeObserver(entries => {
      const cr = entries[0]?.contentRect;
      if (cr) setTrackWidth(Math.max(50, cr.width));
    });
    ro.observe(trackRef.current);
    return () => ro.disconnect();
  }, []);

  // Custom pointer handler for zoom-aware fraction resolution
  const wordPosRef = React.useRef(wordPos);
  wordPosRef.current = wordPos;

  React.useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    let captured = false;
    const onDown = (e) => {
      captured = true;
      el.setPointerCapture?.(e.pointerId);
      apply(e);
    };
    const onMove = (e) => { if (captured) apply(e); };
    const onUp = (e) => {
      if (captured) {
        captured = false;
        el.releasePointerCapture?.(e.pointerId);
        onScrubEnd?.();
      }
    };
    function apply(e) {
      const playheadPctRaw = data.totalWords ? (wordPosRef.current / data.totalWords) * 100 : 0;
      const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
      const innerFrac = fractionFromPointer(el, e, zoom, panPct);
      const target = Math.round(innerFrac * data.totalWords);
      onScrub(target);
    }
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onUp);
    };
  }, [zoom, data, onScrub, onScrubEnd]);

  const total = data.totalWords;
  const playheadPctRaw = (wordPos / total) * 100;
  const panPct = panOffsetForPlayhead(playheadPctRaw, zoom);
  const activeIdx = window.rollIndexAtOrBeforeWord(data, wordPos);

  // Bin to whatever the inner-effective width is
  const bins = React.useMemo(
    () => binRolls(data.rolls, total, trackWidth * zoom),
    [data.rolls, total, trackWidth, zoom]
  );

  const innerStyle = {
    width: `${zoom * 100}%`,
    transform: `translateX(-${panPct}%)`,
    transition: "transform 220ms ease",
  };

  return (
    <div className={`cinema-scrub landscape-only ${isHidden ? "is-hidden" : ""}`}>
      <button className="fab-play sm" onClick={onTogglePlay} aria-label="Play / pause">
        <PlayIcon paused={!playing} size={14} />
      </button>
      <span className="roll-count">{activeIdx + 1} / {data.rolls.length}</span>
      <div className="scrub-track" ref={trackRef}>
        <div className="scrub-track-inner" style={innerStyle}>
          <div className="scrub-rail" />
          <div className="scrub-progress" style={{ width: `${playheadPctRaw}%` }} />
          {bins.map((bin, i) => {
            const p = (bin.midWord / total) * 100;
            return <div key={i} className={`scrub-roll ${bin.dominant}`} style={{ left: `${p}%` }} />;
          })}
          <div className="scrub-thumb" style={{ left: `${playheadPctRaw}%` }} />
        </div>
      </div>
    </div>
  );
}

window.MiniRail = MiniRail;
window.CinemaScrub = CinemaScrub;

/* =====================================================================
   Panels: SettingsFlyout, InfoFlyout, HelpOverlay, FieldLog.
   ===================================================================== */

function PlayIcon({ paused, color = "#03080d", size = 18 }) {
  if (paused) return <svg width={size} height={size} viewBox="0 0 14 14"><path d="M3 11V3l8 4-8 4z" fill={color}/></svg>;
  return <svg width={size} height={size} viewBox="0 0 14 14"><rect x="3" y="3" width="3" height="8" fill={color}/><rect x="8" y="3" width="3" height="8" fill={color}/></svg>;
}

function GearIcon({ size = 18 }) {
  // Proper cog (Feather "settings"): notched circle with toothed outline,
  // not a sun/brightness ray pattern.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}
function InfoIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3">
      <circle cx="9" cy="9" r="7"/>
      <path d="M9 8v4M9 5.5v.5" strokeLinecap="round"/>
    </svg>
  );
}
function HelpIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4">
      <circle cx="9" cy="9" r="7"/>
      <path d="M7 7a2 2 0 1 1 3 1.7c-.7.4-1 .8-1 1.5M9 12.5v.5" strokeLinecap="round"/>
    </svg>
  );
}

function SettingsFlyout({ prefs, setPrefs, onClose }) {
  return (
    <>
      <div className="flyout-backdrop" onClick={onClose} />
      <div className="flyout" role="dialog" aria-label="Settings">
        <h4>Settings</h4>

        <div className="flyout-divider" />

        <div className="group">
          <div className="group-label">View mode</div>
          <Seg value={prefs.mode}
               options={[["playthrough","Playthrough"],["details","Details"]]}
               onChange={v => setPrefs({ mode: v })}/>
        </div>

        <div className="group">
          <div className="group-label">On roll</div>
          <Seg value={prefs.onRoll}
               options={[["cinematic","Cinematic"],["skip","Skip"],["pause","Pause"]]}
               onChange={v => setPrefs({ onRoll: v })}/>
        </div>

        <div className="group">
          <div className="group-label">Speed</div>
          <Seg value={String(prefs.speed)}
               options={[["0.5","½×"],["1","1×"],["2","2×"],["4","4×"]]}
               onChange={v => setPrefs({ speed: Number(v) })}/>
        </div>

        <div className="group">
          <div className="group-label">Timeline zoom</div>
          <Seg value={String(prefs.zoom)}
               options={[["1","1×"],["2","2×"],["4","4×"],["8","8×"]]}
               onChange={v => setPrefs({ zoom: Number(v) })}/>
        </div>

        <div className="group">
          <div className="group-label">Comfort</div>
          <div className="row"><span>Tap sky to pause</span>
            <span className="val" onClick={() => setPrefs({ tapToPause: !prefs.tapToPause })}>
              {prefs.tapToPause ? "On" : "Off"}
            </span>
          </div>
          <div className="row"><span>Haptics</span>
            <span className="val" onClick={() => setPrefs({ haptics: !prefs.haptics })}>
              {prefs.haptics ? "On" : "Off"}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

function InfoFlyout({ data, onOpenHelp, onClose }) {
  return (
    <>
      <div className="flyout-backdrop" onClick={onClose} />
      <div className="flyout" role="dialog" aria-label="About">
        <h4>About this visualization</h4>
        <h2>Brockton's Celestial Forge</h2>
        <div className="credit">
          Worm × Jumpchain crossover by <b>LordRoustabout</b>
        </div>

        <div className="flyout-divider" />

        <div className="group">
          <div className="group-label">Read the source</div>
          <div className="source-row">
            <a href="https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks" target="_blank" rel="noopener noreferrer">SV ↗</a>
            <a href="https://www.fanfiction.net/s/13690963/" target="_blank" rel="noopener noreferrer">FF ↗</a>
            <a href="https://archiveofourown.org/works/22381660" target="_blank" rel="noopener noreferrer">AO3 ↗</a>
          </div>
        </div>

        <div className="group">
          <div className="group-label">Dataset</div>
          <div style={{ fontSize: 11, color: "var(--ink)", lineHeight: 1.45 }}>
            <div>{data?.rolls?.length || 0} rolls · {data?.chapters?.length || 0} chapters</div>
            <div style={{ color: "var(--muted)" }}>{window.fmtWords(data?.totalWords || 0)} words</div>
          </div>
        </div>

        <button className="full-btn" onClick={onOpenHelp}>
          <span>Gestures &amp; help</span><span>↗</span>
        </button>
      </div>
    </>
  );
}

function HelpOverlay({ data, onDismiss }) {
  return (
    <div className="help-overlay" role="dialog" aria-label="Help">
      <header>
        <div>
          <div className="label">Help &amp; credits</div>
          <h1>Reading on mobile</h1>
        </div>
        <button className="close" onClick={onDismiss} aria-label="Close">×</button>
      </header>

      <div className="credit-block">
        <div className="title">Brockton's Celestial Forge</div>
        <div className="by">by <b>LordRoustabout</b> · Worm × Jumpchain</div>
        <div className="source-row">
          <a href="https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks" target="_blank" rel="noopener noreferrer">SV ↗</a>
          <a href="https://www.fanfiction.net/s/13690963/" target="_blank" rel="noopener noreferrer">FF ↗</a>
          <a href="https://archiveofourown.org/works/22381660" target="_blank" rel="noopener noreferrer">AO3 ↗</a>
        </div>
      </div>

      <h3>How to play</h3>
      <div className="gestures">
        <span className="ico">👆</span><span><b>Tap sky</b> — pause / resume.</span>
        <span className="ico">👆👆</span><span><b>Double-tap sky</b> — snap to live edge.</span>
        <span className="ico">👈👉</span><span><b>Swipe sky</b> — scrub by roll (haptic on each).</span>
        <span className="ico">↔</span><span><b>Drag scrubber</b> — direct scrub by word.</span>
        <span className="ico">🔄</span><span><b>Rotate</b> — switches portrait ↔ landscape; state persists.</span>
        <span className="ico">⚙</span><span><b>Settings</b> — speed, on-roll behavior, comfort.</span>
        <span className="ico">ⓘ</span><span><b>About</b> — story credits, source links, gestures.</span>
      </div>

      <h3>Heads-up</h3>
      <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
        Your bookmark, speed, and preferences survive a refresh — pick
        up where you left off. Haptics and tap-to-pause can be disabled
        in Settings → Comfort.
      </div>

      <button className="got-it" onClick={onDismiss}>Got it — read on</button>
    </div>
  );
}

function FieldLog({ data, wordPos }) {
  const idx = window.rollIndexAtOrBeforeWord(data, wordPos);
  const live = idx >= 0 ? data.rolls[idx] : null;
  const recent = window.recentRolls(data, wordPos, 6).slice(live ? 1 : 0);

  return (
    <div className="field-log">
      <h3>
        <span>Field Log · {live?.constellation ? live.constellation : "—"}</span>
        <span className="count">{idx + 1} of {data.rolls.length}</span>
      </h3>

      <div className="log-list">
        {live && (
          <div className="live">
            <div className="row1">
              <span>◢ ROLL {live.rollNumber ?? "—"} · {live.outcome}</span>
              <span>{live.perkCost != null ? `${live.perkCost} CP` : "—"}</span>
            </div>
            <div className="name">{live.perkName || live.constellation || "—"}</div>
            <div className="sub">
              {live.perkJump ? live.perkJump : ""}
              {live.evidenceQuote ? <>{live.perkJump ? " · " : ""}<em>"{truncate(live.evidenceQuote, 100)}"</em></> : null}
            </div>
          </div>
        )}
        {recent.map((r, i) => (
          <div key={i} className="entry">
            <div className="row1">
              <span>Ch {r.chapterNum}</span>
              <span>{r.outcome === "hit" ? `${r.perkCost ?? "—"} CP` : r.outcome}</span>
            </div>
            <div className="name">{r.perkName || r.constellation || "—"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Seg({ value, options, onChange }) {
  return (
    <div className="seg">
      {options.map(([v, label]) => (
        <button key={v}
                className={value === v ? "is-active" : ""}
                onClick={() => onChange(v)}>{label}</button>
      ))}
    </div>
  );
}

function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1).trim() + "…" : s;
}

Object.assign(window, {
  SettingsFlyout, InfoFlyout, HelpOverlay, FieldLog,
  PlayIcon, GearIcon, InfoIcon, HelpIcon,
});

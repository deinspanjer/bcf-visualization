/* =====================================================================
   Layout — single component that adapts to portrait (C) or landscape
   (F) via CSS @media. Same children render in both; layout differs.
   ===================================================================== */

function PortraitC({ data, wordPos, activeRoll, prefs, transport, onSky, openHelp, zoom }) {
  return (
    <>
      {/* Top chip cluster */}
      <div className="top-cluster portrait-only">
        <div style={{ display: "flex", gap: 8 }}>
          <div className="chip">CH {transport.chapter?.num} · {window.fmtWords(wordPos)}w</div>
          {activeRoll && (
            <div className="chip amber">◢ R{activeRoll.rollNumber ?? "—"}</div>
          )}
        </div>
        <button className="icon-btn round compact" onClick={openHelp} aria-label="Help">
          <HelpIcon size={16} />
        </button>
      </div>

      {/* Sky takes flex 1 60% */}
      <Sky activeRoll={activeRoll}
           onTap={onSky.tap}
           onDoubleTap={onSky.dblTap}
           onSwipeStep={onSky.swipeStep}
           onSwipeEnd={onSky.swipeEnd} />

      {/* Bottom dock — mini-rail + transport */}
      <div className="dock portrait-only">
        <div className="dock-transport">
          <button className="fab-play md" onClick={transport.toggle} aria-label="Play / pause">
            <PlayIcon paused={!transport.playing} />
          </button>
          <div className="now">
            <div className="meta">{window.fmtWords(wordPos)} / {window.fmtWords(data.totalWords)} words · {Math.round(wordPos / data.totalWords * 100)}%</div>
            <div className="title">{transport.chapter?.title || "—"}</div>
          </div>
          <button className="icon-btn compact" onClick={transport.cycleSpeed}>{transport.speedLabel}</button>
          <button className="icon-btn compact" onClick={transport.openSettings} aria-label="Settings">
            <GearIcon size={16} />
          </button>
        </div>
        <MiniRail data={data} wordPos={wordPos} zoom={zoom}
                  onScrub={transport.scrubTo}
                  onScrubEnd={transport.scrubEnd}/>
        <div className="hint-row">
          <span>tap rail → jump · drag → scrub</span>
          <span>{zoom > 1 ? `${zoom}× zoom · ` : ""}{transport.chapter?.pov} POV</span>
        </div>
      </div>
    </>
  );
}

function LandscapeF({ data, wordPos, activeRoll, prefs, transport, onSky, openHelp, chromeHidden, openSettings, openInfo, settingsOpen, infoOpen, zoom }) {
  return (
    <>
      {/* Sky region holds the top chips and the auto-hide scrub */}
      <div style={{ position: "relative", flex: "1 1 auto", minWidth: 0, display: "flex" }}>
        <Sky activeRoll={activeRoll}
             onTap={onSky.tap}
             onDoubleTap={onSky.dblTap}
             onSwipeStep={onSky.swipeStep}
             onSwipeEnd={onSky.swipeEnd} />

        <div className="top-cluster landscape-only">
          <div style={{ display: "flex", gap: 8 }}>
            <div className="chip">CH {transport.chapter?.num}</div>
            {activeRoll && (
              <div className="chip amber">◢ R{activeRoll.rollNumber ?? "—"}</div>
            )}
          </div>
          <button className="icon-btn round compact" onClick={openHelp} aria-label="Help">
            <HelpIcon size={16} />
          </button>
        </div>

        {/* Auto-hide cinema scrub — owns its own play button */}
        <CinemaScrub data={data} wordPos={wordPos} zoom={zoom}
                     playing={transport.playing}
                     onTogglePlay={transport.toggle}
                     onScrub={transport.scrubTo}
                     onScrubEnd={transport.scrubEnd}
                     isHidden={chromeHidden} />
      </div>

      {/* Right rail */}
      <div className="rail landscape-only">
        <FieldLog data={data} wordPos={wordPos} />
        <div className="control-dock">
          <div>
            <div className="group-label" style={{ marginBottom: 8 }}>Quick actions</div>
            <div className="dock-grid">
              <button className={`dock-btn ${settingsOpen ? "is-active" : ""}`} onClick={openSettings}>
                <GearIcon />
                <span>Settings</span>
              </button>
              <button className={`dock-btn ${infoOpen ? "is-active" : ""}`} onClick={openInfo}>
                <InfoIcon />
                <span>About</span>
              </button>
            </div>
          </div>
          <div className="dock-status">
            <span>{prefs.speed}× · {prefs.mode}</span>
            <span className="val">{transport.chapter?.pov || "Joe"} POV</span>
          </div>
        </div>
      </div>
    </>
  );
}

window.PortraitC = PortraitC;
window.LandscapeF = LandscapeF;

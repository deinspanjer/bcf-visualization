// Shared tiny UI atoms used by the mockup mocks.

function PlayIcon({ size = 14, paused = false, color = "#03080d" }) {
  if (paused) {
    return (
      <svg width={size} height={size} viewBox="0 0 14 14"><path d="M3 11V3l8 4-8 4z" fill={color}/></svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 14 14"><rect x="3" y="3" width="3" height="8" fill={color}/><rect x="8" y="3" width="3" height="8" fill={color}/></svg>
  );
}

function CornerFrame({ color = "rgba(92,244,255,0.30)", inset = 8 }) {
  const c = {
    position: "absolute",
    width: 14, height: 14,
    borderColor: color,
    borderStyle: "solid",
    borderWidth: 0,
    pointerEvents: "none",
  };
  return (
    <>
      <span style={{ ...c, top: inset, left: inset, borderTopWidth: 1, borderLeftWidth: 1 }} />
      <span style={{ ...c, top: inset, right: inset, borderTopWidth: 1, borderRightWidth: 1 }} />
      <span style={{ ...c, bottom: inset, left: inset, borderBottomWidth: 1, borderLeftWidth: 1 }} />
      <span style={{ ...c, bottom: inset, right: inset, borderBottomWidth: 1, borderRightWidth: 1 }} />
    </>
  );
}

function Chip({ children, color = "rgba(92,244,255,0.55)", bg = "rgba(5,29,38,0.78)", style }) {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "5px 10px",
      background: bg,
      border: `1px solid ${color}`,
      borderRadius: 999,
      color: "#e8fdff",
      fontFamily: "var(--mono)",
      fontSize: 10,
      letterSpacing: 0.5,
      textTransform: "uppercase",
      backdropFilter: "blur(6px)",
      WebkitBackdropFilter: "blur(6px)",
      ...style,
    }}>
      {children}
    </div>
  );
}

function FabPlay({ paused = false, size = 56, color = "#5cf4ff", style }) {
  return (
    <button style={{
      width: size, height: size, borderRadius: "50%",
      border: "none",
      background: color,
      boxShadow: "0 0 24px rgba(92,244,255,0.55), 0 8px 24px rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center",
      cursor: "pointer",
      ...style,
    }}>
      <PlayIcon paused={paused} size={Math.round(size * 0.34)} />
    </button>
  );
}

function DotStream({ count = 24, active = 9, width = "100%", height = 16, color = "#5cf4ff" }) {
  // miniature roll markers — diamonds on a hairline
  return (
    <div style={{ position: "relative", width, height }}>
      <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 1, background: "rgba(92,244,255,0.18)" }}/>
      {Array.from({ length: count }).map((_, i) => {
        const pct = (i + 0.5) / count * 100;
        const isActive = i === active;
        return (
          <div key={i} style={{
            position: "absolute",
            left: `${pct}%`,
            top: "50%",
            transform: "translate(-50%, -50%) rotate(45deg)",
            width: isActive ? 7 : 4,
            height: isActive ? 7 : 4,
            background: isActive ? color : "rgba(92,244,255,0.45)",
            boxShadow: isActive ? `0 0 8px ${color}` : "none",
          }}/>
        );
      })}
    </div>
  );
}

function Playhead({ left = "32%", color = "#5cf4ff" }) {
  return (
    <div style={{
      position: "absolute", top: 0, bottom: 0, left,
      width: 1, background: color,
      boxShadow: `0 0 6px ${color}`,
      pointerEvents: "none",
    }}>
      <div style={{
        position: "absolute", top: -2, left: "50%", transform: "translateX(-50%)",
        width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 10px ${color}`,
      }}/>
      <div style={{
        position: "absolute", bottom: -2, left: "50%", transform: "translateX(-50%)",
        width: 6, height: 6, borderRadius: "50%", background: color, boxShadow: `0 0 10px ${color}`,
      }}/>
    </div>
  );
}

// A miniature multi-track scrubber, scaled to fit any width.
function MultiTrackScrubber({ height = 110, playheadLeft = "34%", showLabels = true }) {
  return (
    <div style={{
      position: "relative", height,
      background: "rgba(3,8,13,0.55)",
      border: "1px solid rgba(92,244,255,0.18)",
      borderRadius: 8,
      padding: "8px 10px",
      overflow: "hidden",
    }}>
      {/* Dates */}
      <Track label="dates" height={14} showLabels={showLabels}>
        <Ticks count={9} color="rgba(154,215,223,0.45)" major={[2, 5, 7]} />
        <div style={{ position: "absolute", left: "20%", top: 4, fontSize: 7, color: "rgba(154,215,223,0.75)", fontFamily: "var(--mono)" }}>2011</div>
        <div style={{ position: "absolute", left: "55%", top: 4, fontSize: 7, color: "rgba(154,215,223,0.55)", fontFamily: "var(--mono)" }}>JUN</div>
      </Track>
      {/* Chapters */}
      <Track label="ch" height={8} showLabels={showLabels}>
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, rgba(92,244,255,0.05), rgba(92,244,255,0.1) 50%, rgba(92,244,255,0.04))" }}/>
        {[10, 22, 34, 46, 58, 70, 82].map((p, i) => (
          <div key={i} style={{ position: "absolute", top: 0, bottom: 0, left: `${p}%`, width: 1, background: "rgba(92,244,255,0.35)" }}/>
        ))}
      </Track>
      {/* POV bands */}
      <Track label="pov" height={10} showLabels={showLabels}>
        <div style={{ position: "absolute", left: "0%", width: "20%", top: 2, bottom: 2, background: "rgba(92,244,255,0.22)", borderRadius: 1 }}/>
        <div style={{ position: "absolute", left: "20%", width: "8%", top: 5, bottom: 1, background: "rgba(180,148,255,0.30)" }}/>
        <div style={{ position: "absolute", left: "28%", width: "40%", top: 2, bottom: 2, background: "rgba(92,244,255,0.22)" }}/>
        <div style={{ position: "absolute", left: "68%", width: "10%", top: 2, bottom: 2, background: "rgba(123,255,189,0.30)" }}/>
        <div style={{ position: "absolute", left: "78%", width: "22%", top: 2, bottom: 2, background: "rgba(92,244,255,0.22)" }}/>
      </Track>
      {/* Rolls — densest band, the heart of the viz */}
      <Track label="rolls" height={32} showLabels={showLabels}>
        {[6, 12, 17, 22, 27, 31, 34, 40, 46, 52, 58, 64, 70, 75, 80, 85, 90].map((p, i) => {
          const isActive = Math.abs(p - 34) < 2;
          return (
            <div key={i} style={{
              position: "absolute",
              left: `${p}%`, top: "30%",
              transform: "translate(-50%, -50%) rotate(45deg)",
              width: isActive ? 8 : 5, height: isActive ? 8 : 5,
              background: isActive ? "#5cf4ff" : (i % 3 === 0 ? "rgba(123,255,189,0.70)" : "rgba(245,210,123,0.65)"),
              boxShadow: isActive ? "0 0 8px #5cf4ff" : "none",
            }}/>
          );
        })}
        {/* miss markers below */}
        {[15, 28, 42, 57, 72, 86].map((p, i) => (
          <div key={`m${i}`} style={{
            position: "absolute", left: `${p}%`, bottom: 2,
            width: 1.5, height: 4, background: "rgba(255,138,168,0.55)",
          }}/>
        ))}
      </Track>
      {/* Axis */}
      <Track label="axis" height={12} showLabels={showLabels}>
        <Ticks count={12} color="rgba(92,244,255,0.25)" />
        <div style={{ position: "absolute", bottom: 0, left: 0, width: "30%", height: 2, background: "rgba(245,210,123,0.40)" }}/>
        <div style={{ position: "absolute", bottom: 0, left: "30%", width: "35%", height: 2, background: "rgba(180,148,255,0.40)" }}/>
        <div style={{ position: "absolute", bottom: 0, left: "65%", width: "35%", height: 2, background: "rgba(255,138,168,0.40)" }}/>
      </Track>
      <Playhead left={playheadLeft} />
    </div>
  );
}

function Track({ label, height, showLabels, children }) {
  return (
    <div style={{ display: "flex", alignItems: "stretch", marginBottom: 3 }}>
      {showLabels && (
        <div style={{
          width: 26, fontSize: 7, fontFamily: "var(--mono)", color: "rgba(154,215,223,0.55)",
          textTransform: "uppercase", letterSpacing: 0.5, alignSelf: "center", flexShrink: 0,
        }}>{label}</div>
      )}
      <div style={{ position: "relative", flex: 1, height }}>
        {children}
      </div>
    </div>
  );
}

function Ticks({ count, color, major = [] }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => {
        const pct = (i / (count - 1)) * 100;
        const isMajor = major.includes(i);
        return (
          <div key={i} style={{
            position: "absolute", left: `${pct}%`, top: 0, bottom: 0,
            width: 1, background: color, opacity: isMajor ? 1 : 0.5,
          }}/>
        );
      })}
    </>
  );
}

Object.assign(window, { PlayIcon, CornerFrame, Chip, FabPlay, DotStream, Playhead, MultiTrackScrubber });

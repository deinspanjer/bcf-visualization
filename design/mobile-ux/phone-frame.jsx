// Lightweight phone frame for design boards.
// Portrait: 390x844; landscape: 844x390. Includes status bar + home indicator.

const PHONE_PORTRAIT = { w: 390, h: 844 };
const PHONE_LANDSCAPE = { w: 844, h: 390 };

function PhoneFrame({ orientation = "portrait", children, label, time = "9:41" }) {
  const isLand = orientation === "landscape";
  const w = isLand ? PHONE_LANDSCAPE.w : PHONE_PORTRAIT.w;
  const h = isLand ? PHONE_LANDSCAPE.h : PHONE_PORTRAIT.h;

  const bezelStyle = {
    width: `${w}px`,
    height: `${h}px`,
    background: "#000",
    borderRadius: isLand ? "48px / 48px" : "48px",
    boxShadow: "0 30px 80px rgba(0,0,0,0.55), inset 0 0 0 2px rgba(92,244,255,0.10)",
    padding: "10px",
    position: "relative",
    overflow: "hidden",
    fontFamily: "var(--sans)",
  };
  const screenStyle = {
    width: "100%",
    height: "100%",
    background: "var(--void-deep)",
    borderRadius: isLand ? "38px" : "38px",
    overflow: "hidden",
    position: "relative",
    isolation: "isolate",
  };

  return (
    <div style={bezelStyle} data-screen-label={label}>
      <div style={screenStyle}>
        {/* Dynamic Island / notch */}
        {isLand ? (
          <div style={{
            position: "absolute", left: 18, top: "50%", transform: "translateY(-50%)",
            width: 32, height: 105, background: "#000", borderRadius: 16, zIndex: 10,
          }} />
        ) : (
          <div style={{
            position: "absolute", top: 12, left: "50%", transform: "translateX(-50%)",
            width: 105, height: 32, background: "#000", borderRadius: 16, zIndex: 10,
          }} />
        )}

        {/* Status bar */}
        <StatusBar orientation={orientation} time={time} />

        {/* Screen content */}
        <div style={{
          position: "absolute",
          inset: 0,
          paddingTop: isLand ? 0 : 50,
          paddingBottom: isLand ? 0 : 22,
          paddingLeft: isLand ? 60 : 0,
          paddingRight: isLand ? 24 : 0,
        }}>
          {children}
        </div>

        {/* Home indicator */}
        {isLand ? (
          <div style={{
            position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)",
            width: 4, height: 110, background: "rgba(255,255,255,0.65)", borderRadius: 4, zIndex: 11,
          }} />
        ) : (
          <div style={{
            position: "absolute", bottom: 6, left: "50%", transform: "translateX(-50%)",
            width: 110, height: 4, background: "rgba(255,255,255,0.65)", borderRadius: 4, zIndex: 11,
          }} />
        )}
      </div>
    </div>
  );
}

function StatusBar({ orientation, time }) {
  const isLand = orientation === "landscape";
  const baseStyle = {
    position: "absolute",
    color: "#fff",
    fontFamily: "var(--sans)",
    fontWeight: 600,
    fontSize: 13,
    letterSpacing: 0.2,
    zIndex: 9,
    pointerEvents: "none",
  };
  if (isLand) {
    return (
      <>
        <div style={{ ...baseStyle, top: 14, left: 60, fontSize: 11 }}>{time}</div>
        <div style={{ ...baseStyle, top: 14, right: 22, fontSize: 11, display: "flex", gap: 6, alignItems: "center" }}>
          <SignalBars /> <Wifi /> <Battery />
        </div>
      </>
    );
  }
  return (
    <>
      <div style={{ ...baseStyle, top: 16, left: 28 }}>{time}</div>
      <div style={{ ...baseStyle, top: 16, right: 22, display: "flex", gap: 6, alignItems: "center" }}>
        <SignalBars /> <Wifi /> <Battery />
      </div>
    </>
  );
}

function SignalBars() {
  return (
    <svg width="17" height="11" viewBox="0 0 17 11" fill="#fff">
      <rect x="0" y="7" width="3" height="4" rx="0.5" />
      <rect x="4.5" y="5" width="3" height="6" rx="0.5" />
      <rect x="9" y="2.5" width="3" height="8.5" rx="0.5" />
      <rect x="13.5" y="0" width="3" height="11" rx="0.5" />
    </svg>
  );
}
function Wifi() {
  return (
    <svg width="16" height="11" viewBox="0 0 16 11" fill="#fff">
      <path d="M8 11l2-2.5a2 2 0 0 0-4 0L8 11zm0-5a5 5 0 0 1 3.6 1.5l1.4-1.5a7 7 0 0 0-10 0L4.4 7.5A5 5 0 0 1 8 6zm0-4a9 9 0 0 1 6.5 2.6L16 3.1a11 11 0 0 0-16 0l1.5 1.5A9 9 0 0 1 8 2z"/>
    </svg>
  );
}
function Battery() {
  return (
    <svg width="27" height="11" viewBox="0 0 27 11" fill="none">
      <rect x="0.5" y="0.5" width="22" height="10" rx="2.5" stroke="#fff" opacity="0.55"/>
      <rect x="2" y="2" width="19" height="7" rx="1" fill="#fff"/>
      <rect x="24" y="3.5" width="1.5" height="4" rx="0.75" fill="#fff" opacity="0.55"/>
    </svg>
  );
}

Object.assign(window, { PhoneFrame, PHONE_PORTRAIT, PHONE_LANDSCAPE });

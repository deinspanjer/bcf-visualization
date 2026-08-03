// ── Portrait mockups ────────────────────────────────────────────────────
// Each Mockup is a static design comp: just a portrait-PhoneFrame wrapper
// with the proposed UI painted on top of a SkyBackground.

// A. Sky-First HUD
// Sky fills viewport. Slim heads-up ribbon at top with chapter + rolls dot
// stream. Persistent play-pause FAB anchored bottom-right. "Tap viewport
// to pause" hint chip appears briefly on first interaction.
function MockA_SkyFirstHUD() {
  return (
    <PhoneFrame orientation="portrait" label="A — Sky-first HUD">
      <div style={{ position: "absolute", inset: 0 }}>
        <SkyBackground />
        <CornerFrame inset={12} />

        {/* Heads-up ribbon */}
        <div style={{
          position: "absolute", top: 12, left: 12, right: 12,
          background: "rgba(5,29,38,0.78)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
          border: "1px solid rgba(92,244,255,0.30)",
          borderRadius: 12,
          padding: "8px 10px 10px",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.75)", letterSpacing: 0.5, textTransform: "uppercase" }}>
              CH 17 · Joe POV
            </div>
            <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(245,210,123,0.85)" }}>
              ◢ ROLL #42
            </div>
            <ChevronDown />
          </div>
          <div style={{ position: "relative", height: 16 }}>
            <DotStream count={28} active={11} />
            <Playhead left="42%" />
          </div>
        </div>

        {/* Active narrative card peek (top of sky area) */}
        <div style={{
          position: "absolute", top: 92, left: 12, right: 12,
          padding: "10px 12px",
          background: "rgba(5,29,38,0.55)",
          border: "1px solid rgba(123,255,189,0.30)",
          borderRadius: 10,
        }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--green)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 4 }}>
            NEW CONSTELLATION
          </div>
          <div style={{ fontFamily: "var(--serif)", fontSize: 17, lineHeight: 1.2 }}>
            Tinkering ★★ — Heroic
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, fontStyle: "italic" }}>
            "Brockton's plan crystallizes…"
          </div>
        </div>

        {/* Bottom-right FAB cluster — always reachable with thumb */}
        <div style={{ position: "absolute", bottom: 86, right: 14, display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
          <FabPlay paused size={62} />
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <RoundBtn label="½×" />
            <RoundBtn label="1×" active />
            <RoundBtn label="2×" />
          </div>
        </div>

        {/* "Tap viewport to pause" hint */}
        <div style={{
          position: "absolute", bottom: 36, left: "50%", transform: "translateX(-50%)",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <Chip color="rgba(123,255,189,0.45)">↯ Tap sky to pause</Chip>
        </div>
      </div>
    </PhoneFrame>
  );
}

// B. Peek Sheet — full-bleed sky, draggable bottom sheet
function MockB_PeekSheet({ expanded = false }) {
  return (
    <PhoneFrame orientation="portrait" label={`B — Peek sheet${expanded ? " (expanded)" : ""}`}>
      <div style={{ position: "absolute", inset: 0 }}>
        <SkyBackground />
        <CornerFrame inset={12} />

        {/* Minimal chapter chip top-left */}
        <div style={{ position: "absolute", top: 14, left: 14 }}>
          <Chip>Ch 17 · 32%</Chip>
        </div>
        {/* Pause toggle top-right always reachable */}
        <button style={{
          position: "absolute", top: 12, right: 12,
          width: 38, height: 38, borderRadius: "50%",
          background: "rgba(5,29,38,0.78)", border: "1px solid rgba(92,244,255,0.40)",
          backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <PlayIcon paused color="#5cf4ff" size={14} />
        </button>

        {/* When collapsed: 56px peek bar */}
        {!expanded && (
          <div style={{
            position: "absolute", left: 12, right: 12, bottom: 18,
            background: "rgba(5,29,38,0.85)", border: "1px solid rgba(92,244,255,0.30)",
            borderRadius: 14, padding: "10px 12px",
            backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
          }}>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 6 }}>
              <div style={{ width: 36, height: 3, borderRadius: 2, background: "rgba(92,244,255,0.45)" }}/>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <FabPlay paused size={36} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.65)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  CH 17 · ROLL 42 of 137
                </div>
                <div style={{ position: "relative", height: 10, marginTop: 4 }}>
                  <DotStream count={20} active={8} height={10} />
                </div>
              </div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 18, color: "var(--cyan)" }}>↑</div>
            </div>
          </div>
        )}

        {/* When expanded: full multi-track sheet with backdrop dim */}
        {expanded && (
          <>
            <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.55)" }} />
            <div style={{
              position: "absolute", left: 0, right: 0, bottom: 0,
              height: "62%",
              background: "rgba(5,29,38,0.96)",
              borderTop: "1px solid rgba(92,244,255,0.40)",
              borderRadius: "20px 20px 0 0",
              padding: "10px 14px 22px",
              boxShadow: "0 -20px 50px rgba(0,0,0,0.6)",
            }}>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>
                <div style={{ width: 44, height: 4, borderRadius: 2, background: "rgba(92,244,255,0.55)" }}/>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.65)", textTransform: "uppercase", letterSpacing: 0.5 }}>Now playing</div>
                  <div style={{ fontFamily: "var(--serif)", fontSize: 15, marginTop: 2 }}>Chapter 17 — Joe POV</div>
                </div>
                <FabPlay paused size={44} />
              </div>
              <MultiTrackScrubber height={112} playheadLeft="34%" />
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <ControlPill icon="↺" label="½×" />
                <ControlPill icon="▶" label="1×" active />
                <ControlPill icon="↻" label="2×" />
                <ControlPill icon="⤓" label="Jump to roll" wide />
              </div>
              <div style={{ marginTop: 10, display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--dim)", fontFamily: "var(--mono)" }}>
                <span>Roll behavior</span><span style={{ color: "var(--cyan)" }}>Cinematic ▾</span>
              </div>
            </div>
          </>
        )}
      </div>
    </PhoneFrame>
  );
}

// C. Mini-Rail Bottom — sky always visible above a compact scrubber
function MockC_MiniRail() {
  return (
    <PhoneFrame orientation="portrait" label="C — Mini-rail bottom">
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column" }}>
        {/* Sky takes ~60% */}
        <div style={{ position: "relative", flex: "1 1 60%", minHeight: 0 }}>
          <SkyBackground />
          <CornerFrame inset={12} />
          <div style={{ position: "absolute", top: 14, left: 14, display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-start" }}>
            <Chip>Ch 17 · Joe</Chip>
            <Chip color="rgba(245,210,123,0.55)">◢ Roll #42 firing</Chip>
          </div>
          {/* Active card overlay over sky */}
          <div style={{
            position: "absolute", left: "50%", bottom: 16, transform: "translateX(-50%)",
            padding: "8px 14px", borderRadius: 999,
            background: "rgba(5,29,38,0.85)", border: "1px solid rgba(123,255,189,0.45)",
            fontFamily: "var(--serif)", fontSize: 14, whiteSpace: "nowrap",
          }}>
            Tinkering ★★
          </div>
        </div>

        {/* Compact scrubber band — 40% of screen */}
        <div style={{
          flex: "0 0 auto",
          background: "linear-gradient(180deg, rgba(5,29,38,0.0), rgba(5,29,38,0.92) 18%)",
          padding: "14px 12px 28px",
          borderTop: "1px solid rgba(92,244,255,0.18)",
        }}>
          {/* Transport */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <FabPlay paused size={44} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.70)", letterSpacing: 0.5, textTransform: "uppercase" }}>
                146,283 / 462,118 words · 32%
              </div>
              <div style={{ fontFamily: "var(--serif)", fontSize: 13, marginTop: 1 }}>April 14, 2011</div>
            </div>
            <button style={{
              width: 36, height: 36, borderRadius: 10,
              background: "rgba(5,29,38,0.8)", border: "1px solid rgba(92,244,255,0.35)",
              fontFamily: "var(--mono)", fontSize: 11, color: "var(--cyan)",
            }}>1×</button>
          </div>
          {/* Compact 2-track scrubber */}
          <div style={{ position: "relative", height: 64, border: "1px solid rgba(92,244,255,0.18)", borderRadius: 8, background: "rgba(3,8,13,0.6)", padding: "6px 8px", overflow: "hidden" }}>
            {/* Chapter band */}
            <div style={{ position: "relative", height: 8, marginBottom: 4 }}>
              {[10, 22, 34, 46, 58, 70, 82].map((p, i) => (
                <div key={i} style={{ position: "absolute", left: `${p}%`, top: 0, bottom: 0, width: 1, background: "rgba(92,244,255,0.40)" }} />
              ))}
              <div style={{ position: "absolute", left: 0, right: 0, top: "50%", height: 1, background: "rgba(92,244,255,0.12)" }}/>
            </div>
            {/* Rolls + POV combined */}
            <div style={{ position: "relative", height: 30 }}>
              <div style={{ position: "absolute", left: "0%", width: "28%", top: 22, height: 4, background: "rgba(92,244,255,0.20)" }}/>
              <div style={{ position: "absolute", left: "28%", width: "10%", top: 22, height: 4, background: "rgba(180,148,255,0.40)" }}/>
              <div style={{ position: "absolute", left: "38%", width: "30%", top: 22, height: 4, background: "rgba(92,244,255,0.20)" }}/>
              <div style={{ position: "absolute", left: "68%", width: "32%", top: 22, height: 4, background: "rgba(123,255,189,0.30)" }}/>
              {[6, 12, 17, 22, 27, 31, 34, 40, 46, 52, 58, 64, 70, 75, 80, 85, 90].map((p, i) => {
                const isActive = Math.abs(p - 34) < 2;
                return (
                  <div key={i} style={{
                    position: "absolute", left: `${p}%`, top: 8,
                    transform: "translateX(-50%) rotate(45deg)",
                    width: isActive ? 9 : 6, height: isActive ? 9 : 6,
                    background: isActive ? "#5cf4ff" : (i % 3 === 0 ? "rgba(123,255,189,0.70)" : "rgba(245,210,123,0.65)"),
                    boxShadow: isActive ? "0 0 8px #5cf4ff" : "none",
                  }}/>
                );
              })}
            </div>
            {/* Axis */}
            <div style={{ position: "relative", height: 10, marginTop: 2, borderTop: "1px solid rgba(92,244,255,0.10)" }}>
              {Array.from({ length: 10 }).map((_, i) => (
                <div key={i} style={{ position: "absolute", left: `${i * 11.1}%`, top: 0, bottom: 4, width: 1, background: "rgba(92,244,255,0.20)" }}/>
              ))}
              <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 2, background: "linear-gradient(90deg, rgba(245,210,123,0.5) 30%, rgba(180,148,255,0.5) 30% 65%, rgba(255,138,168,0.5) 65%)" }}/>
            </div>
            <Playhead left="34%" />
          </div>
          <div style={{ marginTop: 6, display: "flex", justifyContent: "space-between", fontSize: 9, fontFamily: "var(--mono)", color: "rgba(154,215,223,0.55)", textTransform: "uppercase", letterSpacing: 0.5 }}>
            <span>← swipe to zoom</span>
            <span>tap roll to jump</span>
          </div>
        </div>
      </div>
    </PhoneFrame>
  );
}

// D. Gesture Reader — minimal HUD, gesture-driven
function MockD_GestureReader() {
  return (
    <PhoneFrame orientation="portrait" label="D — Gesture reader">
      <div style={{ position: "absolute", inset: 0 }}>
        <SkyBackground variant="alt" />

        {/* Minimal chrome — just two corner chips */}
        <div style={{ position: "absolute", top: 14, left: 14 }}>
          <Chip>17.32</Chip>
        </div>
        <div style={{ position: "absolute", top: 14, right: 14 }}>
          <Chip color="rgba(123,255,189,0.55)">◢ R42</Chip>
        </div>

        {/* Big center halo with play/pause — circular progress ring */}
        <div style={{ position: "absolute", left: "50%", top: "55%", transform: "translate(-50%, -50%)" }}>
          <ProgressHalo size={150} progress={0.32} paused />
          <div style={{
            position: "absolute", left: "50%", top: 167, transform: "translateX(-50%)",
            fontFamily: "var(--mono)", fontSize: 10, color: "var(--cyan)", letterSpacing: 1, textTransform: "uppercase", whiteSpace: "nowrap",
          }}>
            tap · play
          </div>
        </div>

        {/* Side-swipe hint arrows */}
        <div style={{ position: "absolute", left: 8, top: "55%", transform: "translateY(-50%)", color: "rgba(92,244,255,0.45)", fontSize: 20 }}>‹</div>
        <div style={{ position: "absolute", right: 8, top: "55%", transform: "translateY(-50%)", color: "rgba(92,244,255,0.45)", fontSize: 20 }}>›</div>

        {/* Bottom edge — swipe-up affordance */}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 22, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
          <div style={{ width: 50, height: 3, background: "rgba(92,244,255,0.55)", borderRadius: 2 }}/>
          <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.65)", letterSpacing: 1, textTransform: "uppercase" }}>
            swipe up · timeline
          </div>
        </div>

        {/* Tiny breadcrumb mini-progress at very top */}
        <div style={{
          position: "absolute", left: 14, right: 14, bottom: 70,
          height: 2, background: "rgba(92,244,255,0.12)",
        }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "32%", background: "var(--cyan)", boxShadow: "0 0 6px var(--cyan)" }} />
          {/* roll dots */}
          {[6, 12, 17, 22, 27, 31, 40, 46, 58, 70, 85].map((p, i) => (
            <div key={i} style={{ position: "absolute", left: `${p}%`, top: "50%", transform: "translate(-50%, -50%)", width: 3, height: 3, borderRadius: "50%", background: "rgba(245,210,123,0.85)" }}/>
          ))}
        </div>
      </div>
    </PhoneFrame>
  );
}

function ProgressHalo({ size = 140, progress = 0.32, paused = true }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(92,244,255,0.15)" strokeWidth="2" fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke="#5cf4ff" strokeWidth="2.5" fill="none"
                strokeDasharray={`${c * progress} ${c}`}
                strokeLinecap="round"
                transform={`rotate(-90 ${size/2} ${size/2})`}
                style={{ filter: "drop-shadow(0 0 6px #5cf4ff)" }}/>
        {/* Roll markers around ring */}
        {[0.05, 0.10, 0.16, 0.22, 0.28, 0.45, 0.55, 0.68, 0.78, 0.88, 0.95].map((p, i) => {
          const a = -Math.PI/2 + p * 2 * Math.PI;
          const x = size/2 + (r + 7) * Math.cos(a);
          const y = size/2 + (r + 7) * Math.sin(a);
          return <circle key={i} cx={x} cy={y} r="1.4" fill="rgba(245,210,123,0.85)"/>;
        })}
      </svg>
      <button style={{
        position: "absolute", left: "50%", top: "50%", transform: "translate(-50%, -50%)",
        width: size * 0.55, height: size * 0.55, borderRadius: "50%",
        background: "rgba(5,29,38,0.85)", border: "1px solid rgba(92,244,255,0.55)",
        backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        boxShadow: "0 0 30px rgba(92,244,255,0.35)",
      }}>
        <PlayIcon paused={paused} color="#5cf4ff" size={size * 0.18} />
      </button>
    </div>
  );
}

function ChevronDown() {
  return <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--cyan)" }}>▾</span>;
}
function RoundBtn({ label, active = false }) {
  return (
    <button style={{
      width: 36, height: 36, borderRadius: "50%",
      background: active ? "rgba(92,244,255,0.20)" : "rgba(5,29,38,0.78)",
      border: `1px solid ${active ? "var(--cyan)" : "rgba(92,244,255,0.30)"}`,
      backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)",
      fontFamily: "var(--mono)", fontSize: 10, color: active ? "var(--cyan)" : "var(--muted)",
      letterSpacing: 0.5,
    }}>{label}</button>
  );
}
function ControlPill({ icon, label, active = false, wide = false }) {
  return (
    <button style={{
      flex: wide ? 1.6 : 1,
      padding: "10px 8px", borderRadius: 10,
      background: active ? "rgba(92,244,255,0.18)" : "rgba(5,29,38,0.6)",
      border: `1px solid ${active ? "var(--cyan)" : "rgba(92,244,255,0.22)"}`,
      color: active ? "var(--cyan)" : "var(--muted)",
      fontFamily: "var(--mono)", fontSize: 10,
      display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
      letterSpacing: 0.4, textTransform: "uppercase",
    }}>
      <span style={{ fontSize: 12 }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

Object.assign(window, {
  MockA_SkyFirstHUD, MockB_PeekSheet, MockC_MiniRail, MockD_GestureReader,
  ProgressHalo, ChevronDown, RoundBtn, ControlPill,
});

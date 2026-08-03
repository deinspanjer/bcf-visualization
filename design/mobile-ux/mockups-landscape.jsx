// ── Landscape mockups ───────────────────────────────────────────────────

// E. Cinema mode — full bleed sky, auto-hiding chrome, compact pill bottom-center
function MockE_Cinema({ chromeVisible = true }) {
  return (
    <PhoneFrame orientation="landscape" label={`E — Cinema${chromeVisible ? "" : " (chrome hidden)"}`}>
      <div style={{ position: "absolute", inset: 0 }}>
        <SkyBackground />
        <CornerFrame inset={12} />

        {chromeVisible && (
          <>
            <div style={{ position: "absolute", top: 12, left: 12 }}>
              <Chip>Ch 17 · 32%</Chip>
            </div>
            <div style={{ position: "absolute", top: 12, right: 12, display: "flex", gap: 8 }}>
              <Chip color="rgba(123,255,189,0.40)">◢ R42</Chip>
              <button style={{
                width: 32, height: 32, borderRadius: 8,
                background: "rgba(5,29,38,0.78)", border: "1px solid rgba(92,244,255,0.30)",
                color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 11,
              }}>≡</button>
            </div>

            <div style={{
              position: "absolute", left: "50%", bottom: 16, transform: "translateX(-50%)",
              display: "flex", alignItems: "center", gap: 10,
              background: "rgba(5,29,38,0.85)",
              border: "1px solid rgba(92,244,255,0.35)",
              backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
              borderRadius: 999, padding: "6px 8px 6px 6px",
              minWidth: 360,
              boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
            }}>
              <FabPlay paused size={36} />
              <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "rgba(154,215,223,0.85)", letterSpacing: 0.5, textTransform: "uppercase", whiteSpace: "nowrap" }}>
                42 / 137
              </div>
              <div style={{ position: "relative", flex: 1, height: 10 }}>
                <DotStream count={28} active={9} height={10}/>
                <Playhead left="36%"/>
              </div>
              <button style={{ background: "transparent", border: "none", color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 14, padding: "0 8px" }}>▴</button>
            </div>

            <div style={{ position: "absolute", left: 60, top: "50%", transform: "translateY(-50%)", color: "rgba(92,244,255,0.30)", fontSize: 24 }}>‹</div>
            <div style={{ position: "absolute", right: 30, top: "50%", transform: "translateY(-50%)", color: "rgba(92,244,255,0.30)", fontSize: 24 }}>›</div>
          </>
        )}

        {!chromeVisible && (
          <div style={{
            position: "absolute", left: "50%", top: "50%", transform: "translate(-50%, -50%)",
            opacity: 0.5,
            fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase",
          }}>
            tap to reveal controls
          </div>
        )}
      </div>
    </PhoneFrame>
  );
}

// =============================================================================
// F. Side rail v2  (NEW composition)
//    Sky on the left (~62%). Right column is split:
//      Top 2/3: Joe's field log — narrative readout, rolls + perks acquired
//      Bottom 1/3: gear + info icons, each opening a flyout
//    A persistent auto-hide cinema scrubber from E lives along the bottom
//    of the SKY area so chapter scrubbing is always one tap away.
// =============================================================================
function MockF_SideRail({ flyout = "none" /* "none" | "gear" | "info" */, chromeVisible = true }) {
  const label = flyout === "gear" ? " (settings open)"
              : flyout === "info" ? " (credits open)"
              : !chromeVisible ? " (chrome auto-hidden)"
              : "";
  return (
    <PhoneFrame orientation="landscape" label={`F · Side rail v2${label}`}>
      <div style={{ position: "absolute", inset: 0, display: "flex" }}>
        {/* ── Sky region ─────────────────────────────────────────── */}
        <div style={{ position: "relative", flex: "1 1 auto", minWidth: 0 }}>
          <SkyBackground />
          <CornerFrame inset={12} />

          {/* Sky-side chip (chapter only — keep sky uncluttered) */}
          <div style={{ position: "absolute", top: 14, left: 14 }}>
            <Chip>Ch 17 · 32%</Chip>
          </div>

          {/* Constellation focus */}
          <div style={{
            position: "absolute", left: "50%", top: "44%", transform: "translate(-50%, -50%)",
            textAlign: "center", pointerEvents: "none",
          }}>
            <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(92,244,255,0.75)", letterSpacing: 1.2, textTransform: "uppercase" }}>
              ◢ ROLL #42
            </div>
            <div style={{ fontFamily: "var(--serif)", fontSize: 18, marginTop: 4, textShadow: "0 0 14px rgba(92,244,255,0.40)" }}>
              Tinkering ★★
            </div>
          </div>

          {/* Auto-hide cinema scrubber pinned to the bottom of sky area */}
          {chromeVisible && (
            <div style={{
              position: "absolute", left: 12, right: 12, bottom: 12,
              display: "flex", alignItems: "center", gap: 8,
              background: "rgba(5,29,38,0.85)",
              border: "1px solid rgba(92,244,255,0.30)",
              backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)",
              borderRadius: 999, padding: "5px 8px 5px 5px",
              boxShadow: "0 8px 22px rgba(0,0,0,0.45)",
            }}>
              <FabPlay paused size={30} />
              <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "rgba(154,215,223,0.85)", letterSpacing: 0.5, textTransform: "uppercase", whiteSpace: "nowrap" }}>
                42 / 137
              </div>
              <div style={{ position: "relative", flex: 1, height: 10 }}>
                <DotStream count={28} active={9} height={10}/>
                <Playhead left="36%"/>
              </div>
              <button style={{ background: "transparent", border: "none", color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 12, padding: "0 6px" }}>▴</button>
            </div>
          )}

          {!chromeVisible && (
            <div style={{
              position: "absolute", left: "50%", bottom: 12, transform: "translateX(-50%)",
              fontFamily: "var(--mono)", fontSize: 8, color: "rgba(154,215,223,0.45)",
              letterSpacing: 1, textTransform: "uppercase", pointerEvents: "none",
            }}>
              tap sky · reveal scrub
            </div>
          )}
        </div>

        {/* ── Right rail ─────────────────────────────────────────── */}
        <div style={{
          width: 196, flexShrink: 0,
          background: "linear-gradient(270deg, rgba(5,29,38,0.96), rgba(5,29,38,0.55))",
          borderLeft: "1px solid rgba(92,244,255,0.22)",
          display: "flex", flexDirection: "column",
          position: "relative",
        }}>
          {/* TOP 2/3 — Joe's log */}
          <FieldLogPanel />

          {/* BOTTOM 1/3 — controls dock */}
          <div style={{
            flex: "0 0 33%",
            borderTop: "1px solid rgba(92,244,255,0.18)",
            padding: "10px 12px",
            display: "flex", flexDirection: "column", justifyContent: "space-between",
            background: "rgba(3,8,13,0.55)",
          }}>
            <div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "rgba(154,215,223,0.55)", letterSpacing: 0.6, textTransform: "uppercase", marginBottom: 8 }}>
                Quick actions
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <DockButton active={flyout === "gear"} icon={<GearIcon />} label="Settings" />
                <DockButton active={flyout === "info"} icon={<InfoIcon />} label="About" />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontFamily: "var(--mono)", fontSize: 8, color: "rgba(154,215,223,0.45)", letterSpacing: 0.5, textTransform: "uppercase" }}>
              <span>Mode</span>
              <span style={{ color: "var(--cyan)" }}>Playthrough ▾</span>
            </div>
          </div>

          {/* Flyout overlay — settings */}
          {flyout === "gear" && <SettingsFlyout />}
          {flyout === "info" && <CreditsFlyout />}
        </div>
      </div>
    </PhoneFrame>
  );
}

function FieldLogPanel() {
  return (
    <div style={{ flex: "1 1 67%", padding: "12px 12px 6px", overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--cyan)", letterSpacing: 0.7, textTransform: "uppercase" }}>
          Field Log · Joe
        </div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)" }}>3 of 47</div>
      </div>

      {/* Live entry — currently firing */}
      <div style={{
        padding: "8px 10px",
        background: "rgba(123,255,189,0.08)",
        border: "1px solid rgba(123,255,189,0.45)",
        borderRadius: 8,
        marginBottom: 6,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--mono)", fontSize: 8, color: "var(--green)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 3 }}>
          <span>◢ ROLL 42 · firing</span>
          <span>800 CP</span>
        </div>
        <div style={{ fontFamily: "var(--serif)", fontSize: 12, lineHeight: 1.3 }}>
          Atomic Reassembly
        </div>
        <div style={{ fontSize: 9, color: "var(--muted)", marginTop: 2, fontStyle: "italic", lineHeight: 1.35 }}>
          Molecular control over inanimate matter.
        </div>
      </div>

      {/* Previous entries — fading */}
      <div style={{ display: "flex", flexDirection: "column", gap: 5, overflow: "hidden" }}>
        {[
          { ch: "Ch 16", title: "Hydrokinesis", src: "Avatar · 600 CP", color: "rgba(92,244,255,0.55)" },
          { ch: "Ch 14", title: "Perfect Pitch", src: "Music · 100 CP", color: "rgba(92,244,255,0.40)" },
          { ch: "Ch 12", title: "Mechanical Engineer", src: "Generic · 200 CP", color: "rgba(92,244,255,0.30)" },
          { ch: "Ch 11", title: "Spatial Awareness", src: "Generic · 100 CP", color: "rgba(92,244,255,0.20)" },
        ].map((e, i) => (
          <div key={i} style={{
            padding: "5px 8px", borderLeft: `2px solid ${e.color}`,
            opacity: 1 - i * 0.18,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)", letterSpacing: 0.3, textTransform: "uppercase" }}>
              <span>{e.ch}</span><span>{e.src}</span>
            </div>
            <div style={{ fontFamily: "var(--serif)", fontSize: 11, marginTop: 1 }}>{e.title}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DockButton({ icon, label, active }) {
  return (
    <button style={{
      display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
      padding: "10px 6px",
      background: active ? "rgba(92,244,255,0.18)" : "rgba(5,29,38,0.7)",
      border: `1px solid ${active ? "var(--cyan)" : "rgba(92,244,255,0.25)"}`,
      borderRadius: 10,
      color: active ? "var(--cyan)" : "var(--muted)",
      fontFamily: "var(--mono)", fontSize: 9, letterSpacing: 0.5, textTransform: "uppercase",
    }}>
      <span style={{ width: 18, height: 18, display: "block" }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function GearIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3">
      <circle cx="9" cy="9" r="2.4"/>
      <path d="M9 1.5v2M9 14.5v2M16.5 9h-2M3.5 9h-2M14.3 3.7l-1.4 1.4M5.1 12.9l-1.4 1.4M14.3 14.3l-1.4-1.4M5.1 5.1L3.7 3.7"/>
    </svg>
  );
}
function InfoIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3">
      <circle cx="9" cy="9" r="7"/>
      <path d="M9 8v4M9 5.5v.5" strokeLinecap="round"/>
    </svg>
  );
}
function HelpIcon({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3">
      <circle cx="9" cy="9" r="7"/>
      <path d="M7 7a2 2 0 1 1 3 1.7c-.7.4-1 .8-1 1.5M9 12.5v.5" strokeLinecap="round"/>
    </svg>
  );
}

function SettingsFlyout() {
  return (
    <div style={{
      position: "absolute", right: 196 - 4, bottom: 12, width: 240,
      background: "rgba(5,29,38,0.96)",
      border: "1px solid rgba(92,244,255,0.45)",
      borderRadius: 12,
      padding: "12px 14px",
      backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
      boxShadow: "0 12px 36px rgba(0,0,0,0.55), 0 0 18px rgba(92,244,255,0.15)",
      transform: "translateX(-12px)",
      zIndex: 20,
    }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--cyan)", letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 10 }}>
        Settings
      </div>

      <SettingsGroup title="View mode">
        <SegPair labels={["Playthrough", "Details"]} active={0} />
      </SettingsGroup>

      <SettingsGroup title="On roll">
        <SegPair labels={["Cinematic", "Skip", "Pause"]} active={0} />
      </SettingsGroup>

      <SettingsGroup title="Speed">
        <SegPair labels={["½×", "1×", "2×", "4×"]} active={1} />
      </SettingsGroup>

      <SettingsGroup title="Comfort" last>
        <Row label="Reduced motion" value="Auto" />
        <Row label="Tap to pause" value="On" />
        <Row label="Haptics" value="On" />
      </SettingsGroup>
    </div>
  );
}

function CreditsFlyout() {
  return (
    <div style={{
      position: "absolute", right: 196 - 4, bottom: 12, width: 250,
      background: "rgba(5,29,38,0.96)",
      border: "1px solid rgba(92,244,255,0.45)",
      borderRadius: 12,
      padding: "14px 16px",
      backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
      boxShadow: "0 12px 36px rgba(0,0,0,0.55), 0 0 18px rgba(92,244,255,0.15)",
      transform: "translateX(-12px)",
      zIndex: 20,
    }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--cyan)", letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 4 }}>
        About this visualization
      </div>
      <div style={{ fontFamily: "var(--serif)", fontSize: 15, lineHeight: 1.2 }}>
        Brockton's Celestial Forge
      </div>
      <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
        Worm / Jumpchain crossover by <span style={{ color: "var(--ink)" }}>LordRoustabout</span>
      </div>

      <div style={{ height: 1, background: "rgba(92,244,255,0.18)", margin: "12px 0" }}/>

      <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 6 }}>
        Read the source
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {["SV", "FF", "AO3"].map(s => (
          <div key={s} style={{
            padding: "4px 8px", borderRadius: 4,
            background: "rgba(92,244,255,0.10)", border: "1px solid rgba(92,244,255,0.35)",
            color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: 0.5,
          }}>{s} ↗</div>
        ))}
      </div>

      <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 6 }}>
        Now showing
      </div>
      <div style={{ fontSize: 11, color: "var(--ink)", lineHeight: 1.45 }}>
        <div>Power progression · arcs 1–8</div>
        <div style={{ color: "var(--muted)" }}>137 rolls · 21 chapters · 462k words</div>
      </div>

      <div style={{ height: 1, background: "rgba(92,244,255,0.18)", margin: "12px 0" }}/>

      <button style={{
        width: "100%", padding: "8px 10px",
        background: "rgba(92,244,255,0.12)", border: "1px solid rgba(92,244,255,0.45)",
        borderRadius: 8, color: "var(--cyan)",
        fontFamily: "var(--mono)", fontSize: 10, letterSpacing: 0.5, textTransform: "uppercase",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span>Gestures & help</span><span>↗</span>
      </button>
    </div>
  );
}

function SettingsGroup({ title, children, last }) {
  return (
    <div style={{ marginBottom: last ? 0 : 12 }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 5 }}>
        {title}
      </div>
      {children}
    </div>
  );
}
function SegPair({ labels, active }) {
  return (
    <div style={{ display: "flex", gap: 2, border: "1px solid rgba(92,244,255,0.22)", borderRadius: 6, padding: 2, background: "rgba(3,8,13,0.5)" }}>
      {labels.map((l, i) => (
        <div key={i} style={{
          flex: 1, textAlign: "center", padding: "5px 4px",
          fontFamily: "var(--mono)", fontSize: 10, letterSpacing: 0.3,
          background: i === active ? "rgba(92,244,255,0.20)" : "transparent",
          color: i === active ? "var(--cyan)" : "var(--muted)",
          borderRadius: 4,
        }}>{l}</div>
      ))}
    </div>
  );
}
function Row({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", fontSize: 11 }}>
      <span style={{ color: "var(--muted)" }}>{label}</span>
      <span style={{ color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 10 }}>{value}</span>
    </div>
  );
}

// =============================================================================
// Landing / interstitial — preserves Survey's existing in-character note.
// The only additions over today's design are:
//   • a small story-title + author credit bar pinned at the very top
//   • a help/? icon top-right that opens the same overlay shown elsewhere
// Everything else (Aisha letter, "Open visualization" CTA, source link) is
// kept verbatim from the live landing page so the in-universe framing
// stays intact.
// =============================================================================
function MockLanding({ helpOpen = false }) {
  return (
    <PhoneFrame orientation="portrait" label={`Landing${helpOpen ? " · help open" : ""}`}>
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", background: "radial-gradient(circle at 50% 86%, rgba(92,244,255,0.24), transparent 19%), radial-gradient(circle at 27% 18%, rgba(123,255,189,0.14), transparent 28%), linear-gradient(180deg, #07121a 0%, #03080d 57%, #020406 100%)" }}>
        {/* Background constellation hint (kept low-key) */}
        <BackgroundConstellations />

        {/* ── New: title strip pinned to the top ──────────── */}
        <div style={{
          position: "absolute", top: 8, left: 12, right: 56,
          padding: "8px 12px",
          background: "rgba(5,29,38,0.62)",
          border: "1px solid rgba(92,244,255,0.22)",
          borderRadius: 10,
          backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
        }}>
          <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--cyan)", letterSpacing: 1.5, textTransform: "uppercase" }}>
            Now visualizing
          </div>
          <div style={{ fontFamily: "var(--serif)", fontSize: 14, color: "var(--ink)", lineHeight: 1.1, marginTop: 2 }}>
            Brockton's Celestial Forge
          </div>
          <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>
            by <span style={{ color: "var(--ink)" }}>LordRoustabout</span>
            <span style={{ color: "var(--dim)" }}> · Worm × Jumpchain</span>
          </div>
        </div>

        {/* ── New: help/? icon (top-right) ────────────────── */}
        <button style={{
          position: "absolute", top: 12, right: 12,
          width: 38, height: 38, borderRadius: "50%",
          background: "rgba(5,29,38,0.78)",
          border: `1px solid ${helpOpen ? "var(--cyan)" : "rgba(92,244,255,0.35)"}`,
          backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
          color: helpOpen ? "var(--cyan)" : "var(--muted)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: helpOpen ? "0 0 14px rgba(92,244,255,0.30)" : "none",
        }}>
          <HelpIcon />
        </button>

        {/* ── Existing Survey panel (kept verbatim) ───────── */}
        <div style={{
          position: "absolute", top: 96, left: 14, right: 14, bottom: 28,
          padding: "18px 16px",
          border: "1px solid rgba(92,244,255,0.55)",
          background: "linear-gradient(120deg, rgba(92,244,255,0.10), transparent 36%), rgba(5,29,38,0.54)",
          boxShadow: "inset 0 0 0 1px rgba(92,244,255,0.12), 0 0 40px rgba(92,244,255,0.18), 0 18px 60px rgba(0,0,0,0.45)",
          backdropFilter: "blur(2px)",
          overflow: "hidden",
        }}>
          {/* HUD bracket frame */}
          <div style={{
            position: "absolute", inset: 10,
            border: "1px solid rgba(92,244,255,0.24)",
            clipPath: "polygon(0 0, 100% 0, 100% 14%, 96% 14%, 96% 6%, 4% 6%, 4% 94%, 96% 94%, 96% 86%, 100% 86%, 100% 100%, 0 100%)",
            pointerEvents: "none",
          }}/>
          {/* Scanlines */}
          <div style={{
            position: "absolute", inset: 0, pointerEvents: "none",
            mixBlendMode: "screen", opacity: 0.5,
            background: "repeating-linear-gradient(0deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 5px), linear-gradient(180deg, transparent 0 14%, rgba(92,244,255,0.16) 15%, rgba(92,244,255,0.04) 18%, transparent 22% 100%)",
          }}/>

          {/* Subject */}
          <div style={{
            position: "relative", zIndex: 2,
            color: "var(--green)",
            fontFamily: "var(--mono)", fontSize: 9, fontWeight: 800,
            letterSpacing: 1.4, textTransform: "uppercase", lineHeight: 1.45,
            textShadow: "0 0 10px rgba(123,255,189,0.36)",
            marginBottom: 12,
          }}>
            Re: Joe's power progression<br/>visualization
          </div>

          {/* Letter body */}
          <div style={{
            position: "relative", zIndex: 2,
            color: "rgba(232,253,255,0.88)",
            fontFamily: "var(--serif)", fontSize: 11.5, lineHeight: 1.5,
            textShadow: "0 0 8px rgba(92,244,255,0.30)",
            display: "flex", flexDirection: "column", gap: 7,
          }}>
            <p style={{ margin: 0 }}>Aisha,</p>
            <p style={{ margin: 0 }}>
              Regarding your recent complaint about how difficult it is to understand what Joe is talking about when he discusses the "constellations" of his "Forge" and how it "grabs perks," I have performed a new in-depth analysis of all recorded power acquisitions to date and rendered them in an interactive visualization.
            </p>
            <p style={{ margin: 0 }}>
              Similar to digital audio workstation software, the scrubber will let you review the power progression to your desired level of detail, with links to recordings of what Joe and other relevant individuals were doing at the time.
            </p>
            <p style={{ margin: 0 }}>
              Please let me know if you observe any inaccuracies or have ideas for additional analysis.
            </p>
            <p style={{ margin: "4px 0 0", fontStyle: "italic", color: "var(--ink)" }}>– Survey</p>
          </div>

          {/* Actions */}
          <div style={{
            position: "absolute", left: 16, right: 16, bottom: 16,
            paddingTop: 12,
            borderTop: "1px solid rgba(92,244,255,0.22)",
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
            zIndex: 2,
          }}>
            <button style={{
              minHeight: 44, padding: "0 14px",
              border: "1px solid var(--cyan)",
              background: "rgba(92,244,255,0.14)",
              color: "var(--ink)",
              fontFamily: "var(--mono)", fontSize: 10, fontWeight: 800,
              letterSpacing: 1.2, textTransform: "uppercase",
              boxShadow: "0 0 22px rgba(92,244,255,0.28), inset 0 0 0 1px rgba(92,244,255,0.14)",
            }}>
              Open visualization
            </button>
            <span style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--muted)", letterSpacing: 0.5, textTransform: "uppercase", textDecoration: "underline", textUnderlineOffset: 4 }}>
              View source
            </span>
          </div>
        </div>

        {/* Help overlay */}
        {helpOpen && (
          <>
            <div style={{ position: "absolute", inset: 0, background: "rgba(2,6,10,0.75)", backdropFilter: "blur(6px)" }}/>
            <div style={{
              position: "absolute", top: 60, left: 16, right: 16, bottom: 30,
              background: "rgba(5,29,38,0.97)",
              border: "1px solid rgba(92,244,255,0.45)",
              borderRadius: 16, padding: "16px 18px",
              boxShadow: "0 0 40px rgba(92,244,255,0.20)",
              display: "flex", flexDirection: "column",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--cyan)", letterSpacing: 1, textTransform: "uppercase" }}>
                  Help & credits
                </div>
                <div style={{ width: 24, height: 24, borderRadius: "50%", background: "rgba(92,244,255,0.10)", border: "1px solid rgba(92,244,255,0.30)", color: "var(--muted)", fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center" }}>×</div>
              </div>

              <div style={{ marginTop: 8 }}>
                <div style={{ fontFamily: "var(--serif)", fontSize: 17 }}>Brockton's Celestial Forge</div>
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
                  Worm/Jumpchain crossover by <span style={{ color: "var(--ink)" }}>LordRoustabout</span>
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  {["SV", "FF", "AO3"].map(s => (
                    <div key={s} style={{ padding: "4px 8px", borderRadius: 4, background: "rgba(92,244,255,0.10)", border: "1px solid rgba(92,244,255,0.35)", color: "var(--cyan)", fontFamily: "var(--mono)", fontSize: 9, letterSpacing: 0.5 }}>
                      {s} ↗
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ height: 1, background: "rgba(92,244,255,0.18)", margin: "14px 0" }}/>

              <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--cyan)", letterSpacing: 0.8, textTransform: "uppercase", marginBottom: 8 }}>
                How to play
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "30px 1fr", gap: 10, fontSize: 11, color: "var(--ink)", lineHeight: 1.45 }}>
                <span style={{ fontSize: 16 }}>👆</span>
                <span><b style={{ color: "var(--cyan)" }}>Tap sky</b> — pause / resume anywhere.</span>
                <span style={{ fontSize: 16 }}>👈👉</span>
                <span><b style={{ color: "var(--cyan)" }}>Swipe sky</b> — scrub by roll.</span>
                <span style={{ fontSize: 16 }}>👇</span>
                <span><b style={{ color: "var(--cyan)" }}>Swipe down</b> — show field log.</span>
                <span style={{ fontSize: 16 }}>↑</span>
                <span><b style={{ color: "var(--cyan)" }}>Swipe up</b> — open full timeline.</span>
                <span style={{ fontSize: 16 }}>✋</span>
                <span><b style={{ color: "var(--cyan)" }}>Pinch timeline</b> — zoom the axis.</span>
                <span style={{ fontSize: 16 }}>🔄</span>
                <span><b style={{ color: "var(--cyan)" }}>Rotate</b> — hand off to landscape; state persists.</span>
              </div>

              <div style={{ flex: 1 }}/>

              <button style={{
                padding: "12px 14px",
                background: "linear-gradient(180deg, rgba(92,244,255,0.95), rgba(92,244,255,0.78))",
                color: "#03080d", border: "none", borderRadius: 12,
                fontFamily: "var(--mono)", fontSize: 12, fontWeight: 600,
                letterSpacing: 1, textTransform: "uppercase",
              }}>
                Got it — begin
              </button>
            </div>
          </>
        )}
      </div>
    </PhoneFrame>
  );
}

function BackgroundConstellations() {
  // Echoes the live landing page's scattered constellation stars + lines,
  // dimmed so the message panel stays the focal element.
  const stars = [
    { top: "12%", left: "68%" }, { top: "22%", left: "82%" }, { top: "38%", left: "74%" },
    { top: "54%", left: "88%" }, { top: "66%", left: "78%" },
    { top: "30%", left: "18%" }, { top: "48%", left: "12%" }, { top: "64%", left: "24%" },
  ];
  const lines = [
    { top: "20%", left: "68%", w: 70, deg: 29 }, { top: "30%", left: "74%", w: 72, deg: -45 },
    { top: "45%", left: "75%", w: 80, deg: 32 }, { top: "60%", left: "78%", w: 60, deg: -57 },
    { top: "38%", left: "14%", w: 64, deg: 63 }, { top: "56%", left: "14%", w: 76, deg: 31 },
  ];
  return (
    <div style={{ position: "absolute", inset: 0, opacity: 0.35, pointerEvents: "none" }}>
      {lines.map((l, i) => (
        <span key={`l${i}`} style={{
          position: "absolute", top: l.top, left: l.left, width: l.w, height: 1,
          background: "rgba(186,245,255,0.45)", transform: `rotate(${l.deg}deg)`, transformOrigin: "left center",
          boxShadow: "0 0 8px rgba(92,244,255,0.18)",
        }}/>
      ))}
      {stars.map((s, i) => (
        <span key={`s${i}`} style={{
          position: "absolute", top: s.top, left: s.left,
          width: 4, height: 4, borderRadius: "50%",
          background: "rgba(238,253,255,0.88)", transform: "translate(-50%, -50%)",
          boxShadow: "0 0 3px rgba(255,255,255,0.7), 0 0 10px rgba(92,244,255,0.42)",
        }}/>
      ))}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={{
      flex: 1, padding: "10px 8px",
      background: "rgba(5,29,38,0.65)",
      border: "1px solid rgba(92,244,255,0.22)",
      borderRadius: 10,
      textAlign: "center",
    }}>
      <div style={{ fontFamily: "var(--serif)", fontSize: 18, color: "var(--ink)" }}>{value}</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: 8, color: "var(--dim)", letterSpacing: 0.6, textTransform: "uppercase", marginTop: 2 }}>{label}</div>
    </div>
  );
}

// =============================================================================
// Gesture cheat sheet — pulled out as a reference card (unchanged).
// =============================================================================
function GestureMap() {
  const gestures = [
    { icon: "👆", title: "Single tap (sky)", action: "Pause / resume", note: "Anywhere on the viewport — never need to find the play button." },
    { icon: "👆👆", title: "Double tap", action: "Reset to live edge", note: "Bring playhead back to where the cinematic is firing." },
    { icon: "👈👉", title: "Horizontal swipe (sky)", action: "Scrub by roll", note: "Each swipe = ±1 roll. Long swipe = throw, scrubs many rolls." },
    { icon: "👇", title: "Swipe down (from top)", action: "Reveal field log", note: "The narrative readout slides in over the sky." },
    { icon: "👆↑", title: "Swipe up (from bottom)", action: "Open full timeline sheet", note: "Same as tapping the peek bar's chevron." },
    { icon: "✋", title: "Two-finger pinch (timeline)", action: "Zoom in/out", note: "Pinch on the scrubber to zoom the time axis." },
    { icon: "🤏", title: "Long press (roll dot)", action: "Preview tooltip", note: "Hold to peek who/what fired without committing to a jump." },
    { icon: "🔄", title: "Rotate device", action: "Hand-off to landscape", note: "State persists; layout shifts to side-rail or cinema mode." },
  ];
  return (
    <div style={{
      width: 760, padding: 28,
      background: "rgba(5,29,38,0.55)",
      border: "1px solid rgba(92,244,255,0.25)",
      borderRadius: 14,
      backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 14, gap: 16 }}>
        <div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--cyan)", letterSpacing: 1.5, textTransform: "uppercase" }}>
            Touch contract · proposed
          </div>
          <h2 style={{ margin: "4px 0 0", fontFamily: "var(--serif)", fontWeight: 400, fontSize: 24 }}>
            Gesture map for mobile playback
          </h2>
        </div>
        <div style={{ fontSize: 11, color: "var(--muted)", maxWidth: 280, textAlign: "right", lineHeight: 1.5 }}>
          Every direction below assumes this contract. Tap-to-pause is the
          critical one — the play button can always be below the fold.
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {gestures.map((g, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "44px 1fr",
            gap: 12, padding: "12px 14px",
            background: "rgba(3,8,13,0.55)",
            border: "1px solid rgba(92,244,255,0.15)",
            borderRadius: 10,
            alignItems: "start",
          }}>
            <div style={{ fontSize: 22, lineHeight: 1, marginTop: 2 }}>{g.icon}</div>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
                <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                  {g.title}
                </div>
                <div style={{ fontFamily: "var(--serif)", fontStyle: "italic", fontSize: 12, color: "var(--cyan)" }}>
                  {g.action}
                </div>
              </div>
              <div style={{ fontSize: 12, color: "var(--ink)", marginTop: 4, lineHeight: 1.4 }}>
                {g.note}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Intro / system card
function IntroCard() {
  return (
    <div style={{
      width: 760, padding: 32,
      background: "rgba(5,29,38,0.55)",
      border: "1px solid rgba(92,244,255,0.25)",
      borderRadius: 14,
      backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)",
    }}>
      <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--cyan)", letterSpacing: 1.5, textTransform: "uppercase" }}>
        BCF Visualization · mobile UX · v2
      </div>
      <h1 style={{ margin: "6px 0 14px", fontFamily: "var(--serif)", fontWeight: 400, fontSize: 32, letterSpacing: 0.5 }}>
        Mobile reading mode for the Celestial Forge
      </h1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <div style={{ fontFamily: "var(--serif)", fontSize: 14, lineHeight: 1.55, color: "var(--ink)" }}>
          Round two. Portrait directions narrowed to <b style={{ color: "var(--cyan)" }}>A · Sky-first HUD</b> and
          <b style={{ color: "var(--cyan)" }}> C · Mini-rail bottom</b>. Landscape direction
          <b style={{ color: "var(--cyan)" }}> F · Side rail</b> is reworked: top 2/3 is now Joe's field log,
          bottom 1/3 is a control dock with gear + about. Cinema's auto-hiding bottom scrubber from
          <b style={{ color: "var(--cyan)" }}> E</b> is embedded for fast chapter scrub. A new landing
          interstitial introduces story credits + the gesture contract before anyone starts playing.
        </div>
        <div>
          <div style={{ fontFamily: "var(--mono)", fontSize: 9, color: "var(--dim)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>
            What's new in this revision
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--muted)", lineHeight: 1.7 }}>
            <li><b style={{ color: "var(--ink)" }}>F rail rebuilt</b> — log-first, settings + about live in a dock.</li>
            <li><b style={{ color: "var(--ink)" }}>Hybrid F+E</b> — auto-hide cinema scrubber lives along the bottom of the sky.</li>
            <li><b style={{ color: "var(--ink)" }}>Landing interstitial</b> — credits surfaced; help button reveals the gesture map.</li>
            <li><b style={{ color: "var(--ink)" }}>Help button</b> — visible on every screen via the About flyout.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  MockE_Cinema, MockF_SideRail, MockLanding, GestureMap, IntroCard,
  HelpIcon, GearIcon, InfoIcon,
});

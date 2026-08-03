// Static "sky" placeholder — starfield, focal constellation, glow.
// Used as the background inside each phone mockup so the mockups look
// like the real visualization rather than empty rectangles.

function SkyBackground({ variant = "default", style }) {
  const stars = React.useMemo(() => generateStars(140, variant), [variant]);
  const constellations = CONSTELLATIONS[variant] || CONSTELLATIONS.default;

  return (
    <div style={{
      position: "absolute", inset: 0, overflow: "hidden",
      background: "radial-gradient(ellipse at 60% 40%, rgba(92,244,255,0.10), transparent 50%), radial-gradient(ellipse at 20% 80%, rgba(123,255,189,0.08), transparent 45%), linear-gradient(180deg, #03080d 0%, #02060a 100%)",
      ...style,
    }}>
      <svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        {/* Background stars */}
        {stars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#fff" opacity={s.o} />
        ))}
        {/* Constellation lines + focal stars */}
        {constellations.map((c, ci) => (
          <g key={ci} opacity={c.opacity ?? 1}>
            {c.edges.map((e, i) => (
              <line key={i} x1={c.nodes[e[0]].x} y1={c.nodes[e[0]].y} x2={c.nodes[e[1]].x} y2={c.nodes[e[1]].y}
                    stroke={c.color || "rgba(92,244,255,0.55)"} strokeWidth="0.18" />
            ))}
            {c.nodes.map((n, i) => (
              <g key={i}>
                <circle cx={n.x} cy={n.y} r={n.big ? 0.9 : 0.55} fill={c.color || "#5cf4ff"} opacity="0.9" />
                <circle cx={n.x} cy={n.y} r={n.big ? 2.4 : 1.6} fill={c.color || "#5cf4ff"} opacity="0.12" />
              </g>
            ))}
          </g>
        ))}
      </svg>
      {/* Scanline overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        backgroundImage: "repeating-linear-gradient(0deg, rgba(255,255,255,0.025) 0 1px, transparent 1px 4px)",
        mixBlendMode: "screen",
      }}/>
    </div>
  );
}

function generateStars(n, seed) {
  // deterministic-ish via a tiny LCG
  let s = seed === "default" ? 17 : seed === "alt" ? 41 : 89;
  const rand = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; };
  const out = [];
  for (let i = 0; i < n; i += 1) {
    out.push({
      x: rand() * 100,
      y: rand() * 100,
      r: 0.08 + rand() * 0.32,
      o: 0.20 + rand() * 0.70,
    });
  }
  return out;
}

const CONSTELLATIONS = {
  default: [
    {
      // central "active" constellation — bright cyan
      color: "#5cf4ff",
      nodes: [
        { x: 48, y: 42, big: true }, { x: 55, y: 38 }, { x: 60, y: 45 },
        { x: 58, y: 52, big: true }, { x: 50, y: 55 }, { x: 44, y: 50 },
      ],
      edges: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0],[0,3]],
    },
    {
      // secondary constellation — green
      color: "rgba(123,255,189,0.4)",
      opacity: 0.55,
      nodes: [{ x: 18, y: 25 }, { x: 24, y: 28 }, { x: 28, y: 22 }, { x: 22, y: 18 }],
      edges: [[0,1],[1,2],[2,3],[3,0]],
    },
    {
      // tertiary — amber, top right
      color: "rgba(245,210,123,0.35)",
      opacity: 0.45,
      nodes: [{ x: 78, y: 18 }, { x: 84, y: 24 }, { x: 88, y: 16 }],
      edges: [[0,1],[1,2]],
    },
    {
      // bottom left rose
      color: "rgba(255,138,168,0.32)",
      opacity: 0.42,
      nodes: [{ x: 14, y: 75 }, { x: 22, y: 80 }, { x: 28, y: 72 }, { x: 20, y: 68 }],
      edges: [[0,1],[1,2],[2,3]],
    },
  ],
  alt: [
    {
      color: "#7bffbd",
      nodes: [
        { x: 50, y: 50, big: true }, { x: 58, y: 44 }, { x: 64, y: 52 },
        { x: 60, y: 60, big: true }, { x: 52, y: 62 }, { x: 44, y: 56 },
      ],
      edges: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,0]],
    },
    {
      color: "rgba(92,244,255,0.35)",
      opacity: 0.5,
      nodes: [{ x: 22, y: 30 }, { x: 30, y: 28 }, { x: 26, y: 36 }],
      edges: [[0,1],[1,2],[2,0]],
    },
  ],
};

Object.assign(window, { SkyBackground });

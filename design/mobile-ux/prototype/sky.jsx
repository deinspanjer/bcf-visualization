/* =====================================================================
   Sky viewport — static starfield with a focal constellation drawn for
   the currently-active roll. Re-renders only when active roll changes.
   ===================================================================== */

function Sky({ activeRoll, onTap, onDoubleTap, onSwipeStep, onSwipeEnd }) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;
    return window.attachSkyGestures(el, {
      onTap, onDoubleTap, onSwipeStep, onSwipeEnd,
    });
  }, [onTap, onDoubleTap, onSwipeStep, onSwipeEnd]);

  // Generate stars deterministically once
  const stars = React.useMemo(() => {
    let s = 17;
    const rand = () => { s = (s * 1664525 + 1013904223) % 4294967296; return s / 4294967296; };
    return Array.from({ length: 180 }).map(() => ({
      x: rand() * 100,
      y: rand() * 100,
      r: 0.08 + rand() * 0.32,
      o: 0.20 + rand() * 0.65,
    }));
  }, []);

  // Pick a constellation shape based on outcome
  const cons = React.useMemo(() => buildConstellation(activeRoll), [activeRoll?.globalIndex]);

  return (
    <div className="sky" ref={ref}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
        {stars.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#fff" opacity={s.o} />
        ))}
        {cons && (
          <g>
            {cons.edges.map((e, i) => (
              <line key={`e${i}`}
                    x1={cons.nodes[e[0]].x} y1={cons.nodes[e[0]].y}
                    x2={cons.nodes[e[1]].x} y2={cons.nodes[e[1]].y}
                    stroke={cons.color} strokeWidth="0.18" />
            ))}
            {cons.nodes.map((n, i) => (
              <g key={`n${i}`}>
                <circle cx={n.x} cy={n.y} r={n.big ? 1.0 : 0.6} fill={cons.color} opacity="0.95" />
                <circle cx={n.x} cy={n.y} r={n.big ? 2.4 : 1.4} fill={cons.color} opacity="0.12" />
              </g>
            ))}
          </g>
        )}
      </svg>
      <div className="sky-corners">
        <span /><span /><span /><span />
      </div>
    </div>
  );
}

/* Pick the constellation outline based on activeRoll. Hits get tight
   cyan diamond clusters; misses get sparser rose triangles; unknowns
   default to amber. */
function buildConstellation(roll) {
  if (!roll) {
    return {
      color: "rgba(92,244,255,0.6)",
      nodes: [
        { x: 50, y: 50, big: true }, { x: 56, y: 46 }, { x: 60, y: 52 },
        { x: 56, y: 58 }, { x: 50, y: 60 }, { x: 44, y: 56 }, { x: 44, y: 50 },
      ],
      edges: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,0]],
    };
  }
  const seed = (roll.constellation || roll.perkJump || "").length + (roll.globalIndex || 0);
  let s = (seed * 9301 + 49297) & 0xffff;
  const rand = () => { s = (s * 9301 + 49297) & 0xffff; return s / 0xffff; };
  const cx = 50, cy = 50;
  const nodeCount = 5 + Math.floor(rand() * 4);
  const nodes = [];
  for (let i = 0; i < nodeCount; i += 1) {
    const ang = (i / nodeCount) * Math.PI * 2 + rand() * 0.6;
    const r = 8 + rand() * 12;
    nodes.push({
      x: cx + Math.cos(ang) * r,
      y: cy + Math.sin(ang) * r,
      big: i === 0,
    });
  }
  const edges = [];
  for (let i = 0; i < nodeCount; i += 1) edges.push([i, (i + 1) % nodeCount]);
  // a few cross-edges
  if (nodeCount >= 5) {
    edges.push([0, Math.floor(nodeCount / 2)]);
  }

  const color = roll.outcome === "hit" ? "#5cf4ff"
              : roll.outcome === "miss" ? "rgba(255,138,168,0.85)"
              : "rgba(245,210,123,0.85)";
  return { color, nodes, edges };
}

window.Sky = Sky;

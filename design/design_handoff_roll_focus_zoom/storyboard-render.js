/* eslint-disable */
// Storyboard frame renderer.
// Builds SVG markup per frame for each scenario, plus HUD chrome + captions.

(() => {
  const { SHAPES, SCENARIOS, clusterToWorld, jumpPerkToWorld, JUMP_RADIUS } = window.STORYBOARD;

  // ---------- visual helpers ----------

  // Seeded random for deterministic background starfields.
  function rng(seed) {
    let s = seed;
    return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  }

  // Background stars: a static cloud in world space, same for every frame in a scenario.
  // We draw a generous area so they cover the viewBox even when panned.
  function backgroundStars(seed) {
    const r = rng(seed);
    const out = [];
    for (let i = 0; i < 260; i++) {
      const x = -200 + r() * 2000;
      const y = -100 + r() * 1200;
      const size = r() < 0.18 ? 1.6 : r() < 0.5 ? 1.0 : 0.6;
      const op = 0.18 + r() * 0.55;
      out.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${size}" fill="#cfe9ff" opacity="${op.toFixed(2)}"/>`);
    }
    return `<g class="bg-stars">${out.join("")}</g>`;
  }

  // Diffraction-star symbol — mirrors web/app.js · starSvg() recipe.
  // Cost determines ray count.
  function diffractionMark(cost, color, options = {}) {
    const recipe = recipeFor(cost);
    const id = options.id || `dm-${Math.random().toString(36).slice(2, 8)}`;
    const opacity = options.opacity ?? 0.92;
    const haloR = options.haloR ?? 2.6;

    const rays = (count, len, w, offset = 0) => {
      const parts = [];
      for (let i = 0; i < count; i++) {
        const angle = (360 / count) * i + offset + ((i % 2) ? recipe.jitter : -recipe.jitter);
        parts.push(`<rect x="${-len}" y="${-w/2}" width="${len * 2}" height="${w}" rx="${w/2}" fill="url(#${id})" transform="rotate(${angle.toFixed(2)})"/>`);
      }
      return parts.join("");
    };

    return `
      <g style="filter:drop-shadow(0 0 0.6px #fff) drop-shadow(0 0 3px ${color})" opacity="${opacity}">
        <defs>
          <linearGradient id="${id}" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0"    stop-color="transparent"/>
            <stop offset="0.48" stop-color="#fff" stop-opacity="0.58"/>
            <stop offset="0.50" stop-color="#fff" stop-opacity="0.92"/>
            <stop offset="0.52" stop-color="#fff" stop-opacity="0.58"/>
            <stop offset="1"    stop-color="transparent"/>
          </linearGradient>
        </defs>
        <g opacity="0.68" style="mix-blend-mode:screen">${rays(recipe.major, recipe.length, recipe.width)}</g>
        <g opacity="0.32" style="mix-blend-mode:screen">${rays(recipe.minor, recipe.minorLength, recipe.minorWidth, 360 / (recipe.major * 2))}</g>
        <circle r="${haloR}" fill="${color}" opacity="0.18"/>
        <circle r="1.4" fill="#fff"/>
      </g>
    `;
  }

  function recipeFor(cost) {
    if (cost >= 800) return { major: 12, minor: 12, length: 46, width: 1.05, minorLength: 32, minorWidth: 0.32, jitter: 8 };
    if (cost >= 400) return { major: 8, minor: 8, length: 39, width: 0.92, minorLength: 24, minorWidth: 0.28, jitter: 5 };
    if (cost >= 200) return { major: 6, minor: 6, length: 32, width: 0.78, minorLength: 18, minorWidth: 0.25, jitter: 3 };
    return { major: 4, minor: 4, length: 27, width: 0.7, minorLength: 12, minorWidth: 0.22, jitter: 1 };
  }

  // Visual size of a diffraction marker in world units, given cost.
  function sizeFor(cost) {
    if (cost >= 800) return 96;
    if (cost >= 400) return 78;
    if (cost >= 200) return 64;
    return 54;
  }

  // Place a `<use>`-equivalent: wrap the diffractionMark in a transform group.
  function placeStar(x, y, cost, color, size, options = {}) {
    const s = size / 100;
    return `<g transform="translate(${x.toFixed(2)}, ${y.toFixed(2)}) scale(${s.toFixed(3)})">${diffractionMark(cost, color, options)}</g>`;
  }

  // Simple non-diffraction dot used for un-acquired / dim stars.
  function placeDot(x, y, r, color, opacity = 0.6) {
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r}" fill="${color}" opacity="${opacity}"/>`;
  }

  // Mass-render the cluster silhouette as polylines.
  function renderSilhouette(shape, opacity) {
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    return shape.silhouette.map(poly => {
      const pts = poly.map(([x, y]) => `${(window.STORYBOARD.CLUSTER_OFFSET_X + x * window.STORYBOARD.CLUSTER_SCALE).toFixed(1)},${(window.STORYBOARD.CLUSTER_OFFSET_Y + y * window.STORYBOARD.CLUSTER_SCALE).toFixed(1)}`).join(" ");
      return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" stroke-opacity="${opacity}" stroke-linecap="round" stroke-linejoin="round"/>`;
    }).join("");
  }

  // Cluster-level markers — render every jump marker as a small star.
  // For perk-vertex constellations: focalIsClusterMarker singles out the rolled star.
  // For jump-vertex constellations: anchorMarker is the rolled-jump's anchor.
  function renderClusterMarkers(scenario, frameIdx) {
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const focalIdx = scenario.focalIsClusterMarker ?? scenario.anchorMarker;
    const parts = [];
    shape.markers.forEach((m, idx) => {
      const [wx, wy] = clusterToWorld(m);
      const isFocal = idx === focalIdx;
      if (isFocal && frameIdx >= 3 && scenario.jumpPerks) {
        // The cluster marker is replaced by the interior jump-perks once we're zoomed in.
        return;
      }
      if (isFocal && frameIdx >= 3 && !scenario.jumpPerks) {
        // Perk-vertex case: don't draw a plain marker here, the focal star renders separately.
        return;
      }
      // At F4/F5 (frameIdx >= 3) the camera is on the rolled jump's cluster; the rest of
      // the parent constellation drops to a faint background so the interior perks dominate.
      let dim = (frameIdx >= 2 && !isFocal) ? 0.42 : 0.7;
      let size = isFocal ? 40 : 28;
      if (frameIdx >= 3) {
        dim = isFocal ? 0.55 : 0.16;
        size = isFocal ? 30 : 20;
      }
      parts.push(placeStar(wx, wy, 100, color, size, { opacity: dim }));
    });
    return `<g class="cluster-markers">${parts.join("")}</g>`;
  }

  // Lines connecting interior perks: faint MST-style web inside the jump cluster.
  function renderJumpWeb(scenario) {
    if (!scenario.jumpPerks || scenario.jumpPerks.length < 2) return "";
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    const pts = scenario.jumpPerks.map(p => jumpPerkToWorld(anchor, p));
    // Minimum-spanning-tree approximation: connect each star to the nearest already-placed star.
    const lines = [];
    const used = [0];
    for (let i = 1; i < pts.length; i++) {
      let best = 0, bestD = Infinity;
      for (const u of used) {
        const dx = pts[i][0] - pts[u][0], dy = pts[i][1] - pts[u][1];
        const d = dx * dx + dy * dy;
        if (d < bestD) { bestD = d; best = u; }
      }
      lines.push(`<line x1="${pts[best][0].toFixed(1)}" y1="${pts[best][1].toFixed(1)}" x2="${pts[i][0].toFixed(1)}" y2="${pts[i][1].toFixed(1)}" stroke="${color}" stroke-width="0.7" opacity="0.4"/>`);
      used.push(i);
    }
    return `<g class="jump-web">${lines.join("")}</g>`;
  }

  // Interior jump perks. Appears from frame 3 onward; fades up over frames 3 -> 4.
  function renderInteriorPerks(scenario, frameIdx) {
    if (!scenario.jumpPerks) return "";
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    const focals = scenario.outcome === "multi-grab"
      ? new Set(scenario.focalPerkIndices)
      : new Set(scenario.focalPerkIndex == null ? [] : [scenario.focalPerkIndex]);

    // multi-grab F5: render the binary diffraction marker at the merged position INSTEAD of separate perks.
    if (scenario.outcome === "multi-grab" && frameIdx === 4) {
      const ps = [...focals].map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
      const cx = ps.reduce((a, p) => a + p[0], 0) / ps.length;
      const cy = ps.reduce((a, p) => a + p[1], 0) / ps.length;
      // Binary diffraction marker: two diffraction stars overlaid with slight offset (like the scrubber's binary).
      const offset = 10;
      const out = [
        // faint trace lines remembering original positions
        ...ps.map(p => `<line x1="${p[0].toFixed(1)}" y1="${p[1].toFixed(1)}" x2="${cx.toFixed(1)}" y2="${cy.toFixed(1)}" stroke="${color}" stroke-width="0.6" opacity="0.22" stroke-dasharray="3 3"/>`),
        // flash burst
        `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="36" fill="white" opacity="0.22"/>`,
        `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="22" fill="white" opacity="0.42"/>`,
        // binary marker — sized for the combined cost of the grabbed perks
        placeStar(cx - offset, cy + 2, 200, color, sizeFor(200) * 1.15, { opacity: 1, haloR: 3 }),
        placeStar(cx + offset, cy - 2, 200, color, sizeFor(200) * 1.05, { opacity: 1, haloR: 3 }),
      ];
      // Render also the non-focal perks dim in their original positions (background)
      scenario.jumpPerks.forEach((p, i) => {
        if (focals.has(i)) return;
        const [wx, wy] = jumpPerkToWorld(anchor, p);
        out.push(placeStar(wx, wy, p.cost, color, sizeFor(p.cost) * 0.85, { opacity: 0.4 }));
      });
      return `<g class="interior">${out.join("")}</g>`;
    }

    if (frameIdx < 3) return "";

    // Default render: each perk drawn at its wireframe position
    const fadeIn = frameIdx === 3 ? 0.7 : 1.0;
    const parts = [];

    // For multi-grab F4 (split + suck): the focal perks have been pulled most of the way
    // toward the beam apex (which sits at the centerpoint between them).
    let mergeT = 0;
    if (scenario.outcome === "multi-grab" && frameIdx === 3) mergeT = 0.55;

    let mergeCenter = null;
    if (mergeT > 0) {
      const ps = [...focals].map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
      mergeCenter = [ps.reduce((a, p) => a + p[0], 0) / ps.length, ps.reduce((a, p) => a + p[1], 0) / ps.length];
    }

    scenario.jumpPerks.forEach((p, i) => {
      let [wx, wy] = jumpPerkToWorld(anchor, p);
      const isFocal = focals.has(i);
      if (isFocal && mergeT > 0) {
        wx = wx + (mergeCenter[0] - wx) * mergeT;
        wy = wy + (mergeCenter[1] - wy) * mergeT;
      }
      // All interior perks render at their real cost-appropriate mote size — they're the
      // actual motes of the rolled jump and should dominate the frame visually. Focal
      // stays at full brightness; siblings stay clearly visible at ~70% opacity, not
      // shrunk down (the cost-encoded size already differentiates them).
      let size = sizeFor(p.cost);
      const dim = isFocal ? 1.0 * fadeIn : 0.72 * fadeIn;

      // F5: focal flares (hit) or dims (miss). Siblings stay at sizeFor(cost).
      if (frameIdx === 4 && isFocal) {
        if (scenario.outcome === "miss") {
          parts.push(placeStar(wx, wy, p.cost, color, size * 0.9, { opacity: 0.5 }));
          return;
        }
        size = sizeFor(p.cost) * 1.18;
      }
      parts.push(placeStar(wx, wy, p.cost, color, size, { opacity: dim }));

      // Add motion arrows on multi-grab F4 — telegraph the suck-into-beam
      if (scenario.outcome === "multi-grab" && frameIdx === 3 && isFocal) {
        const [tx, ty] = mergeCenter;
        const dx = tx - wx, dy = ty - wy;
        const len = Math.hypot(dx, dy);
        if (len > 8) {
          const nx = dx / len, ny = dy / len;
          parts.push(`<line x1="${(wx + nx*14).toFixed(1)}" y1="${(wy + ny*14).toFixed(1)}" x2="${(wx + nx*26).toFixed(1)}" y2="${(wy + ny*26).toFixed(1)}" stroke="white" stroke-width="1.1" opacity="0.65" stroke-linecap="round"/>`);
          parts.push(`<line x1="${(wx + nx*30).toFixed(1)}" y1="${(wy + ny*30).toFixed(1)}" x2="${(wx + nx*38).toFixed(1)}" y2="${(wy + ny*38).toFixed(1)}" stroke="white" stroke-width="0.7" opacity="0.42" stroke-linecap="round"/>`);
        }
      }
    });

    // Add "free perk" satellite dots on F5 hit (illustrative, since the storyboard scenarios don't include free perks for clarity)
    return `<g class="interior">${parts.join("")}</g>`;
  }

  // Focal-perk star for perk-vertex constellations (no jump interior).
  function renderFocalClusterPerk(scenario, frameIdx) {
    if (scenario.focalIsClusterMarker == null) return "";
    if (frameIdx < 3) return "";
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const [wx, wy] = clusterToWorld(shape.markers[scenario.focalIsClusterMarker]);
    const cost = scenario.rollMeta.cost || 100;
    const size = frameIdx === 4 ? sizeFor(cost) * 1.18 : sizeFor(cost);
    const opacity = frameIdx === 4 ? 1 : 0.92;
    return placeStar(wx, wy, cost, color, size, { opacity });
  }

  // Spotlight overlay — dark fill with a radial-gradient hole over the focal area.
  function renderSpotlight(scenario, frameIdx, camera) {
    if (!scenario.spotlight) return "";
    if (frameIdx < 3) return "";
    const focal = focalWorldPoint(scenario);
    // Tighten the spotlight as we move from F4 (reveal) to F5 (hit)
    const baseR = frameIdx === 4 ? (scenario.outcome === "multi-grab" ? 95 : (scenario.jumpPerks ? 110 : 70)) : 70;
    const spotR = baseR;
    // The dark fill covers a generous rect, so it stays full even if the camera pans
    const darkOpacity = frameIdx === 4 ? 0.78 : 0.6;
    const id = `spot-${scenario.id}-${frameIdx}`;
    return `
      <defs>
        <radialGradient id="${id}" cx="${focal[0]}" cy="${focal[1]}" r="${spotR}" gradientUnits="userSpaceOnUse">
          <stop offset="0"   stop-color="black" stop-opacity="0"/>
          <stop offset="0.55" stop-color="black" stop-opacity="0"/>
          <stop offset="1"   stop-color="black" stop-opacity="${darkOpacity}"/>
        </radialGradient>
        <radialGradient id="${id}-glow" cx="${focal[0]}" cy="${focal[1]}" r="${spotR * 1.1}" gradientUnits="userSpaceOnUse">
          <stop offset="0"   stop-color="oklch(0.82 0.14 ${SHAPES[scenario.shape].hue})" stop-opacity="${frameIdx === 4 ? 0.10 : 0.05}"/>
          <stop offset="1"   stop-color="oklch(0.82 0.14 ${SHAPES[scenario.shape].hue})" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect x="${camera.x - 200}" y="${camera.y - 200}" width="${camera.w + 400}" height="${camera.h + 400}" fill="url(#${id}-glow)"/>
      <rect x="${camera.x - 200}" y="${camera.y - 200}" width="${camera.w + 400}" height="${camera.h + 400}" fill="url(#${id})"/>
    `;
  }

  // Forge reach beam — a cone of light rising FROM BELOW the visible viewport up to the
  // focal point. Apex at focal, widens downward off the bottom edge of the sky view.
  function renderBeam(scenario, frameIdx, camera) {
    if (!scenario.beam) return "";
    if (frameIdx < 3) return "";   // beam only appears once the split has happened (F4 onward)
    const focal = focalWorldPoint(scenario);
    const hue = SHAPES[scenario.shape].hue;
    const color = `oklch(0.82 0.14 ${hue})`;
    // Bottom of beam = just past the bottom edge of the current camera frame, so the
    // beam always appears to emerge from off-screen at the bottom of the sky view.
    const bottomY = camera.y + camera.h + 40;
    // Beam apex (at focal) is narrow; beam widens going downward.
    const halfWidthApex = frameIdx === 4 ? 4 : 10;
    const halfWidthBase = frameIdx === 4 ? 56 : 88;
    const id = `beam-${scenario.id}-${frameIdx}`;
    const points = [
      [focal[0] - halfWidthApex, focal[1]],
      [focal[0] + halfWidthApex, focal[1]],
      [focal[0] + halfWidthBase, bottomY],
      [focal[0] - halfWidthBase, bottomY],
    ].map(p => p.join(",")).join(" ");
    const opacity = frameIdx === 4 ? 0.9 : 0.55;
    return `
      <defs>
        <linearGradient id="${id}" x1="0" y1="${focal[1]}" x2="0" y2="${bottomY}" gradientUnits="userSpaceOnUse">
          <stop offset="0"    stop-color="${color}" stop-opacity="${(0.72 * opacity).toFixed(2)}"/>
          <stop offset="0.55" stop-color="${color}" stop-opacity="${(0.28 * opacity).toFixed(2)}"/>
          <stop offset="1"    stop-color="${color}" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <polygon points="${points}" fill="url(#${id})"/>
      <line x1="${focal[0]}" y1="${focal[1]}" x2="${focal[0]}" y2="${bottomY}" stroke="${color}" stroke-width="0.8" opacity="${(opacity * 0.45).toFixed(2)}"/>
    `;
  }

  // Where is the rolled focal point in world coords?
  function focalWorldPoint(scenario) {
    const shape = SHAPES[scenario.shape];
    if (scenario.focalIsClusterMarker != null) {
      return clusterToWorld(shape.markers[scenario.focalIsClusterMarker]);
    }
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    if (scenario.outcome === "multi-grab") {
      const ps = scenario.focalPerkIndices.map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
      return [(ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2];
    }
    if (scenario.focalPerkIndex != null && scenario.jumpPerks) {
      return jumpPerkToWorld(anchor, scenario.jumpPerks[scenario.focalPerkIndex]);
    }
    return anchor;
  }

  // ---------- camera positions per frame ----------

  function cameraForFrame(scenario, frameIdx) {
    const shape = SHAPES[scenario.shape];
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    const focal = focalWorldPoint(scenario);

    const wide = { cx: 800, cy: 500, w: 1280, h: 800 };
    const lockOn = { cx: 800, cy: 500, w: 1100, h: 687 };           // F2 — slight scale-down on lock
    const revealTarget = (scenario.jumpPerks && scenario.jumpPerks.length > 1) ? anchor : focal;
    const reveal = { cx: revealTarget[0], cy: revealTarget[1], w: 320, h: 200 };
    const hit = { cx: focal[0], cy: focal[1], w: 192, h: 120 };

    // F3 approach — partial lerp from wide to reveal
    const t = 0.55;
    const approach = {
      cx: wide.cx + (reveal.cx - wide.cx) * t,
      cy: wide.cy + (reveal.cy - wide.cy) * t,
      w: wide.w + (reveal.w - wide.w) * t,
      h: wide.h + (reveal.h - wide.h) * t,
    };

    const cameras = [wide, lockOn, approach, reveal, hit];
    const c = cameras[frameIdx];
    return { x: c.cx - c.w / 2, y: c.cy - c.h / 2, w: c.w, h: c.h };
  }

  // ---------- HUD chrome (per-frame) ----------

  function renderHud(scenario, frameIdx) {
    const shape = SHAPES[scenario.shape];
    const states = [
      { lock: "drifting", state: "drifting", stateCls: "" },
      { lock: "lock requested", state: "lock", stateCls: "active" },
      { lock: shape.label.toLowerCase(), state: "forge active", stateCls: "active" },
      { lock: shape.label.toLowerCase(), state: "reach extending", stateCls: "active" },
      { lock: shape.label.toLowerCase(), state: scenario.outcome === "miss" ? "miss" : (scenario.outcome === "multi-grab" ? "multi-grab" : "grab confirmed"), stateCls: scenario.outcome === "miss" ? "miss" : "active" },
    ];
    const s = states[frameIdx];
    return `
      <div class="hud">
        <span class="pip ${s.stateCls}"><span class="led"></span>sky lock <b>${s.lock}</b></span>
        <span class="pip ${s.stateCls}">${s.state}</span>
      </div>
    `;
  }

  // ---------- caption inside frame (visible on lock / hit frames) ----------

  function renderInFrameCaption(scenario, frameIdx) {
    if (frameIdx < 4) return "";
    const r = scenario.rollMeta;
    if (scenario.outcome === "miss") {
      return `
        <div class="cap miss">
          <span class="cap-name">miss</span>
          <span class="cap-cp">est. ${r.miss_estimate} CP</span>
          <span class="cap-where">${r.color_text}</span>
          <span class="cap-cp">#${r.roll}</span>
        </div>
      `;
    }
    return `
      <div class="cap">
        <span class="cap-name">${r.perk}</span>
        <span class="cap-cp">${r.cost} CP</span>
        <span class="cap-where">${r.color_text}</span>
        <span class="cap-cp">#${r.roll}</span>
      </div>
    `;
  }

  // ---------- per-frame textual description ----------

  const FRAME_LABELS = ["drift", "lock", "approach", "split / reveal", "hit"];
  const FRAME_DESCS = [
    () => `Scrubber is moving through chapter. Cluster silhouette at rest, no roll firing.`,
    () => `Scrubber lands on a chapter with a roll. <b>SKY LOCK</b> activates, easing toward the target jump.`,
    (s) => {
      if (s.jumpPerks && SHAPES[s.shape].vertex_source === "jumps") {
        return `Camera pans + scales rapidly. Cluster and jump-vertex <b>smear with motion blur</b> as the camera accelerates — readies the eye for the split that's about to land.`;
      }
      return `Camera pans + scales. Focal point slides toward center; outer cluster markers drift off-screen.`;
    },
    (s) => {
      if (s.outcome === "miss") return `Blur clears; the inferred candidate perk appears in place of the jump-vertex. Beam rises from below toward it but the apex doesn't yet touch.`;
      if (s.outcome === "multi-grab") return `<b>Split</b> — the single jump-vertex resolves into its perk stars. Beam rises toward the centerpoint between the two grabbed perks; they begin drifting toward the beam apex.`;
      if (s.jumpPerks && SHAPES[s.shape].vertex_source === "jumps") return `<b>Split</b> — blur clears and the jump-vertex resolves into the jump's distinct perk stars in their wireframe positions. Beam rises from below the sky view toward the rolled perk; spotlight tightens.`;
      return `Focal perk fills the frame. Beam reaches up toward it from the bottom of the sky view; spotlight tightens.`;
    },
    (s) => {
      if (s.outcome === "miss") return `Beam stays cast but its apex never lands — the candidate dims rather than flares. Forge couldn't afford the grab.`;
      if (s.outcome === "multi-grab") return `Beam apex on the centerpoint; the two perks have been <b>sucked into the beam</b> and merge with a flash into the <b>binary diffraction marker</b> that the scrubber uses.`;
      return `<b>Hit</b> — beam apex locks on the focal perk; star flares to full diffraction-star (matches scrubber). Holds for the configured beat.`;
    },
  ];

  // ---------- assemble a single frame ----------

  function buildFrame(scenario, frameIdx) {
    const camera = cameraForFrame(scenario, frameIdx);
    const shape = SHAPES[scenario.shape];
    const seed = (scenario.id.length * 71 + 13) % 10000;

    // Motion-blur the cluster contents on F3 (approach) whenever the rolled jump has
    // multiple motes — jump-vertex constellation about to split, or multi-grab where the
    // grabbed motes are about to be sucked into the beam. Reads as "camera is moving fast
    // and we're about to land."
    const wantsBlur = frameIdx === 2 && Array.isArray(scenario.jumpPerks) && scenario.jumpPerks.length >= 2;
    const blurId = `blur-${scenario.id}`;
    const blurDef = wantsBlur
      ? `<defs><filter id="${blurId}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="7"/></filter></defs>`
      : "";
    const blurOpen = wantsBlur ? `<g filter="url(#${blurId})">` : "";
    const blurClose = wantsBlur ? `</g>` : "";

    const layers = [
      backgroundStars(seed),
      blurDef,
      blurOpen,
      `<g class="silhouette">${renderSilhouette(shape, frameIdx <= 1 ? 0.42 : 0.34)}</g>`,
      renderClusterMarkers(scenario, frameIdx),
      blurClose,
      // Interior perks render as a free-floating organic cluster (no connecting lines —
      // we don't want it to read as a mini-constellation in its own right).
      renderInteriorPerks(scenario, frameIdx),
      renderFocalClusterPerk(scenario, frameIdx),
      renderBeam(scenario, frameIdx, camera),
      renderSpotlight(scenario, frameIdx, camera),
    ].filter(Boolean).join("");

    return `
      <div class="frame">
        <div class="frame-head">
          <span class="fh-num">F${frameIdx + 1}</span>
          <span class="fh-t">${FRAME_LABELS[frameIdx]}</span>
        </div>
        <div class="frame-canvas">
          <svg viewBox="${camera.x.toFixed(1)} ${camera.y.toFixed(1)} ${camera.w.toFixed(1)} ${camera.h.toFixed(1)}" preserveAspectRatio="xMidYMid slice">
            ${layers}
          </svg>
          <div class="corners"><span class="tl"></span><span class="tr"></span><span class="bl"></span><span class="br"></span></div>
          ${renderHud(scenario, frameIdx)}
        </div>
        <div class="frame-cap">${FRAME_DESCS[frameIdx](scenario)}</div>
      </div>
    `;
  }

  // ---------- assemble one storyboard artboard ----------

  function buildArtboard(scenario) {
    const tag = scenario.section === "approaches" ? "approach" : "outcome";
    const tech = (scenario.tech || []).map(t => `<span>${t}</span>`).join(" · ");
    const frames = [0, 1, 2, 3, 4].map(i => buildFrame(scenario, i)).join("");
    return `
      <article class="artboard" data-scenario="${scenario.id}">
        <header class="ab-label">
          <span class="ab-tag"><span class="tag-dot"></span>${tag}</span>
          <h3 class="ab-title">${scenario.title}</h3>
          <p class="ab-desc">${scenario.description}</p>
          <div class="ab-tech">${tech}</div>
        </header>
        <div class="frames">${frames}</div>
      </article>
    `;
  }

  // ---------- mount ----------

  const sectionA = SCENARIOS.filter(s => s.section === "approaches");
  const sectionB = SCENARIOS.filter(s => s.section === "outcomes");

  document.getElementById("approaches-boards").innerHTML = sectionA.map(buildArtboard).join("");
  document.getElementById("outcomes-boards").innerHTML = sectionB.map(buildArtboard).join("");
})();

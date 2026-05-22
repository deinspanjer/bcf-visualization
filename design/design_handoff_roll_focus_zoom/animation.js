/* eslint-disable */
// Animated sky-view roll-focus prototype.
// Continuous-time renderer + player. Reads scene data from window.STORYBOARD
// (populated by storyboard-data.js).
//
// Animation timing per scene (t = 0..1 across SCENE_DURATION_MS):
//   0.00 - 0.10  drift           idle, sky at rest
//   0.10 - 0.20  lock            HUD switches; camera barely moves
//   0.20 - 0.55  approach        camera pans+scales, motion blur builds (peaks 0.50)
//   0.55 - 0.65  split           blur clears, jump-vertex resolves into perks
//   0.65 - 0.82  reveal          beam rises from below, spotlight tightens
//   0.82 - 0.90  hit / merge     focal flares (hit) | perks merge into binary mark (multi-grab) | beam stalls (miss)
//   0.90 - 1.00  hold            stays at end state until scene gap, then next scene

(() => {
  const {
    SHAPES, SCENARIOS,
    clusterToWorld, jumpPerkToWorld,
    CLUSTER_OFFSET_X, CLUSTER_OFFSET_Y, CLUSTER_SCALE,
  } = window.STORYBOARD;

  // ---- which scenarios to animate ----
  const SCENE_IDS = ["out-multi-perk-jump", "out-multi-grab", "out-miss"];
  const SCENES = SCENE_IDS.map(id => SCENARIOS.find(s => s.id === id));

  const SCENE_DURATION_MS = 2800;
  const SCENE_GAP_MS = 400;
  const CYCLE_MS = SCENE_DURATION_MS + SCENE_GAP_MS;
  const TOTAL_DURATION_MS = SCENES.length * CYCLE_MS;

  // ---- easing & math helpers ----
  const easeInOutCubic = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const easeOutCubic = t => 1 - Math.pow(1 - t, 3);
  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp01 = t => Math.max(0, Math.min(1, t));
  // Map t from [a,b] to [0,1], clamped.
  const phase = (t, a, b) => clamp01((t - a) / (b - a));

  // ---- diffraction-star recipe (matches web/app.js · recipeFor) ----
  function recipeFor(cost) {
    if (cost >= 800) return { major: 12, minor: 12, length: 46, width: 1.05, minorLength: 32, minorWidth: 0.32, jitter: 8 };
    if (cost >= 400) return { major: 8, minor: 8, length: 39, width: 0.92, minorLength: 24, minorWidth: 0.28, jitter: 5 };
    if (cost >= 200) return { major: 6, minor: 6, length: 32, width: 0.78, minorLength: 18, minorWidth: 0.25, jitter: 3 };
    return { major: 4, minor: 4, length: 27, width: 0.7, minorLength: 12, minorWidth: 0.22, jitter: 1 };
  }
  function sizeFor(cost) {
    if (cost >= 800) return 96;
    if (cost >= 400) return 78;
    if (cost >= 200) return 64;
    return 54;
  }

  // ---- shared symbol defs (built once, embedded in every frame's SVG) ----
  function buildSymbolDefs() {
    const symbol = cost => {
      const recipe = recipeFor(cost);
      const rays = (count, len, w, offset = 0) => Array.from({ length: count }, (_, i) => {
        const angle = (360 / count) * i + offset + ((i % 2) ? recipe.jitter : -recipe.jitter);
        return `<rect x="${-len}" y="${-w/2}" width="${len * 2}" height="${w}" rx="${w/2}" fill="url(#ray-grad)" transform="rotate(${angle.toFixed(2)})"/>`;
      }).join("");
      return `<symbol id="dm-${cost}" viewBox="-50 -50 100 100" overflow="visible">
        <g style="filter:drop-shadow(0 0 0.6px #fff) drop-shadow(0 0 3px currentColor)">
          <g opacity="0.68" style="mix-blend-mode:screen">${rays(recipe.major, recipe.length, recipe.width)}</g>
          <g opacity="0.32" style="mix-blend-mode:screen">${rays(recipe.minor, recipe.minorLength, recipe.minorWidth, 360 / (recipe.major * 2))}</g>
          <circle r="2.2" fill="currentColor" opacity="0.20"/>
          <circle r="1.4" fill="#fff"/>
        </g>
      </symbol>`;
    };
    const grad = `<linearGradient id="ray-grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"    stop-color="transparent"/>
      <stop offset="0.48" stop-color="#fff" stop-opacity="0.58"/>
      <stop offset="0.50" stop-color="#fff" stop-opacity="0.92"/>
      <stop offset="0.52" stop-color="#fff" stop-opacity="0.58"/>
      <stop offset="1"    stop-color="transparent"/>
    </linearGradient>`;
    return grad + [100, 200, 400, 600, 800].map(symbol).join("");
  }
  const SYMBOL_DEFS = buildSymbolDefs();

  // Place a star instance via <use> — much cheaper than rebuilding rays per call.
  // visualSize is the rendered diameter in world units.
  // NOTE: <use> referencing a <symbol> with a viewBox MUST have explicit x/y/width/height,
  // otherwise browsers fall back to fitting the symbol into the outer SVG viewport and the
  // transform on the wrapper misaligns the star. We size the use to the symbol's intrinsic
  // viewBox (-50,-50,100,100) so the wrapper's scale produces a star centered on the translate.
  function placeStar(x, y, cost, color, visualSize, opacity = 1) {
    const s = visualSize / 100;
    const id = `dm-${cost >= 800 ? 800 : cost >= 600 ? 600 : cost >= 400 ? 400 : cost >= 200 ? 200 : 100}`;
    return `<g transform="translate(${x.toFixed(2)},${y.toFixed(2)}) scale(${s.toFixed(3)})" style="color:${color};opacity:${opacity.toFixed(3)}"><use href="#${id}" x="-50" y="-50" width="100" height="100"/></g>`;
  }

  // ---- background stars (per-scenario static cloud, generated once) ----
  // Static screen-space starscape: lives in a separate fixed-size SVG layer behind the
  // dynamic stage, so it never scales when the camera zooms in. Reads as truly distant
  // "infinity" background that isn't part of the constellation geometry.
  function backgroundStarsScreenSpace(scenario) {
    let seed = (scenario.id.length * 71 + 13) % 10000;
    const random = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
    const out = [];
    // Sized to a fixed 1600x1000 viewBox covering the stage. The bg-svg's preserveAspectRatio
    // matches the stage so they line up. Density and sizes tuned for ambient-only feel.
    for (let i = 0; i < 220; i++) {
      const x = random() * 1600;
      const y = random() * 1000;
      const size = random() < 0.12 ? 1.4 : random() < 0.5 ? 0.9 : 0.5;
      const op = 0.18 + random() * 0.42;
      out.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${size}" fill="#cfe9ff" opacity="${op.toFixed(2)}"/>`);
    }
    return out.join("");
  }
  const bgCache = new Map();
  function getBgScreenSpace(scenario) {
    if (!bgCache.has(scenario.id)) bgCache.set(scenario.id, backgroundStarsScreenSpace(scenario));
    return bgCache.get(scenario.id);
  }

  // ---- focal world point ----
  function focalWorldPoint(scenario) {
    const shape = SHAPES[scenario.shape];
    if (scenario.focalIsClusterMarker != null) return clusterToWorld(shape.markers[scenario.focalIsClusterMarker]);
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    if (scenario.outcome === "multi-grab") {
      const ps = scenario.focalPerkIndices.map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
      return [(ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2];
    }
    if (scenario.focalPerkIndex != null && scenario.jumpPerks) return jumpPerkToWorld(anchor, scenario.jumpPerks[scenario.focalPerkIndex]);
    return anchor;
  }

  // ---- camera trajectory ----
  function cameraAt(scenario, t) {
    const shape = SHAPES[scenario.shape];
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    const focal = focalWorldPoint(scenario);

    const wide   = { cx: 800, cy: 500, w: 1280, h: 800 };
    const revealTarget = (scenario.jumpPerks && scenario.jumpPerks.length > 1) ? anchor : focal;
    const reveal = { cx: revealTarget[0], cy: revealTarget[1], w: 320, h: 200 };
    const hit    = { cx: focal[0], cy: focal[1], w: 192, h: 120 };

    let cur;
    if (t < 0.10) {
      cur = wide;
    } else if (t < 0.65) {
      const k = easeInOutCubic((t - 0.10) / 0.55);
      cur = {
        cx: lerp(wide.cx, reveal.cx, k), cy: lerp(wide.cy, reveal.cy, k),
        w:  lerp(wide.w,  reveal.w,  k), h:  lerp(wide.h,  reveal.h,  k),
      };
    } else if (t < 0.86) {
      const k = easeInOutCubic((t - 0.65) / 0.21);
      cur = {
        cx: lerp(reveal.cx, hit.cx, k), cy: lerp(reveal.cy, hit.cy, k),
        w:  lerp(reveal.w,  hit.w,  k), h:  lerp(reveal.h,  hit.h,  k),
      };
    } else {
      cur = hit;
    }

    return { x: cur.cx - cur.w / 2, y: cur.cy - cur.h / 2, w: cur.w, h: cur.h };
  }

  // ---- per-effect progress curves ----
  function blurAt(scenario, t) {
    // Motion blur during approach for multi-perk jumps; peaks just before the split.
    if (!scenario.jumpPerks || scenario.jumpPerks.length < 2) return 0;
    if (t < 0.22) return 0;
    if (t < 0.50) return ((t - 0.22) / 0.28) * 8;
    if (t < 0.62) return Math.max(0, 8 - ((t - 0.50) / 0.12) * 8);
    return 0;
  }

  function splitProgress(scenario, t) {
    // Perks start emerging during the rising-blur portion of the approach, so they fade
    // in concurrently with the silhouette fading out AND with the camera still panning.
    // The motion blur masks both transitions; when the smear clears we land on the four
    // motes already in position. Earlier start (t=0.40) means perks are first perceptible
    // around 1.12s in scene 1, comfortably ahead of the blur peak at 1.40s.
    if (!scenario.jumpPerks) return 0;
    if (t < 0.40) return 0;
    if (t < 0.58) return easeInOutCubic((t - 0.40) / 0.18);
    return 1;
  }

  function beamOpacity(scenario, t) {
    if (!scenario.beam) return 0;
    if (t < 0.55) return 0;
    if (t < 0.80) return easeInOutCubic((t - 0.55) / 0.25) * 0.92;
    return 0.92;
  }

  function beamReach(scenario, t) {
    // 0 = apex at bottom of viewport; 1 = apex at focal point.
    // Miss never reaches > 0.78 — beam stalls visibly short.
    if (!scenario.beam) return 0;
    if (t < 0.55) return 0;
    const raw = easeOutCubic(clamp01((t - 0.55) / 0.27));
    if (scenario.outcome === "miss") return raw * 0.78;
    return raw;
  }

  function spotlightProgress(scenario, t) {
    if (!scenario.spotlight) return 0;
    if (t < 0.48) return 0;
    if (t < 0.84) return easeInOutCubic((t - 0.48) / 0.36);
    return 1;
  }

  function focalScaleFactor(scenario, t) {
    if (scenario.outcome === "miss") return 0.95;
    // Multi-grab focals slide to binary positions and stay at base size — the binary
    // visual is achieved through proximity + ray overlap, not size boost.
    if (scenario.outcome === "multi-grab") return 1.0;
    // Boost the single-focal's diffraction size during reveal→hit so a small-cost focal still
    // competes with larger-cost siblings in the same jump. Tops out at ~1.5x at the flare.
    if (t < 0.66) return 1.0;
    if (t < 0.82) return 1.0 + easeOutCubic((t - 0.66) / 0.16) * 0.28;
    if (t < 0.90) return 1.28 + easeOutCubic((t - 0.82) / 0.08) * 0.22;
    return 1.50;
  }

  function multiGrabMerge(scenario, t) {
    // Perks slide toward beam apex (centerpoint) starting once the split has just happened
    // and the beam has begun rising. Reaches the apex by t≈0.88, then the flash + binary takes over.
    if (scenario.outcome !== "multi-grab") return 0;
    if (t < 0.62) return 0;
    if (t < 0.88) return easeInOutCubic((t - 0.62) / 0.26);
    return 1;
  }

  function multiGrabFlash(scenario, t) {
    if (scenario.outcome !== "multi-grab") return 0;
    // Brief flash at the moment of fusion (mergeT ≈ 1, around t=0.83–0.88). Quick in,
    // quick out — it's a punctuation mark, not a long bloom.
    if (t < 0.82) return 0;
    if (t < 0.86) return easeOutCubic((t - 0.82) / 0.04);
    if (t < 0.92) return Math.max(0, 1 - ((t - 0.86) / 0.06));
    return 0;
  }

  // ---- layer renderers ----

  function renderSilhouette(scenario, t) {
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    // Silhouette + pins fade out UNDER COVER of the motion blur (blur peaks at t=0.50,
    // clears by t=0.62). If the opacity fade outlasts the blur, the silhouette appears
    // to "pop back in" sharp the moment blur clears. Holding op=0.62 until t=0.50 then
    // crashing to 0 by t=0.60 hides the entire transition behind the smear.
    const fadeT = phase(t, 0.50, 0.60);
    const op = t < 0.50 ? 0.62 : lerp(0.62, 0, fadeT);
    const sw = t < 0.50 ? 2.4 : lerp(2.4, 1.0, fadeT);
    if (op <= 0.01) return "";
    const lines = shape.silhouette.map(poly => {
      const pts = poly.map(([x, y]) => `${(CLUSTER_OFFSET_X + x * CLUSTER_SCALE).toFixed(1)},${(CLUSTER_OFFSET_Y + y * CLUSTER_SCALE).toFixed(1)}`).join(" ");
      return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="${sw.toFixed(2)}" stroke-opacity="${op.toFixed(3)}" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
    }).join("");
    const pinOp = t < 0.50 ? 0.85 : lerp(0.85, 0, fadeT);
    const pins = pinOp <= 0.01 ? "" : shape.markers.map(m => {
      const [wx, wy] = clusterToWorld(m);
      return `<circle cx="${wx.toFixed(1)}" cy="${wy.toFixed(1)}" r="3.0" fill="${color}" opacity="${pinOp.toFixed(3)}"/>`;
    }).join("");
    return lines + pins;
  }

  function renderClusterMarkers(scenario, t) {
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const focalIdx = scenario.focalIsClusterMarker ?? scenario.anchorMarker;
    const split = splitProgress(scenario, t);
    const zoomedIn = phase(t, 0.55, 0.85);
    const parts = [];
    shape.markers.forEach((m, idx) => {
      const [wx, wy] = clusterToWorld(m);
      const isFocal = idx === focalIdx;

      let opacity, size;
      if (isFocal) {
        // The focal vertex fades out as the split takes over (replaced by interior perks)
        if (scenario.jumpPerks) {
          opacity = lerp(0.85, 0, split);
          size = lerp(54, 38, split);
        } else {
          // Perk-vertex case: marker also fades, focal star renders separately
          opacity = lerp(0.85, 0, split);
          size = 54;
        }
      } else {
        // Outer cluster markers fade under the blur same as the silhouette — if their
        // opacity outlasts the blur they pop back as sharp dots when the smear clears.
        const outerFade = phase(t, 0.50, 0.60);
        opacity = lerp(0.65, 0, outerFade);
        size = lerp(34, 18, outerFade);
      }

      if (opacity > 0.01) parts.push(placeStar(wx, wy, 100, color, size, opacity));
    });
    return `<g class="cluster-markers">${parts.join("")}</g>`;
  }

  function renderInteriorPerks(scenario, t) {
    if (!scenario.jumpPerks) return "";
    const shape = SHAPES[scenario.shape];
    const color = `oklch(0.82 0.14 ${shape.hue})`;
    const anchor = clusterToWorld(shape.markers[scenario.anchorMarker]);
    const split = splitProgress(scenario, t);
    if (split <= 0) return "";

    const focals = scenario.outcome === "multi-grab"
      ? new Set(scenario.focalPerkIndices)
      : new Set(scenario.focalPerkIndex == null ? [] : [scenario.focalPerkIndex]);

    let mergeCenter = null;
    let binaryTargets = null;
    if (scenario.outcome === "multi-grab") {
      const ps = scenario.focalPerkIndices.map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
      mergeCenter = [(ps[0][0] + ps[1][0]) / 2, (ps[0][1] + ps[1][1]) / 2];
      // Binary positions — mirrors the scrubber's two-perk diffraction marker:
      // first focal goes to (-5, +1), second to (+5, -1) relative to merge center.
      // This is close enough that the 100 CP perks' rays overlap heavily, reading as
      // a single "fused" binary unit per the scrubber's visual vocabulary.
      binaryTargets = [
        [mergeCenter[0] - 5, mergeCenter[1] + 1],
        [mergeCenter[0] + 5, mergeCenter[1] - 1],
      ];
    }
    const mergeT = multiGrabMerge(scenario, t);

    const parts = [];

    scenario.jumpPerks.forEach((p, i) => {
      const isFocal = focals.has(i);
      let [wx, wy] = jumpPerkToWorld(anchor, p);

      // Multi-grab: focal perks slide to their BINARY positions (close, slightly offset)
      // rather than collapsing to a single point. They never disappear — they fuse.
      if (isFocal && scenario.outcome === "multi-grab" && mergeT > 0) {
        const focalSlot = scenario.focalPerkIndices.indexOf(i);
        const [tx, ty] = binaryTargets[focalSlot];
        wx = lerp(wx, tx, mergeT);
        wy = lerp(wy, ty, mergeT);
      }

      // Non-focal perks dim significantly during reveal/hit so the rolled perk reads as
      // the focal regardless of its cost. A 100 CP focal in a jump that contains an 800 CP
      // sibling shouldn't get visually buried by the sibling's larger diffraction recipe.
      const dimFloor = scenario.outcome === "miss" ? 0.30 : 0.28;
      const baseOp = isFocal ? 1.0 : lerp(0.72, dimFloor, phase(t, 0.66, 0.90));
      const op = baseOp * split;

      let visualSize = sizeFor(p.cost);
      if (isFocal) visualSize *= focalScaleFactor(scenario, t);

      // Per-perk aura removed — we now draw ONE shared shrinking halo per hit (any
      // outcome), in the block after this forEach. The shared halo reads consistently
      // across single-perk hits and multi-grab. Miss explicitly skips the halo so the
      // "no lock" outcome is visually distinct from "locked on."

      // Motion arrows for multi-grab focal perks as they slide
      if (scenario.outcome === "multi-grab" && isFocal && mergeT > 0.05 && mergeT < 0.9) {
        const dx = mergeCenter[0] - wx;
        const dy = mergeCenter[1] - wy;
        const len = Math.hypot(dx, dy);
        if (len > 6) {
          const nx = dx / len, ny = dy / len;
          const trailOp = (0.7 * (1 - mergeT)).toFixed(2);
          parts.push(`<line x1="${(wx + nx*12).toFixed(1)}" y1="${(wy + ny*12).toFixed(1)}" x2="${(wx + nx*22).toFixed(1)}" y2="${(wy + ny*22).toFixed(1)}" stroke="white" stroke-width="1" opacity="${trailOp}" stroke-linecap="round"/>`);
        }
      }

      parts.push(placeStar(wx, wy, p.cost, color, visualSize, op));
    });

    // Shared shrinking halo — the Forge's reach drawing in around the target. Drawn
    // for any HIT outcome (single-focal or multi-grab). Skipped for miss so the
    // "didn't connect" outcome reads visually distinct from a successful lock.
    if (scenario.outcome !== "miss") {
      const auraP = phase(t, 0.62, 0.86);
      if (auraP > 0.04) {
        let auraCx, auraCy, initialR, finalR, shrinkT;
        if (scenario.outcome === "multi-grab" && mergeCenter) {
          auraCx = mergeCenter[0];
          auraCy = mergeCenter[1];
          const wireframePs = scenario.focalPerkIndices.map(i => jumpPerkToWorld(anchor, scenario.jumpPerks[i]));
          const halfDist = Math.hypot(wireframePs[0][0] - wireframePs[1][0], wireframePs[0][1] - wireframePs[1][1]) / 2;
          initialR = halfDist + 16;
          finalR = 14;
          shrinkT = mergeT;
        } else if (scenario.focalPerkIndex != null && scenario.jumpPerks) {
          // Single hit on a multi-perk jump. Halo starts at the jump's perk-radius
          // (encompassing siblings) and tightens onto the rolled perk.
          const focalPerk = scenario.jumpPerks[scenario.focalPerkIndex];
          const [fx, fy] = jumpPerkToWorld(anchor, focalPerk);
          auraCx = fx;
          auraCy = fy;
          const focalVisualSize = sizeFor(focalPerk.cost) * focalScaleFactor(scenario, t);
          initialR = JUMP_RADIUS * 0.85;
          finalR = focalVisualSize * 0.40;
          shrinkT = easeInOutCubic(auraP);
        }
        if (auraCx != null) {
          const auraR = lerp(initialR, finalR, shrinkT);
          const auraOp = lerp(0.18, 0.58, auraP);
          parts.push(`<circle cx="${auraCx.toFixed(1)}" cy="${auraCy.toFixed(1)}" r="${auraR.toFixed(1)}" fill="none" stroke="${color}" stroke-width="1.4" opacity="${auraOp.toFixed(2)}" vector-effect="non-scaling-stroke"/>`);
        }
      }
      // Multi-grab flash burst stays a separate beat (punctuates the fusion moment).
      if (scenario.outcome === "multi-grab" && mergeCenter) {
        const flash = multiGrabFlash(scenario, t);
        if (flash > 0.04) {
          const r1 = 28 + flash * 14;
          const r2 = 14 + flash * 8;
          parts.push(`<circle cx="${mergeCenter[0].toFixed(1)}" cy="${mergeCenter[1].toFixed(1)}" r="${r1.toFixed(1)}" fill="white" opacity="${(flash * 0.16).toFixed(2)}"/>`);
          parts.push(`<circle cx="${mergeCenter[0].toFixed(1)}" cy="${mergeCenter[1].toFixed(1)}" r="${r2.toFixed(1)}" fill="white" opacity="${(flash * 0.32).toFixed(2)}"/>`);
        }
      }
    }

    return `<g class="interior">${parts.join("")}</g>`;
  }

  // Forge reach beam — layered mystical light rather than a flat polygon.
  //
  //   outer cone    wide outer cone, accent color, gaussian-blurred for a soft halo
  //   inner core    narrow inner cone, brighter / less saturated, also blurred
  //   particles     small white motes rising up the cone, driven by t for continuous flow
  //   apex bloom    soft radial pool of light where the beam meets the focal mote
  //
  // Apex sits AT the focal (reach → 1) or short of it (miss outcome, reach ≤ 0.78).
  // Base is just below the visible viewport so the beam reads as rising from off-frame.
  function renderBeam(scenario, t, camera) {
    if (!scenario.beam) return "";
    const op = beamOpacity(scenario, t);
    const reach = beamReach(scenario, t);
    if (op <= 0.02) return "";

    const focal = focalWorldPoint(scenario);
    const hue = SHAPES[scenario.shape].hue;
    const color = `oklch(0.82 0.14 ${hue})`;
    const coreColor = `oklch(0.95 0.06 ${hue})`;
    const bottomY = camera.y + camera.h + 30;

    const apexY = lerp(bottomY, focal[1], reach);
    // Beam tapers to a true point at the apex so the gaussian blur dissolves the tip
    // into the void on misses (where there's no focal star to mask a flat edge).
    // At hits the focal + apex bloom paint over the tip, so the point is invisible there too.
    const apexW = lerp(4, 0, reach);
    const baseW = 72;
    const coreApexW = lerp(2, 0, reach);
    const coreBaseW = 22;
    const beamLen = Math.max(1, bottomY - apexY);
    const id = `beam-${Math.floor(t * 1e6)}`;

    const outerPts = [
      [focal[0] - apexW, apexY],
      [focal[0] + apexW, apexY],
      [focal[0] + baseW, bottomY],
      [focal[0] - baseW, bottomY],
    ].map(p => p.join(",")).join(" ");
    const corePts = [
      [focal[0] - coreApexW, apexY],
      [focal[0] + coreApexW, apexY],
      [focal[0] + coreBaseW, bottomY],
      [focal[0] - coreBaseW, bottomY],
    ].map(p => p.join(",")).join(" ");

    // Particle motes rising along the beam. Each has a fixed seeded x-jitter; the
    // global phase cycles based on t so they continuously flow upward. Brightness
    // peaks mid-rise (sin curve) so they appear to emerge from the base and dissolve
    // near the apex.
    const particleCount = 14;
    const cycleSpeed = 2.6;
    const particles = [];
    for (let i = 0; i < particleCount; i++) {
      const seed = (i * 73 + 11) % 100;
      const phaseOffset = (seed / 100 + i / particleCount) % 1;
      const ph = ((t * cycleSpeed) + phaseOffset) % 1;       // 0 = at base, 1 = at apex
      const py = bottomY - ph * beamLen;
      const widthHere = lerp(baseW, apexW, ph) * 0.7;
      const xJ = ((seed * 1.618) % 1) - 0.5;
      const px = focal[0] + xJ * widthHere;
      const alpha = Math.sin(ph * Math.PI) * 0.55 * op;
      if (alpha < 0.04) continue;
      const psize = 0.7 + ((seed % 7) / 7) * 1.0;
      particles.push(`<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="${psize.toFixed(2)}" fill="white" opacity="${alpha.toFixed(2)}"/>`);
    }

    // Apex bloom — soft pool of light at the top of the beam. For miss the apex
    // never reaches the focal, so the bloom stays dim and tight (no successful lock).
    const isMiss = scenario.outcome === "miss";
    const bloomR = isMiss ? lerp(4, 9, reach) : lerp(8, 26, reach);
    const bloomOp = (isMiss ? 0.25 : 0.7) * reach * op;

    return `<defs>
      <linearGradient id="${id}-outer" x1="0" y1="${apexY}" x2="0" y2="${bottomY}" gradientUnits="userSpaceOnUse">
        <stop offset="0"    stop-color="${color}" stop-opacity="${(0.52 * op).toFixed(2)}"/>
        <stop offset="0.45" stop-color="${color}" stop-opacity="${(0.20 * op).toFixed(2)}"/>
        <stop offset="1"    stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="${id}-core" x1="0" y1="${apexY}" x2="0" y2="${bottomY}" gradientUnits="userSpaceOnUse">
        <stop offset="0"    stop-color="${coreColor}" stop-opacity="${(0.78 * op).toFixed(2)}"/>
        <stop offset="0.55" stop-color="${coreColor}" stop-opacity="${(0.30 * op).toFixed(2)}"/>
        <stop offset="1"    stop-color="${coreColor}" stop-opacity="0"/>
      </linearGradient>
      <filter id="${id}-blur-outer" x="-30%" y="-10%" width="160%" height="120%">
        <feGaussianBlur stdDeviation="6"/>
      </filter>
      <filter id="${id}-blur-core" x="-20%" y="-10%" width="140%" height="120%">
        <feGaussianBlur stdDeviation="2.4"/>
      </filter>
      <radialGradient id="${id}-bloom" cx="${focal[0]}" cy="${apexY}" r="${(bloomR * 1.6).toFixed(1)}" gradientUnits="userSpaceOnUse">
        <stop offset="0"    stop-color="white" stop-opacity="${(bloomOp * 0.85).toFixed(2)}"/>
        <stop offset="0.45" stop-color="${color}" stop-opacity="${(bloomOp * 0.45).toFixed(2)}"/>
        <stop offset="1"    stop-color="${color}" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <polygon points="${outerPts}" fill="url(#${id}-outer)" filter="url(#${id}-blur-outer)"/>
    <polygon points="${corePts}" fill="url(#${id}-core)" filter="url(#${id}-blur-core)"/>
    ${particles.join("")}
    <circle cx="${focal[0]}" cy="${apexY}" r="${(bloomR * 1.6).toFixed(1)}" fill="url(#${id}-bloom)"/>`;
  }

  function renderSpotlight(scenario, t, camera) {
    if (!scenario.spotlight) return "";
    const p = spotlightProgress(scenario, t);
    if (p < 0.03) return "";

    const focal = focalWorldPoint(scenario);
    const hue = SHAPES[scenario.shape].hue;
    const accent = `oklch(0.82 0.14 ${hue})`;
    // Tighten the hole as we lock on
    const radius = lerp(220, 64, p);
    const darkOp = lerp(0, 0.74, p);
    const glowOp = lerp(0, 0.12, p);
    const id = `spot-${Math.floor(t * 1e6)}`;

    return `<defs>
      <radialGradient id="${id}-glow" cx="${focal[0]}" cy="${focal[1]}" r="${(radius * 1.15).toFixed(1)}" gradientUnits="userSpaceOnUse">
        <stop offset="0"   stop-color="${accent}" stop-opacity="${glowOp.toFixed(2)}"/>
        <stop offset="1"   stop-color="${accent}" stop-opacity="0"/>
      </radialGradient>
      <radialGradient id="${id}-dark" cx="${focal[0]}" cy="${focal[1]}" r="${radius.toFixed(1)}" gradientUnits="userSpaceOnUse">
        <stop offset="0"    stop-color="black" stop-opacity="0"/>
        <stop offset="0.55" stop-color="black" stop-opacity="0"/>
        <stop offset="1"    stop-color="black" stop-opacity="${darkOp.toFixed(2)}"/>
      </radialGradient>
    </defs>
    <rect x="${(camera.x - 200).toFixed(1)}" y="${(camera.y - 200).toFixed(1)}" width="${(camera.w + 400).toFixed(1)}" height="${(camera.h + 400).toFixed(1)}" fill="url(#${id}-glow)"/>
    <rect x="${(camera.x - 200).toFixed(1)}" y="${(camera.y - 200).toFixed(1)}" width="${(camera.w + 400).toFixed(1)}" height="${(camera.h + 400).toFixed(1)}" fill="url(#${id}-dark)"/>`;
  }

  // ---- assemble full scene at time t ----
  function renderScene(scenario, t) {
    const camera = cameraAt(scenario, t);
    const blur = blurAt(scenario, t);
    const blurId = `blur-${Math.floor(t * 1e6)}`;
    const blurDefs = blur > 0.4
      ? `<filter id="${blurId}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${blur.toFixed(2)}"/></filter>`
      : "";
    const blurOpen  = blur > 0.4 ? `<g filter="url(#${blurId})">` : "";
    const blurClose = blur > 0.4 ? `</g>` : "";

    const content = [
      `<defs>${SYMBOL_DEFS}${blurDefs}</defs>`,
      // background stars are rendered in their own static layer behind this SVG
      blurOpen,
      renderSilhouette(scenario, t),
      renderClusterMarkers(scenario, t),
      blurClose,
      renderInteriorPerks(scenario, t),
      renderBeam(scenario, t, camera),
      renderSpotlight(scenario, t, camera),
    ].filter(Boolean).join("");

    return {
      viewBox: `${camera.x.toFixed(2)} ${camera.y.toFixed(2)} ${camera.w.toFixed(2)} ${camera.h.toFixed(2)}`,
      content,
    };
  }

  // ---- HUD / phase indicators inside the sky view have been intentionally removed.
  // The interior of the stage stays purely spacey — no techy chrome inside. The outer
  // controls (scrubber, scenario picker, time readout) still surface state.

  // ---- player loop ----

  const stageEl = document.getElementById("stage");
  const bgStageEl = document.getElementById("stage-bg");
  const scrubEl = document.getElementById("scrub");
  const playpauseEl = document.getElementById("playpause");
  const restartEl = document.getElementById("restart");
  const timeEl = document.getElementById("time");

  let playing = true;
  let virtualMs = 0;
  let lastRealTime = performance.now();
  let speed = 1.0;

  function setPlayingClass() {
    playpauseEl.classList.toggle("playing", playing);
  }
  setPlayingClass();

  function updateScrubFromElapsed() {
    scrubEl.value = String(Math.round((virtualMs / TOTAL_DURATION_MS) * 1000));
  }

  function pickSceneFromMs(ms) {
    const sceneIdx = Math.min(SCENES.length - 1, Math.floor(ms / CYCLE_MS));
    const inSceneMs = ms - sceneIdx * CYCLE_MS;
    const t = clamp01(inSceneMs / SCENE_DURATION_MS);
    return { sceneIdx, t };
  }

  function updateFrame(ms) {
    const { sceneIdx, t } = pickSceneFromMs(ms);
    const scenario = SCENES[sceneIdx];
    const { viewBox, content } = renderScene(scenario, t);
    stageEl.setAttribute("viewBox", viewBox);
    stageEl.innerHTML = content;
    // Refresh the static background starscape whenever the scenario changes (each scene
    // gets its own seeded starfield so they don't all look identical).
    if (bgStageEl.dataset.scene !== scenario.id) {
      bgStageEl.dataset.scene = scenario.id;
      bgStageEl.innerHTML = getBgScreenSpace(scenario);
    }

    timeEl.textContent = `${(ms / 1000).toFixed(2)}s / ${(TOTAL_DURATION_MS / 1000).toFixed(1)}s`;

    document.querySelectorAll(".scenario-picker button").forEach((b, i) => {
      b.classList.toggle("active", i === sceneIdx);
    });
  }

  function frameLoop(now) {
    const delta = now - lastRealTime;
    lastRealTime = now;
    if (playing) {
      virtualMs = (virtualMs + delta * speed) % TOTAL_DURATION_MS;
      updateScrubFromElapsed();
      updateFrame(virtualMs);
    }
    requestAnimationFrame(frameLoop);
  }

  function setPlaying(v) {
    playing = v;
    setPlayingClass();
  }

  // ---- controls ----
  playpauseEl.addEventListener("click", () => setPlaying(!playing));
  restartEl.addEventListener("click", () => {
    virtualMs = 0;
    updateScrubFromElapsed();
    updateFrame(virtualMs);
    setPlaying(true);
  });
  scrubEl.addEventListener("input", () => {
    setPlaying(false);
    virtualMs = (Number(scrubEl.value) / 1000) * TOTAL_DURATION_MS;
    updateFrame(virtualMs);
  });
  document.querySelectorAll(".scenario-picker button").forEach((b, i) => {
    b.addEventListener("click", () => {
      virtualMs = i * CYCLE_MS;
      updateScrubFromElapsed();
      updateFrame(virtualMs);
      setPlaying(true);
    });
  });
  document.querySelectorAll(".speed-group .ctl-pill").forEach(b => {
    b.addEventListener("click", () => {
      speed = Number(b.dataset.speed);
      document.querySelectorAll(".speed-group .ctl-pill").forEach(o => o.classList.toggle("active", o === b));
    });
  });

  // ---- keyboard ----
  window.addEventListener("keydown", e => {
    if (e.target.tagName === "INPUT") return;
    if (e.key === " ") { e.preventDefault(); setPlaying(!playing); }
    else if (e.key === "r" || e.key === "R") { restartEl.click(); }
    else if (e.key === "1") document.querySelector('[data-scenario="0"]').click();
    else if (e.key === "2") document.querySelector('[data-scenario="1"]').click();
    else if (e.key === "3") document.querySelector('[data-scenario="2"]').click();
  });

  // ---- kick off ----
  updateFrame(0);
  requestAnimationFrame(frameLoop);
})();

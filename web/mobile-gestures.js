/* =====================================================================
   Gesture helpers — bare-bones pointer event handlers that implement
   the contract laid out in gesture-contract.html.
   ===================================================================== */

const G = {
  TAP_MAX_DURATION: 250,
  TAP_MAX_MOVE: 8,
  DOUBLE_TAP_INTERVAL: 300,
  DOUBLE_TAP_RADIUS: 24,
  SWIPE_ENGAGE: 24,
  SWIPE_AXIS_LOCK: 1.5,
  SCRUB_STEP_PX: 56,
  THROW_DECAY: 600,
  LONG_PRESS: 450,
  CHROME_AUTOHIDE: 4000,
  ROTATION_ANIM: 220,
  HAPTIC_TICK: 8,
};

function haptic(ms = G.HAPTIC_TICK) {
  if (!window.__bcfPrefs?.haptics) return;
  try { navigator.vibrate?.(ms); } catch {}
}

/* Attach tap / double-tap / horizontal-swipe handlers to an element.
   Caller supplies callbacks. Returns a teardown fn.

   options:
     onTap()                    — single tap (debounced past double-tap window)
     onDoubleTap()              — double tap
     onSwipeStep(dir)           — fires every SCRUB_STEP_PX of horizontal swipe; dir = +1/-1
     onSwipeEnd(velocity)       — pointerup at end of an engaged swipe (px/ms)
*/
function attachSkyGestures(el, opts) {
  let down = null;
  let lastTapAt = 0;
  let lastTapXY = null;
  let pendingTapTimer = null;
  let engagedSwipe = false;
  let swipeAccum = 0;
  let velSamples = [];

  function onDown(e) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    el.setPointerCapture?.(e.pointerId);
    down = {
      x: e.clientX, y: e.clientY, t: performance.now(),
      pid: e.pointerId, moved: 0, dxTotal: 0, dyTotal: 0,
    };
    engagedSwipe = false;
    swipeAccum = 0;
    velSamples = [{ x: e.clientX, t: performance.now() }];
  }
  function onMove(e) {
    if (!down || e.pointerId !== down.pid) return;
    const dx = e.clientX - down.x;
    const dy = e.clientY - down.y;
    down.dxTotal = dx;
    down.dyTotal = dy;
    down.moved = Math.max(down.moved, Math.hypot(dx, dy));
    velSamples.push({ x: e.clientX, t: performance.now() });
    if (velSamples.length > 8) velSamples.shift();

    if (!engagedSwipe && Math.abs(dx) >= G.SWIPE_ENGAGE && Math.abs(dx) >= G.SWIPE_AXIS_LOCK * Math.abs(dy)) {
      engagedSwipe = true;
      swipeAccum = dx;
      // First engagement: cancel any pending tap
      if (pendingTapTimer) { clearTimeout(pendingTapTimer); pendingTapTimer = null; }
    }
    if (engagedSwipe) {
      // Fire step events for each whole SCRUB_STEP_PX traversed since last fire
      const diff = dx - swipeAccum;
      if (Math.abs(diff) >= G.SCRUB_STEP_PX) {
        const steps = Math.trunc(diff / G.SCRUB_STEP_PX);
        for (let i = 0; i < Math.abs(steps); i += 1) {
          opts.onSwipeStep?.(Math.sign(steps));
          haptic();
        }
        swipeAccum += steps * G.SCRUB_STEP_PX;
      }
    }
  }
  function onUp(e) {
    if (!down || e.pointerId !== down.pid) return;
    el.releasePointerCapture?.(e.pointerId);
    const dur = performance.now() - down.t;
    const moved = down.moved;
    const wasSwipe = engagedSwipe;

    if (wasSwipe) {
      // Compute release velocity (px/ms) over the last ~80ms of samples
      const now = performance.now();
      const recent = velSamples.filter(s => now - s.t < 80);
      let vel = 0;
      if (recent.length >= 2) {
        const a = recent[0], b = recent[recent.length - 1];
        const dt = b.t - a.t;
        if (dt > 0) vel = (b.x - a.x) / dt;
      }
      opts.onSwipeEnd?.(vel);
    } else if (moved <= G.TAP_MAX_MOVE && dur <= G.TAP_MAX_DURATION) {
      // It's a tap. Check for double-tap.
      const now = performance.now();
      const inDoubleWindow = now - lastTapAt <= G.DOUBLE_TAP_INTERVAL;
      const closeEnough = lastTapXY && Math.hypot(e.clientX - lastTapXY.x, e.clientY - lastTapXY.y) <= G.DOUBLE_TAP_RADIUS;
      if (inDoubleWindow && closeEnough) {
        if (pendingTapTimer) { clearTimeout(pendingTapTimer); pendingTapTimer = null; }
        lastTapAt = 0; lastTapXY = null;
        opts.onDoubleTap?.();
      } else {
        lastTapAt = now;
        lastTapXY = { x: e.clientX, y: e.clientY };
        // Fire single-tap IMMEDIATELY (per ambiguity resolution in contract);
        // double-tap still detects from the next tap and adds the snap-to-live behavior.
        opts.onTap?.();
      }
    }
    down = null; engagedSwipe = false; swipeAccum = 0; velSamples = [];
  }
  function onCancel(e) {
    if (down && e.pointerId === down.pid) {
      if (pendingTapTimer) { clearTimeout(pendingTapTimer); pendingTapTimer = null; }
      down = null; engagedSwipe = false; swipeAccum = 0;
    }
  }

  el.addEventListener("pointerdown", onDown);
  el.addEventListener("pointermove", onMove);
  el.addEventListener("pointerup", onUp);
  el.addEventListener("pointercancel", onCancel);

  return () => {
    el.removeEventListener("pointerdown", onDown);
    el.removeEventListener("pointermove", onMove);
    el.removeEventListener("pointerup", onUp);
    el.removeEventListener("pointercancel", onCancel);
    if (pendingTapTimer) clearTimeout(pendingTapTimer);
  };
}

/* Attach drag-to-scrub handler to a rail. Caller supplies a fn that
   maps fraction (0..1 across the rail's width) to a word-position
   commit.

   onScrub(fraction) — fires on every move and on initial down.
   onScrubEnd()      — fires on release.
*/
function attachRailScrub(el, opts) {
  let down = null;
  let lastRollIdx = null;

  function fractionFromEvent(e) {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  }
  function onDown(e) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    el.setPointerCapture?.(e.pointerId);
    down = { pid: e.pointerId };
    const f = fractionFromEvent(e);
    lastRollIdx = opts.onScrub?.(f) ?? null;
  }
  function onMove(e) {
    if (!down || e.pointerId !== down.pid) return;
    const f = fractionFromEvent(e);
    const idx = opts.onScrub?.(f);
    if (idx != null && lastRollIdx != null && idx !== lastRollIdx) {
      haptic();
    }
    if (idx != null) lastRollIdx = idx;
  }
  function onUp(e) {
    if (!down || e.pointerId !== down.pid) return;
    el.releasePointerCapture?.(e.pointerId);
    down = null;
    lastRollIdx = null;
    opts.onScrubEnd?.();
  }

  el.addEventListener("pointerdown", onDown);
  el.addEventListener("pointermove", onMove);
  el.addEventListener("pointerup", onUp);
  el.addEventListener("pointercancel", onUp);

  return () => {
    el.removeEventListener("pointerdown", onDown);
    el.removeEventListener("pointermove", onMove);
    el.removeEventListener("pointerup", onUp);
    el.removeEventListener("pointercancel", onUp);
  };
}

window.GestureConstants = G;
window.attachSkyGestures = attachSkyGestures;
window.attachRailScrub = attachRailScrub;
window.haptic = haptic;

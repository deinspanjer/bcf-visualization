from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _node_eval(source: str) -> str:
    result = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def test_roll_marker_model_classifies_paid_free_and_untracked_shapes() -> None:
    source = """
      import { rollMarkerModel } from './web/viz-model.js';
      const rolls = [
        {
          outcome: 'hit',
          constellation: 'Toolkits',
          purchased_perks: [{ name: 'A', cost: 100, free: false }],
          purchased_perk_cost_total: 100,
          free_perks: [],
        },
        {
          outcome: 'hit',
          constellation: 'Quality',
          purchased_perks: [
            { name: 'A', cost: 100, free: false },
            { name: 'B', cost: 200, free: false },
          ],
          purchased_perk_cost_total: 300,
          free_perks: [{ name: 'Free A', constellation: 'Quality' }],
        },
        {
          outcome: 'hit',
          constellation: 'Knowledge',
          purchased_perks: [
            { name: 'A', cost: 100, free: false },
            { name: 'B', cost: 100, free: false },
            { name: 'C', cost: 100, free: false },
            { name: 'D', cost: 100, free: false },
          ],
          purchased_perk_cost_total: 400,
          free_perks: [],
        },
        {
          outcome: 'hit',
          evidence_kind: 'untracked_acquisition',
          constellation: 'Toolkits',
          purchased_perks: [{ name: 'A', cost: 100, free: false }],
          purchased_perk_cost_total: 100,
          free_perks: [],
        },
        { outcome: 'miss', constellation: 'Magic', available_cp: 50 },
      ];
      console.log(JSON.stringify(rolls.map(rollMarkerModel)));
    """
    assert json.loads(_node_eval(source)) == [
        {
            "kind": "single",
            "paidCount": 1,
            "freeCount": 0,
            "isUntracked": False,
            "isMissLike": False,
            "cost": 100,
        },
        {
            "kind": "binary-free",
            "paidCount": 2,
            "freeCount": 1,
            "isUntracked": False,
            "isMissLike": False,
            "cost": 300,
        },
        {
            "kind": "trinary",
            "paidCount": 4,
            "freeCount": 0,
            "isUntracked": False,
            "isMissLike": False,
            "cost": 400,
        },
        {
            "kind": "single-untracked",
            "paidCount": 1,
            "freeCount": 0,
            "isUntracked": True,
            "isMissLike": False,
            "cost": 100,
        },
        {
            "kind": "miss",
            "paidCount": 0,
            "freeCount": 0,
            "isUntracked": False,
            "isMissLike": True,
            "cost": None,
        },
    ]


def test_skipped_predicted_roll_title_explains_narrative_alignment() -> None:
    source = """
      import { skippedPredictedRollTitle } from './web/viz-model.js';
      const chapter = { chapter_num: '9' };
      const marker = { slot_index: 2, roll_number: 35 };
      console.log(skippedPredictedRollTitle(marker, chapter));
    """
    assert _node_eval(source) == (
        "ch 9 · predicted roll #35 · skipped to align with narrative mentions"
    )


def test_constellation_progress_hides_late_constellations_until_opened() -> None:
    source = """
      import { buildConstellationProgressIndex } from './web/viz-model.js';
      const facts = {
        chapters: [
          {
            chapter_num: '1',
            constellation_progress: [
              { name: 'Toolkits', count: 1, total: 3, discovered: 2, discovered_pct: 67, complete: false, visible: true },
              { name: 'Personal Reality', count: 0, total: 2, discovered: 0, discovered_pct: 0, complete: false, visible: false },
              { name: 'Capstone', count: 0, total: 2, discovered: 0, discovered_pct: 0, complete: false, visible: false },
            ],
          },
          {
            chapter_num: '62',
            constellation_progress: [
              { name: 'Toolkits', count: 1, total: 3, discovered: 2, discovered_pct: 67, complete: false, visible: true },
              { name: 'Personal Reality', count: 2, total: 2, discovered: 1, discovered_pct: 50, complete: false, visible: true },
              { name: 'Capstone', count: 0, total: 2, discovered: 0, discovered_pct: 0, complete: false, visible: false },
            ],
          },
          {
            chapter_num: '63',
            constellation_progress: [
              { name: 'Toolkits', count: 1, total: 3, discovered: 2, discovered_pct: 67, complete: false, visible: true },
              { name: 'Personal Reality', count: 2, total: 2, discovered: 1, discovered_pct: 50, complete: false, visible: true },
              { name: 'Capstone', count: 2, total: 2, discovered: 2, discovered_pct: 100, complete: true, visible: true },
            ],
          },
        ],
      };
      const order = ['Toolkits', 'Personal Reality', 'Capstone'];
      const idx = buildConstellationProgressIndex(facts, order);
      const ch1 = idx.byChapter.get('1');
      const ch62 = idx.byChapter.get('62');
      const ch63 = idx.byChapter.get('63');
      console.log(JSON.stringify({
        ch1Visible: ch1.rows.map(r => r.name),
        toolkits: ch1.byName.get('Toolkits'),
        ch62Visible: ch62.rows.map(r => r.name),
        personal: ch62.byName.get('Personal Reality'),
        capstone: ch63.byName.get('Capstone'),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "ch1Visible": ["Toolkits"],
        "toolkits": {
            "name": "Toolkits",
            "count": 1,
            "total": 3,
            "discovered": 2,
            "discoveredPct": 67,
            "complete": False,
            "visible": True,
        },
        "ch62Visible": ["Toolkits", "Personal Reality"],
        "personal": {
            "name": "Personal Reality",
            "count": 2,
            "total": 2,
            "discovered": 1,
            "discoveredPct": 50,
            "complete": False,
            "visible": True,
        },
        "capstone": {
            "name": "Capstone",
            "count": 2,
            "total": 2,
            "discovered": 2,
            "discoveredPct": 100,
            "complete": True,
            "visible": True,
        },
    }


def test_field_log_uses_evidence_quotes_and_placeholder_without_synthetic_prose() -> None:
    source = """
      import { fieldLogModel } from './web/viz-model.js';
      const quoted = fieldLogModel({
        evidence_quotes: [{ text: 'Actual Joe narration.' }, { text: 'Second quote.' }],
        evidence_kind: 'narrative',
        roll_number: 7,
        chapter_num: '2',
        outcome: 'hit',
      }, { chapter_num: '2' });
      const missing = fieldLogModel({
        evidence_quotes: [],
        evidence_kind: 'predicted',
        roll_number: 8,
        chapter_num: '3',
        outcome: 'miss',
      }, { chapter_num: '3' });
      console.log(JSON.stringify({ quoted, missing }));
    """
    assert json.loads(_node_eval(source)) == {
        "quoted": {
            "kind": "quotes",
            "heading": "Field log",
            "source": "narrative",
            "quotes": ["Actual Joe narration.", "Second quote."],
            "placeholder": None,
            "rollLabel": "roll 7 · ch 2 · HIT",
        },
        "missing": {
            "kind": "placeholder",
            "heading": "Field log",
            "source": "predicted",
            "quotes": [],
            "placeholder": "No log data for ch 3.",
            "rollLabel": "roll 8 · ch 3 · MISS",
        },
    }


def test_on_roll_behavior_windows_classify_cinematic_pause_and_quick() -> None:
    # The decoupled cinematic redesign collapses the three behaviors onto
    # a single firing window (ROLL_FIRING_WINDOW_WORDS = 700):
    #   - cinematic + pause: lock during firing (onRoll=True inside the
    #     window). wordPos lock is enforced in app.js by suppressing
    #     advance, not by speedMultiplier scaling.
    #   - quick: no lock, never reports onRoll — scrubber flies through.
    # speedMultiplier is preserved in the return shape but is always 1 now;
    # the lock is binary (advance vs hold), not a slowdown.
    source = """
      import { onRollPlaybackState } from './web/viz-model.js';
      const roll = { word_position: 10000 };
      console.log(JSON.stringify({
        cinematic: onRollPlaybackState(roll, 10650, 'cinematic'),
        cinematicOutside: onRollPlaybackState(roll, 10750, 'cinematic'),
        pause: onRollPlaybackState(roll, 10650, 'pause'),
        pauseOutside: onRollPlaybackState(roll, 10750, 'pause'),
        quickInside: onRollPlaybackState(roll, 10010, 'quick'),
        quickOutside: onRollPlaybackState(roll, 10750, 'quick'),
        defaultIsCinematic: onRollPlaybackState(roll, 10650),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "cinematic": {"behavior": "cinematic", "onRoll": True, "speedMultiplier": 1},
        "cinematicOutside": {"behavior": "cinematic", "onRoll": False, "speedMultiplier": 1},
        "pause": {"behavior": "pause", "onRoll": True, "speedMultiplier": 1},
        "pauseOutside": {"behavior": "pause", "onRoll": False, "speedMultiplier": 1},
        "quickInside": {"behavior": "quick", "onRoll": False, "speedMultiplier": 1},
        "quickOutside": {"behavior": "quick", "onRoll": False, "speedMultiplier": 1},
        "defaultIsCinematic": {"behavior": "cinematic", "onRoll": True, "speedMultiplier": 1},
    }


def test_on_roll_behavior_falls_back_to_cinematic_for_unknown_values() -> None:
    # Stale localStorage values from the prior `normal` / `bullet-time` schema
    # must not survive — readStoredChoice in app.js handles that fallback at
    # boot, and onRollPlaybackState's own behavior normalization belt-and-
    # suspenders the same default.
    source = """
      import { onRollPlaybackState } from './web/viz-model.js';
      const roll = { word_position: 10000 };
      console.log(JSON.stringify({
        normal: onRollPlaybackState(roll, 10650, 'normal'),
        bullet: onRollPlaybackState(roll, 10650, 'bullet-time'),
        empty: onRollPlaybackState(roll, 10650, ''),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "normal": {"behavior": "cinematic", "onRoll": True, "speedMultiplier": 1},
        "bullet": {"behavior": "cinematic", "onRoll": True, "speedMultiplier": 1},
        "empty": {"behavior": "cinematic", "onRoll": True, "speedMultiplier": 1},
    }


def test_sky_carousel_layout_preserves_minimum_spacing_for_close_rolls() -> None:
    source = """
      import { buildSkyCarouselLayout } from './web/viz-model.js';
      const rolls = [
        { roll_number: 1, word_position: 2253 },
        { roll_number: 2, word_position: 4253 },
        { roll_number: 3, word_position: 6253 },
      ];
      const layout = buildSkyCarouselLayout(rolls, {
        totalWords: 2_600_000,
        wordPos: 4253,
        averageCardWidth: 348,
        minCardSpacing: 440,
      });
      console.log(JSON.stringify({
        gaps: [
          layout.positions[1] - layout.positions[0],
          layout.positions[2] - layout.positions[1],
        ],
        playheadPx: layout.playheadPx,
        activePx: layout.positions[1],
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["gaps"] == [440, 440]
    assert result["playheadPx"] == result["activePx"]


def test_sky_carousel_layout_leaves_roll_droughts_empty_after_dense_groups() -> None:
    source = """
      import { buildSkyCarouselLayout } from './web/viz-model.js';
      const rolls = [
        { roll_number: 1, word_position: 0 },
        { roll_number: 2, word_position: 2_000 },
        { roll_number: 3, word_position: 4_000 },
        { roll_number: 4, word_position: 900_000 },
      ];
      const layout = buildSkyCarouselLayout(rolls, {
        totalWords: 1_000_000,
        wordPos: 450_000,
        averageCardWidth: 348,
        minCardSpacing: 440,
      });
      const desiredLast = rolls[3].word_position * layout.pxPerWord;
      console.log(JSON.stringify({
        playheadPx: layout.playheadPx,
        positions: layout.positions,
        desiredLast,
        nearestCardDistance: Math.min(
          ...layout.positions.map(position => Math.abs(position - layout.playheadPx)),
        ),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["positions"][3] == result["desiredLast"]
    assert result["nearestCardDistance"] > 440


def test_sky_carousel_layout_spreads_every_dense_cluster_in_view() -> None:
    # Two dense clusters separated by a gap that is just wider than
    # minCardSpacing — exactly the early-story shape that produced overlapping
    # constellation cards on the right half of the viewport (rolls #10–#13)
    # while the playhead sat on the left-side cluster (rolls near #9). The
    # old single-cluster spread left the far-side cluster un-separated.
    source = """
      import { buildSkyCarouselLayout } from './web/viz-model.js';
      const rolls = [
        { roll_number: 1, word_position: 12_581 },
        { roll_number: 2, word_position: 14_866 },
        { roll_number: 3, word_position: 16_866 },
        { roll_number: 4, word_position: 18_866 },
        { roll_number: 5, word_position: 24_378 },
        { roll_number: 6, word_position: 26_378 },
        { roll_number: 7, word_position: 28_378 },
        { roll_number: 8, word_position: 30_378 },
      ];
      const layout = buildSkyCarouselLayout(rolls, {
        totalWords: 2_645_680,
        wordPos: 21_000,
        averageCardWidth: 348,
        minCardSpacing: 440,
      });
      const gaps = [];
      for (let i = 1; i < layout.positions.length; i += 1) {
        gaps.push(layout.positions[i] - layout.positions[i - 1]);
      }
      console.log(JSON.stringify({ gaps, positions: layout.positions }));
    """
    result = json.loads(_node_eval(source))
    # Every adjacent pair must be at least minCardSpacing apart, on BOTH
    # sides of the playhead — not only inside the playhead's own cluster.
    for gap in result["gaps"]:
        assert gap >= 440 - 1e-6, (
            f"gap {gap} < 440 (positions={result['positions']})"
        )


def test_constellation_outlines_are_roll_time_knowledge_not_later_playback_state() -> None:
    source = """
      import {
        buildConstellationKnowledgeIndex,
        constellationOutlineVisibleForRoll,
      } from './web/viz-model.js';
      const alchemyMissBeforeReveal = {
        roll_number: 1,
        outcome: 'miss',
        constellation: 'Alchemy',
        word_position: 2253,
        purchased_perks: [],
        free_perks: [],
      };
      const clothingHit = {
        roll_number: 2,
        outcome: 'hit',
        constellation: 'Clothing',
        word_position: 4253,
        purchased_perks: [{ name: 'Fashion', cost: 200 }],
        free_perks: [],
      };
      const alchemyHit = {
        roll_number: 5,
        outcome: 'hit',
        constellation: 'Alchemy',
        word_position: 10581,
        purchased_perks: [{ name: 'Alchemist', cost: 200 }],
        free_perks: [],
      };
      const alchemyMissAfterReveal = {
        roll_number: 6,
        outcome: 'miss',
        constellation: 'Alchemy',
        word_position: 12581,
        purchased_perks: [],
        free_perks: [],
      };
      const knowledge = buildConstellationKnowledgeIndex([
        alchemyMissBeforeReveal,
        clothingHit,
        alchemyHit,
        alchemyMissAfterReveal,
      ]);
      console.log(JSON.stringify({
        alchemyMissBeforeReveal: constellationOutlineVisibleForRoll(alchemyMissBeforeReveal, knowledge),
        clothingHit: constellationOutlineVisibleForRoll(clothingHit, knowledge),
        alchemyHit: constellationOutlineVisibleForRoll(alchemyHit, knowledge),
        alchemyMissAfterReveal: constellationOutlineVisibleForRoll(alchemyMissAfterReveal, knowledge),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "alchemyMissBeforeReveal": False,
        "clothingHit": True,
        "alchemyHit": True,
        "alchemyMissAfterReveal": True,
    }


def test_constellation_outline_knowledge_uses_roll_order_before_display_position() -> None:
    source = """
      import {
        buildConstellationKnowledgeIndex,
        constellationOutlineVisibleForRoll,
      } from './web/viz-model.js';
      const missDisplayedLater = {
        roll_number: 1,
        outcome: 'miss',
        constellation: 'Alchemy',
        word_position: 5_000,
        purchased_perks: [],
        free_perks: [],
      };
      const hitDisplayedEarlier = {
        roll_number: 2,
        outcome: 'hit',
        constellation: 'Alchemy',
        word_position: 1_000,
        purchased_perks: [{ name: 'Alchemist', cost: 200 }],
        free_perks: [],
      };
      const knowledge = buildConstellationKnowledgeIndex([
        missDisplayedLater,
        hitDisplayedEarlier,
      ]);
      console.log(JSON.stringify({
        missDisplayedLater: constellationOutlineVisibleForRoll(missDisplayedLater, knowledge),
        hitDisplayedEarlier: constellationOutlineVisibleForRoll(hitDisplayedEarlier, knowledge),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "missDisplayedLater": False,
        "hitDisplayedEarlier": True,
    }


def test_roll_log_filtering_sorting_and_click_targets_use_word_positions() -> None:
    source = """
      import { buildRollLogRows } from './web/viz-model.js';
      const rolls = [
        { roll_number: 1, outcome: 'hit', word_position: 1000, chapter_num: '1',
          purchased_perks: [{ name: 'Single', cost: 100, free: false }], free_perks: [] },
        { roll_number: 2, outcome: 'miss', word_position: 2000, chapter_num: '2',
          miss_cost_estimate: 300, purchased_perks: [], free_perks: [] },
        { roll_number: 3, outcome: 'hit', word_position: 3000, chapter_num: '2',
          purchased_perks: [
            { name: 'Multi A', cost: 200, free: false },
            { name: 'Multi B', cost: 400, free: false },
          ], free_perks: [{ name: 'Free C', free: true }] },
      ];
      console.log(JSON.stringify({
        all: buildRollLogRows(rolls, 3000).map(r => [r.rollNumber, r.outcome, r.clickWord]),
        misses: buildRollLogRows(rolls, 3000, { filter: 'miss' }).map(r => r.rollNumber),
        multi: buildRollLogRows(rolls, 3000, { filter: 'multi' }).map(r => [r.rollNumber, r.names]),
        cost: buildRollLogRows(rolls, 3000, { sort: 'cost' }).map(r => [r.rollNumber, r.paidCost]),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "all": [[3, "hit", 3000], [2, "miss", 2000], [1, "hit", 1000]],
        "misses": [2],
        "multi": [[3, ["Multi A", "Multi B", "Free C (free)"]]],
        "cost": [[3, 600], [2, 300], [1, 100]],
    }


def test_focus_anim_duration_is_constant_across_behaviors() -> None:
    # Under the decoupled cinematic redesign, the animation always plays out
    # at full wall-clock pace — wordPos is locked during firing so there's
    # no longer a need to stretch or compress the camera duration to match
    # word advance. focusAnimDurationFor ignores its argument.
    source = """
      import { focusAnimDurationFor, FOCUS_ANIM_DURATION_MS } from './web/viz-model.js';
      console.log(JSON.stringify({
        base: FOCUS_ANIM_DURATION_MS,
        cinematic: focusAnimDurationFor('cinematic'),
        pause: focusAnimDurationFor('pause'),
        quick: focusAnimDurationFor('quick'),
        unknown: focusAnimDurationFor('something-else'),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "base": 2800,
        "cinematic": 2800,
        "pause": 2800,
        "quick": 2800,
        "unknown": 2800,
    }


def test_focus_camera_viewbox_interpolates_wide_reveal_hit_keyframes() -> None:
    # Phase 2 camera math. At t=0 the camera is the wide world view centered
    # on the 1600x1000 stage. At t=1 it's the tight 192x120 hit view centered
    # on the focal star. Intermediate t values lie between via easeInOutCubic.
    source = """
      import { focusCameraViewBox } from './web/viz-model.js';
      const scene = {
        branch: 'single-hit',
        focalStars: [{ id: 'star-1', x: 0, y: 0, cost: 200 }],
        ambientStars: [],
        anchorWorld: [600, 400],
        hue: 196,
        vertexSource: 'perks',
      };
      // At t=0 the camera is the wide world view.
      const wide = focusCameraViewBox(0, scene);
      // Mid pan/scale.
      const mid = focusCameraViewBox(0.5, scene);
      // Hit view at t=1: tight box centered on focal (600, 400 because
      // vertexSource = 'perks' means anchorWorld IS the focal world coord).
      const hit = focusCameraViewBox(1, scene);
      console.log(JSON.stringify({ wide, mid, hit }));
    """
    result = json.loads(_node_eval(source))
    # Wide view: viewBox "x y w h" = "(800-640) (500-400) 1280 800" = "160 100 1280 800"
    assert result["wide"] == "160 100 1280 800"
    # Hit view: "(600-96) (400-60) 192 120" = "504 340 192 120"
    assert result["hit"] == "504 340 192 120"
    # Mid is some interpolated state — between wide and hit, neither equal.
    assert result["mid"] != result["wide"]
    assert result["mid"] != result["hit"]


def test_motion_blur_curve_rises_peaks_and_falls_under_blur_window() -> None:
    # Phase 3 curve. stdDeviation is 0 outside [0.22, 0.62], rises linearly
    # 0 → 8 across [0.22, 0.50], then falls linearly 8 → 0 across [0.50, 0.62].
    # The held final frame at t=1 must be 0 (silhouette has resolved).
    source = """
      import { motionBlurStdDeviation } from './web/viz-model.js';
      console.log(JSON.stringify({
        zero:        motionBlurStdDeviation(0),
        before:      motionBlurStdDeviation(0.21),
        riseStart:   motionBlurStdDeviation(0.22),
        midRise:     motionBlurStdDeviation(0.36),
        peak:        motionBlurStdDeviation(0.50),
        midFall:     motionBlurStdDeviation(0.56),
        fallEnd:     motionBlurStdDeviation(0.62),
        after:       motionBlurStdDeviation(0.75),
        held:        motionBlurStdDeviation(1.0),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["zero"] == 0
    assert result["before"] == 0
    assert result["riseStart"] == 0
    assert result["peak"] == 8
    assert result["fallEnd"] == 0
    assert result["after"] == 0
    assert result["held"] == 0
    # Mid-rise ~half-way between 0.22 and 0.50 should give ~4.
    assert abs(result["midRise"] - 4.0) < 0.05
    # Mid-fall (~halfway between 0.50 and 0.62) should give ~4.
    assert abs(result["midFall"] - 4.0) < 0.5


def test_split_progress_reveals_interior_perks_across_0_40_to_0_58() -> None:
    # Phase 3 split curve: easeInOutCubic across [0.40, 0.58]. Zero before
    # 0.40, one after 0.58, monotonic in between. The held-final-frame state
    # at t=1 must be 1 (interior perks fully resolved).
    source = """
      import { splitProgress } from './web/viz-model.js';
      console.log(JSON.stringify({
        zero:    splitProgress(0),
        before:  splitProgress(0.39),
        start:   splitProgress(0.40),
        mid:     splitProgress(0.49),
        end:     splitProgress(0.58),
        after:   splitProgress(0.75),
        held:    splitProgress(1),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["zero"] == 0
    assert result["before"] == 0
    assert result["start"] == 0
    assert result["end"] == 1
    assert result["after"] == 1
    assert result["held"] == 1
    # easeInOutCubic at 0.5 input → 0.5 output, so midpoint should be ~0.5.
    assert abs(result["mid"] - 0.5) < 0.02


def test_silhouette_and_marker_fade_curves_resolve_to_zero_by_t_0_60() -> None:
    # Phase 3 fades: silhouette 0.62, vertex pin 0.85, non-focal cluster 0.65.
    # All multiply by (1 - phase(t, 0.50, 0.60)) so they hold their base until
    # t=0.50, fade to 0 by t=0.60. The held-final-frame state at t=1 is 0.
    source = """
      import {
        silhouetteOpacity, vertexPinOpacity, nonFocalClusterOpacity,
        focalClusterOpacity, nonFocalInteriorOpacity,
      } from './web/viz-model.js';
      console.log(JSON.stringify({
        silhStart:      silhouetteOpacity(0),
        silhHold:       silhouetteOpacity(0.50),
        silhEnd:        silhouetteOpacity(0.60),
        silhHeld:       silhouetteOpacity(1),
        pinStart:       vertexPinOpacity(0),
        pinEnd:         vertexPinOpacity(0.60),
        nonFocStart:    nonFocalClusterOpacity(0),
        nonFocEnd:      nonFocalClusterOpacity(0.60),
        focalAtZero:    focalClusterOpacity(0),
        focalSplitEnd:  focalClusterOpacity(0.58),
        focalHeld:      focalClusterOpacity(1),
        ambStart:       nonFocalInteriorOpacity(0, false),
        ambHeld:        nonFocalInteriorOpacity(1, false),
        ambMissHeld:    nonFocalInteriorOpacity(1, true),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["silhStart"] == 0.62
    assert result["silhHold"] == 0.62
    assert abs(result["silhEnd"]) < 1e-9
    assert abs(result["silhHeld"]) < 1e-9
    assert result["pinStart"] == 0.85
    assert abs(result["pinEnd"]) < 1e-9
    assert result["nonFocStart"] == 0.65
    assert abs(result["nonFocEnd"]) < 1e-9
    # Focal cluster marker holds full opacity at t=0 (no split yet), and is
    # fully gone once the split completes.
    assert result["focalAtZero"] == 0.85
    assert abs(result["focalSplitEnd"]) < 1e-9
    assert abs(result["focalHeld"]) < 1e-9
    # Interior ambient perks: 0 before the split starts; held-final = dimFloor.
    assert result["ambStart"] == 0
    assert abs(result["ambHeld"] - 0.28) < 1e-9
    assert abs(result["ambMissHeld"] - 0.30) < 1e-9


# The old cascade + cp-fraction coordinate helpers are gone. Predicted and
# curated positions are now canonical fields on every bundle roll
# (`epub_word_offset_predicted` / `epub_word_offset_curated`), computed in
# the pipeline via scripts/cp_epub_map.py. UI position selection is
# trivial; the invariants live in:
#   tests/test_cp_epub_map.py
#   tests/test_chapter_alignment_fingerprints.py
#   tests/test_roll_position_invariants.py


def test_ease_out_cubic_runs_from_zero_to_one() -> None:
    # Phase 4 — easeOutCubic powers the beam-reach curve. Hit the endpoints
    # exactly so the held-final-frame contract (t=1 → 1) holds.
    source = """
      import { easeOutCubic } from './web/viz-model.js';
      console.log(JSON.stringify({
        zero: easeOutCubic(0),
        one: easeOutCubic(1),
        mid: easeOutCubic(0.5),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["zero"] == 0
    assert result["one"] == 1
    # 1 - (1 - 0.5)^3 = 1 - 0.125 = 0.875
    assert abs(result["mid"] - 0.875) < 1e-9


def test_beam_opacity_rises_then_holds_across_phase_4_window() -> None:
    # Phase 4 — beam opacity is 0 before t=0.55, eases up to 0.92 at t=0.80,
    # then holds at 0.92 through the held final frame.
    source = """
      import { beamOpacity } from './web/viz-model.js';
      console.log(JSON.stringify({
        before: beamOpacity(0.50),
        start: beamOpacity(0.55),
        end: beamOpacity(0.80),
        late: beamOpacity(0.95),
        held: beamOpacity(1.0),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["before"] == 0
    assert result["start"] == 0
    assert abs(result["end"] - 0.92) < 1e-9
    assert abs(result["late"] - 0.92) < 1e-9
    assert abs(result["held"] - 0.92) < 1e-9


def test_beam_reach_eases_to_one_for_hits_and_caps_at_0_78_for_misses() -> None:
    # Phase 4 — beam reach is 0 before t=0.55, eases up to 1.0 at t=0.82
    # (held to t=1). Miss outcome scales the raw curve by 0.78 — the beam
    # stalls visibly short of the focal so "no lock" reads distinct from a
    # successful connection.
    source = """
      import { beamReach } from './web/viz-model.js';
      console.log(JSON.stringify({
        hitBefore: beamReach(0.50, 'hit'),
        hitFull: beamReach(0.82, 'hit'),
        hitHeld: beamReach(1.0, 'hit'),
        missBefore: beamReach(0.50, 'miss'),
        missFull: beamReach(0.82, 'miss'),
        missHeld: beamReach(1.0, 'miss'),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["hitBefore"] == 0
    assert abs(result["hitFull"] - 1.0) < 1e-9
    assert abs(result["hitHeld"] - 1.0) < 1e-9
    assert result["missBefore"] == 0
    assert abs(result["missFull"] - 0.78) < 1e-9
    assert abs(result["missHeld"] - 0.78) < 1e-9


def test_focal_world_from_scene_picks_focal_or_miss_candidate_or_anchor() -> None:
    # Phase 4 — the beam, the camera, and any future overlays all need the
    # same answer for "where is the focal in world coords." Single source of
    # truth: focusScene's starWorldById for single-hit + miss-with-candidate,
    # anchorWorld as the degenerate fallback.
    source = """
      import { focalWorldFromScene, WORLD_STAGE_WIDTH, WORLD_STAGE_HEIGHT } from './web/viz-model.js';
      const hit = {
        branch: 'single-hit',
        focalStars: [{ id: 'p-1' }],
        ambientStars: [],
        anchorWorld: [600, 400],
        hue: 196,
        vertexSource: 'perks',
        starWorldById: new Map([['p-1', [612, 388]]]),
      };
      const miss = {
        branch: 'miss',
        focalStars: [],
        ambientStars: [],
        missCandidate: { id: 'p-9' },
        anchorWorld: [400, 300],
        hue: 30,
        vertexSource: 'perks',
        starWorldById: new Map([['p-9', [420, 290]]]),
      };
      const degenerate = {
        branch: 'miss',
        focalStars: [],
        ambientStars: [],
        anchorWorld: [123, 456],
        hue: 196,
        vertexSource: null,
        starWorldById: new Map(),
      };
      const empty = {};
      console.log(JSON.stringify({
        hit: focalWorldFromScene(hit),
        miss: focalWorldFromScene(miss),
        degenerate: focalWorldFromScene(degenerate),
        empty: focalWorldFromScene(empty),
        defaults: [WORLD_STAGE_WIDTH / 2, WORLD_STAGE_HEIGHT / 2],
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["hit"] == [612, 388]
    assert result["miss"] == [420, 290]
    assert result["degenerate"] == [123, 456]
    assert result["empty"] == result["defaults"]


def test_spotlight_progress_eases_across_late_window() -> None:
    # Phase 5 — vignette overlay tightens 0 → 1 across t=0.48-0.84. Before that
    # window the rect stays absent; after it the held-final-frame contract
    # keeps the spotlight at full strength so reduced-motion users still see
    # the locked-on framing.
    source = """
      import { spotlightProgress } from './web/viz-model.js';
      console.log(JSON.stringify({
        early: spotlightProgress(0.30),
        start: spotlightProgress(0.48),
        end: spotlightProgress(0.84),
        held: spotlightProgress(1.0),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["early"] == 0
    assert result["start"] == 0
    assert abs(result["end"] - 1.0) < 1e-9
    assert abs(result["held"] - 1.0) < 1e-9


def test_halo_aura_progress_eases_across_hit_window() -> None:
    # Phase 5 — single-focal halo radius + opacity ride this curve across
    # t=0.62-0.86. Multi-grab halo opacity uses this curve too (the radius
    # uses multiGrabMergeProgress instead).
    source = """
      import { haloAuraProgress } from './web/viz-model.js';
      console.log(JSON.stringify({
        early: haloAuraProgress(0.50),
        end: haloAuraProgress(0.86),
        held: haloAuraProgress(1.0),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["early"] == 0
    assert abs(result["end"] - 1.0) < 1e-9
    assert abs(result["held"] - 1.0) < 1e-9


def test_multi_grab_merge_progress_eases_across_slide_window() -> None:
    # Phase 5 — drives both the focal-position lerp toward binary positions
    # AND the multi-grab halo's shrink. Single source of truth for "how far
    # along is the fusion."
    source = """
      import { multiGrabMergeProgress } from './web/viz-model.js';
      console.log(JSON.stringify({
        early: multiGrabMergeProgress(0.50),
        end: multiGrabMergeProgress(0.88),
        held: multiGrabMergeProgress(1.0),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["early"] == 0
    assert abs(result["end"] - 1.0) < 1e-9
    assert abs(result["held"] - 1.0) < 1e-9


def test_multi_grab_flash_opacity_peaks_then_decays() -> None:
    # Phase 5 — brief white burst punctuating the fusion. Rises easeOutCubic
    # across t=0.82-0.86 to alpha 0.32, falls easeOutCubic across t=0.86-0.92
    # back to 0. Before 0.82 and after 0.92 the flash is dark.
    source = """
      import { multiGrabFlashOpacity } from './web/viz-model.js';
      console.log(JSON.stringify({
        before: multiGrabFlashOpacity(0.50),
        peak: multiGrabFlashOpacity(0.86),
        after: multiGrabFlashOpacity(1.0),
        midRise: multiGrabFlashOpacity(0.84),
        midFall: multiGrabFlashOpacity(0.89),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["before"] == 0
    assert abs(result["peak"] - 0.32) < 1e-9
    assert result["after"] == 0
    assert 0 < result["midRise"] < 0.32
    assert 0 < result["midFall"] < 0.32


def test_focal_scale_factor_branches_on_outcome() -> None:
    # Phase 5 — single-hit focal blooms 1.0 → 1.50 across t=0.66-0.90 so a
    # small-cost focal still reads against larger-cost siblings. Multi-grab
    # stays at 1.0 (proximity + ray overlap carries the binary visual). Miss
    # holds at 0.95 so the no-lock outcome dims subtly.
    source = """
      import { focalScaleFactor } from './web/viz-model.js';
      console.log(JSON.stringify({
        singleEarly: focalScaleFactor(0.50, 'single-hit'),
        singleMid: focalScaleFactor(0.82, 'single-hit'),
        singleEnd: focalScaleFactor(0.90, 'single-hit'),
        singleHeld: focalScaleFactor(1.0, 'single-hit'),
        multiZero: focalScaleFactor(0.0, 'multi-grab'),
        multiMid: focalScaleFactor(0.5, 'multi-grab'),
        multiHeld: focalScaleFactor(1.0, 'multi-grab'),
        missEarly: focalScaleFactor(0.0, 'miss'),
        missMid: focalScaleFactor(0.5, 'miss'),
        missHeld: focalScaleFactor(1.0, 'miss'),
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["singleEarly"] == 1.0
    assert abs(result["singleMid"] - 1.28) < 1e-9
    assert abs(result["singleEnd"] - 1.50) < 1e-9
    assert abs(result["singleHeld"] - 1.50) < 1e-9
    assert result["multiZero"] == 1.0
    assert result["multiMid"] == 1.0
    assert result["multiHeld"] == 1.0
    assert result["missEarly"] == 0.95
    assert result["missMid"] == 0.95
    assert result["missHeld"] == 0.95


def test_halo_binary_offset_and_jump_radius_world_exported() -> None:
    # Phase 5 — constants the camera renderer relies on must be a single
    # source of truth in viz-model.js. The binary offset places the two
    # focals at (±5, ∓1) relative to the merge center; JUMP_RADIUS_WORLD
    # sets the initial halo radius for single-focal hits (0.85 of it).
    source = """
      import { HALO_BINARY_OFFSET, JUMP_RADIUS_WORLD } from './web/viz-model.js';
      console.log(JSON.stringify({
        offset: HALO_BINARY_OFFSET,
        jumpRadius: JUMP_RADIUS_WORLD,
      }));
    """
    result = json.loads(_node_eval(source))
    assert result["offset"] == {"x": 5, "y": 1}
    assert result["jumpRadius"] == 70


# Unknown-constellation stand-in resolution. The curator's source records some
# misses without knowing which constellation would have been hit; the cinematic
# falls back to an unrevealed constellation as a placeholder shape so the camera
# has something to focus on. The renderer reads `isUnknownConstellationStandIn`
# to apply a dashed silhouette treatment.
_STAND_IN_DATA_FIXTURE = """
  const data = {
    clusterAnchors: new Map([
      ['Toolkits', { vertexSource: 'jumps', byJump: new Map(), byPerkId: new Map(), jumpByPerkId: new Map() }],
      ['Knowledge', { vertexSource: 'jumps', byJump: new Map(), byPerkId: new Map(), jumpByPerkId: new Map() }],
      ['Vehicles', { vertexSource: 'jumps', byJump: new Map(), byPerkId: new Map(), jumpByPerkId: new Map() }],
      ['Time', { vertexSource: 'jumps', byJump: new Map(), byPerkId: new Map(), jumpByPerkId: new Map() }],
    ]),
    jumpWireframeByKey: new Map(),
    wireframes: { jump_constellations: [] },
    story: {
      chapters: [
        { chapter_num: '1', constellation_progress: [
          { name: 'Toolkits', count: 1 },
          { name: 'Knowledge', count: 0 },
          { name: 'Vehicles', count: 0 },
          { name: 'Time', count: 0 },
        ] },
        { chapter_num: '2', constellation_progress: [
          { name: 'Toolkits', count: 2 },
          { name: 'Knowledge', count: 1 },
          { name: 'Vehicles', count: 0 },
          { name: 'Time', count: 0 },
        ] },
      ],
    },
  };
"""


def test_focus_scene_picks_stand_in_for_unknown_constellation_miss() -> None:
    source = f"""
      import {{ focusScene }} from './web/viz-model.js';
      {_STAND_IN_DATA_FIXTURE}
      const roll = {{
        roll_number: 13,
        outcome: 'miss',
        constellation: null,
        chapter_num: '2',
        purchased_perks: [],
        free_perks: [],
      }};
      const scene = focusScene(roll, data);
      console.log(JSON.stringify({{
        isStandIn: scene.isUnknownConstellationStandIn,
        resolved: scene.resolvedConstellation,
        branch: scene.branch,
      }}));
    """
    result = json.loads(_node_eval(source))
    assert result["isStandIn"] is True
    assert result["branch"] == "miss"
    # Through ch 2, Toolkits and Knowledge are revealed; stand-in must be one
    # of the still-unrevealed clusters.
    assert result["resolved"] in {"Vehicles", "Time"}


def test_focus_scene_deterministic_stand_in_pick() -> None:
    source = f"""
      import {{ focusScene }} from './web/viz-model.js';
      {_STAND_IN_DATA_FIXTURE}
      const roll = {{
        roll_number: 13,
        outcome: 'miss',
        constellation: null,
        chapter_num: '2',
        purchased_perks: [],
        free_perks: [],
      }};
      const a = focusScene(roll, data);
      const b = focusScene(roll, data);
      console.log(JSON.stringify({{ a: a.resolvedConstellation, b: b.resolvedConstellation }}));
    """
    result = json.loads(_node_eval(source))
    assert result["a"] == result["b"]


def test_focus_scene_does_not_set_stand_in_flag_for_known_constellation_misses() -> None:
    source = f"""
      import {{ focusScene }} from './web/viz-model.js';
      {_STAND_IN_DATA_FIXTURE}
      const roll = {{
        roll_number: 7,
        outcome: 'miss',
        constellation: 'Toolkits',
        chapter_num: '2',
        purchased_perks: [],
        free_perks: [],
      }};
      const scene = focusScene(roll, data);
      console.log(JSON.stringify({{
        isStandIn: scene.isUnknownConstellationStandIn,
        resolved: scene.resolvedConstellation,
      }}));
    """
    result = json.loads(_node_eval(source))
    assert result["isStandIn"] is False
    assert result["resolved"] == "Toolkits"

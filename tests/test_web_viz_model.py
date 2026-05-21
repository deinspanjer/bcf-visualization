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


def test_on_roll_behavior_windows_classify_normal_pause_and_bullet_time() -> None:
    source = """
      import { onRollPlaybackState } from './web/viz-model.js';
      const roll = { word_position: 10000 };
      console.log(JSON.stringify({
        normal: onRollPlaybackState(roll, 10010, 'normal'),
        pause: onRollPlaybackState(roll, 10650, 'pause'),
        pauseOutside: onRollPlaybackState(roll, 10750, 'pause'),
        bullet: onRollPlaybackState(roll, 11400, 'bullet-time'),
        bulletOutside: onRollPlaybackState(roll, 11600, 'bullet-time'),
      }));
    """
    assert json.loads(_node_eval(source)) == {
        "normal": {"behavior": "normal", "onRoll": False, "speedMultiplier": 1},
        "pause": {"behavior": "pause", "onRoll": True, "speedMultiplier": 0},
        "pauseOutside": {"behavior": "pause", "onRoll": False, "speedMultiplier": 1},
        "bullet": {"behavior": "bullet-time", "onRoll": True, "speedMultiplier": 0.04},
        "bulletOutside": {"behavior": "bullet-time", "onRoll": False, "speedMultiplier": 1},
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


# The old cascade + cp-fraction coordinate helpers are gone. Predicted and
# curated positions are now canonical fields on every bundle roll
# (`epub_word_offset_predicted` / `epub_word_offset_curated`), computed in
# the pipeline via scripts/cp_epub_map.py. UI position selection is
# trivial; the invariants live in:
#   tests/test_cp_epub_map.py
#   tests/test_chapter_alignment_fingerprints.py
#   tests/test_roll_position_invariants.py

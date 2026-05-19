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


def test_coordinate_helpers_map_predicted_cp_ticks_to_raw_word_scrubber_positions() -> None:
    source = """
      import { buildCoordinateModel, rollWordPosition } from './web/viz-model.js';
      const facts = { chapters: [
        { chapter_num: '1', total_word_count: 1000, cumulative_words_through_chapter: 1000,
          cp_earning_word_count: 500, cumulative_cp_earning_words: 500 },
        { chapter_num: '2', total_word_count: 2000, cumulative_words_through_chapter: 3000,
          cp_earning_word_count: 1000, cumulative_cp_earning_words: 1500 },
      ]};
      const model = buildCoordinateModel(facts);
      const mapped = rollWordPosition(model, { predicted_word_position_epub: 1000 }, facts.chapters[1]);
      const displayOverride = rollWordPosition(model, { display_word_position_epub: 2500, predicted_word_position_epub: 1000 }, facts.chapters[1]);
      console.log(JSON.stringify({ mapped, displayOverride }));
    """
    assert json.loads(_node_eval(source)) == {
        "mapped": 2000,
        "displayOverride": 2500,
    }

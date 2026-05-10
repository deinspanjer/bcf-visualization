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
      const idx = buildConstellationProgressIndex(facts);
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

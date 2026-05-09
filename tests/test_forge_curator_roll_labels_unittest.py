from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from scripts.forge_curator.app import ForgeCuratorApp
from scripts.forge_curator.persistence import CurationPersistence


class ForgeCuratorRollLabelTests(unittest.IsolatedAsyncioTestCase):
    async def test_chapter_1_roll_attempt_index_excludes_trigger(self) -> None:
        app = ForgeCuratorApp(start_chapter="1")
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            chapter_state = app.state.chapter
            self.assertIsNotNone(chapter_state)

            rolls = app._unified_rolls(chapter_state)
            self.assertGreaterEqual(len(rolls), 1)
            self.assertEqual(rolls[0]["roll_number"], 1)
            self.assertEqual(rolls[0]["index"], 1)

            rendered = app._format_roll_stat_line(rolls[0], "▸")
            self.assertIn("#1 (global #1) miss", rendered)
            self.assertNotIn("#2 (global #1)", rendered)

    async def test_chapter_1_roll_list_includes_deferred_display_roll(self) -> None:
        app = ForgeCuratorApp(start_chapter="1")
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            chapter_state = app.state.chapter
            self.assertIsNotNone(chapter_state)

            rolls = app._unified_rolls(chapter_state)

            self.assertEqual([r["index"] for r in rolls], [1, 2])
            self.assertEqual([r["roll_number"] for r in rolls], [1, 2])
            self.assertEqual(rolls[1]["outcome"], "hit")
            self.assertEqual(rolls[1]["mechanical_chapter_num"], "1")
            self.assertEqual(rolls[1]["display_chapter_num"], "1")
            self.assertEqual(rolls[1]["purchased_perks"][0]["name"], "Fashion")

    async def test_chapter_1_roll_jumps_reach_deferred_display_roll(self) -> None:
        app = ForgeCuratorApp(start_chapter="1")
        async with app.run_test(size=(180, 50)) as pilot:
            await pilot.pause()
            chapter_state = app.state.chapter
            self.assertIsNotNone(chapter_state)
            rolls = app._unified_rolls(chapter_state)

            first_raw = app._raw_word_for_cp_offset(int(rolls[0]["word_position"]))
            second_raw = app._raw_word_for_cp_offset(int(rolls[1]["word_position"]))

            app._jump_to_word(first_raw)
            app._jump_roll_predicted(forward=True)
            await pilot.pause()
            self.assertEqual(chapter_state.cursor_word_index, second_raw)

            app._jump_to_word(first_raw)
            app._jump_roll_quoted(forward=True)
            await pilot.pause()
            self.assertEqual(chapter_state.cursor_word_index, second_raw)


class ForgeCuratorRollDeferralTests(unittest.TestCase):
    def test_mark_roll_deferred_preserves_existing_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapter_roll_overrides.json"
            persistence = CurationPersistence(
                chapter_roll_overrides_path=path,
                journal_dir_path=Path(tmp) / ".journals",
            )
            persistence.update_roll_at_index("1", 2, outcome="hit")

            persistence.mark_roll_deferred_to_chapter("1", 2, "2")

            rolls = (
                persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"]
            )
            self.assertEqual(rolls[1]["outcome"], "hit")
            self.assertEqual(rolls[1]["mention_chapter_num"], "2")
            self.assertIsNone(rolls[1]["mention_word_position"])
            self.assertEqual(rolls[1]["display_position_policy"], "mechanical")

    def test_mark_roll_deferred_creates_unset_outcome_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapter_roll_overrides.json"
            persistence = CurationPersistence(
                chapter_roll_overrides_path=path,
                journal_dir_path=Path(tmp) / ".journals",
            )

            persistence.mark_roll_deferred_to_chapter("1", 2, "2")

            rolls = (
                persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"]
            )
            self.assertEqual(len(rolls), 2)
            self.assertIsNone(rolls[1]["outcome"])
            self.assertEqual(rolls[1]["mention_chapter_num"], "2")
            self.assertIsNone(rolls[1]["mention_word_position"])
            self.assertEqual(rolls[1]["display_position_policy"], "mechanical")


if __name__ == "__main__":
    unittest.main()

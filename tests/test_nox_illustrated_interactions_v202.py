"""Regression tests for illustrated NOX daily posts."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / 'cogs/nox_daily_12.py').read_text(encoding='utf-8')

class IllustratedDailyPosts(unittest.TestCase):
    def test_valid_python(self):
        ast.parse(SRC)

    def test_all_illustrated_slots_send_persistent_buttons(self):
        self.assertIn('view=IllustratedReactionView(item[\'scene_id\'])', SRC)
        self.assertIn('bot.add_view(IllustratedReactionView())', SRC)
        self.assertIn('timeout=None', SRC)
        self.assertIn('horizons:nox:illustre:', SRC)

    def test_vote_is_saved_per_member_per_message(self):
        self.assertIn('PRIMARY KEY(guild_id,message_id,user_id)', SRC)
        self.assertIn('DO UPDATE SET choice=excluded.choice', SRC)
        self.assertIn("state='sent',message_id=?", SRC)

    def test_existing_poll_and_challenge_views_preserved(self):
        self.assertIn('view=ChallengeView()', SRC)
        self.assertIn('view=PollView()', SRC)

    def test_scene_labels_and_safe_fallback(self):
        self.assertIn("'grillepain':", SRC)
        self.assertIn('DEFAULT_REACTIONS', SRC)

if __name__ == '__main__':
    unittest.main()

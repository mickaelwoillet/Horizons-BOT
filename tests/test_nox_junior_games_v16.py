"""Regression tests for three repeatable NOX Junior games."""
import tempfile
import unittest
from pathlib import Path
from cogs import nox_junior_engine as engine


class NewGamesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = engine.connect(Path(self.tmp.name) / 'junior.sqlite3')
        self.pet = engine.adopt(self.con, 123, 456, 'Nova', 'violet', True, now=100)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_three_games_complete_and_reward_cap(self):
        import json
        from datetime import datetime, timezone
        base = datetime(2026, 11, 11, 12, tzinfo=timezone.utc).timestamp()
        for index, game in enumerate(('cache_cache', 'cuisine', 'danse') * 3):
            now = base + index * 20
            session = engine.game_start(self.con, self.pet, 456, 123, game, now=now)
            self.assertTrue(session['question'])
            self.assertGreaterEqual(len(session['choices']), 3)
            self.assertEqual(session['game'], game)
            record = self.con.execute('SELECT answer FROM junior_game_sessions WHERE token=?', (session['token'],)).fetchone()
            correct = record['answer']
            success, bond = engine.game_finish(self.con, session['token'], self.pet, 456, 123, correct, now=now+1)
            self.assertTrue(success)
            self.assertEqual(bond, 4)
            with self.assertRaises(engine.JuniorError):
                engine.game_finish(self.con, session['token'], self.pet, 456, 123, correct, now=now+2)
        reward = self.con.execute('SELECT SUM(amount) FROM junior_star_rewards WHERE pet_id=?',(self.pet,)).fetchone()[0]
        self.assertEqual(reward, 10)
        count = self.con.execute('SELECT COUNT(*) FROM junior_game_sessions WHERE completed_at IS NOT NULL').fetchone()[0]
        self.assertEqual(count, 9)


if __name__ == '__main__':
    unittest.main()

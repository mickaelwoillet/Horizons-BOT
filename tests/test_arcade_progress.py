"""Tests isolés du stockage de statistiques et de succès Arcade."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cogs import arcade_progress


class ArcadeProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.temp.close()
        self.path = self.temp.name

        initial = sqlite3.connect(self.path)
        initial.executescript("""
            CREATE TABLE celestial_game_history (
                session_id TEXT PRIMARY KEY, guild_id INTEGER NOT NULL, game_key TEXT NOT NULL,
                mode TEXT NOT NULL, players_json TEXT NOT NULL, winners_json TEXT NOT NULL,
                status TEXT NOT NULL, scores_json TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT NOT NULL
            );
            CREATE TABLE celestial_game_player_stats (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, game_key TEXT NOT NULL,
                played INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0, draws INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id,game_key)
            );
            CREATE TABLE celestial_game_achievements (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, achievement_key TEXT NOT NULL,
                unlocked_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id,achievement_key)
            );
            CREATE TABLE celestial_weekly_missions (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, week_key TEXT NOT NULL,
                mission_key TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT, claimed_at TEXT, xp_awarded INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(guild_id,user_id,week_key,mission_key)
            );
            CREATE TABLE celestial_game_rewards (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reward_date TEXT NOT NULL,
                game_key TEXT NOT NULL, xp_awarded INTEGER NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(guild_id,user_id,reward_date,game_key)
            );
            CREATE TABLE celestial_game_xp (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id)
            );
        """)
        initial.close()

        @contextmanager
        def temporary_db():
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            try:
                yield connection
                connection.commit()
            finally:
                connection.close()

        self.db_patch = patch.object(arcade_progress, "db", temporary_db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def tearDown(self):
        Path(self.path).unlink(missing_ok=True)

    def test_result_updates_stats_history_and_achievements(self):
        unlocked = arcade_progress.record_game_result(
            123, "morpion", "duel", [10, 20], winners=[10], scores={10: 1, 20: 0}
        )
        self.assertIn("premiere_partie", unlocked)
        self.assertIn("premiere_victoire", unlocked)
        stats = arcade_progress.get_game_stats(123, 10)
        self.assertEqual(stats[0]["played"], 1)
        self.assertEqual(stats[0]["wins"], 1)
        history = arcade_progress.get_game_history(123, 10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["winners"], [10])
        badges = arcade_progress.get_achievements(123, 10)
        self.assertGreaterEqual(len(badges), 2)


    def test_progress_view_renders_all_sections(self):
        view = arcade_progress.ProgressView(123, 10, 75, 2, "Observateur céleste")
        with patch.object(arcade_progress, "get_game_stats", return_value=[{"game_key": "morpion", "played": 3, "wins": 2, "losses": 1, "draws": 0}]), \
             patch.object(arcade_progress, "get_achievements", return_value=[{"key": "premiere_victoire", "title": "🏆 Première victoire", "description": "Première victoire", "unlocked_at": "2026-11-08T12:00:00+01:00"}]), \
             patch.object(arcade_progress, "get_game_history", return_value=[{"game_key": "morpion", "mode": "duel", "players": [10, 20], "winners": [10], "status": "completed", "scores": {}, "ended_at": "2026-11-08T12:00:00+01:00"}]), \
             patch.object(arcade_progress, "get_weekly_missions", return_value=[{"key": "parties_3", "title": "Faire trois parties", "description": "Terminer trois parties", "target": 3, "reward": 15, "progress": 1, "completed_at": None, "claimed_at": None, "xp_awarded": 0, "week_key": "2026-W45"}]), \
             patch.object(arcade_progress, "get_pending_weekly_missions", return_value=[]):
            self.assertIn("passeport", view.overview_embed().title)
            self.assertIn("Morpion", view.stats_embed().description)
            self.assertIn("Victoire", view.history_embed().description)
            self.assertIn("Première victoire", view.achievements_embed().description)
            self.assertIn("Faire trois parties", view.missions_embed().description)
        self.assertLessEqual(len(view.to_components()), 5)


    def test_noncompetitive_legacy_game_counts_as_completed(self):
        unlocked = arcade_progress.record_game_result(123, "de", "solo", [10], status="completed", scores={10: 4})
        self.assertIn("premiere_partie", unlocked)
        stats = arcade_progress.get_game_stats(123, 10)
        self.assertEqual(stats[0]["played"], 1)
        self.assertEqual(stats[0]["wins"], 0)
        self.assertEqual(stats[0]["losses"], 0)
        history = arcade_progress.get_game_history(123, 10)
        self.assertEqual(history[0]["game_key"], "de")

    def test_weekly_missions_progress_and_claim_respects_daily_cap(self):
        arcade_progress.record_game_result(123, "morpion", "duel", [10, 20], winners=[10])
        arcade_progress.record_game_result(123, "memory", "solo", [10], winners=[10])
        arcade_progress.record_game_result(123, "quizjeu", "collectif", [10], winners=[10])
        missions = arcade_progress.get_weekly_missions(123, 10)
        by_key = {item["key"]: item for item in missions}
        self.assertTrue(by_key["parties_3"]["completed_at"])
        self.assertTrue(by_key["variety_3"]["completed_at"])
        self.assertTrue(by_key["duel_1"]["completed_at"])
        self.assertTrue(by_key["collective_1"]["completed_at"])
        total, count = arcade_progress.claim_all_weekly_missions(123, 10)
        self.assertEqual(total, 60)
        self.assertGreaterEqual(count, 3)
        xp = arcade_progress.get_game_stats(123, 10)
        self.assertEqual(len(xp), 3)
        self.assertEqual(arcade_progress.claim_all_weekly_missions(123, 10), (0, 0))
        self.assertTrue(arcade_progress.get_pending_weekly_missions(123, 10))

    def test_loss_and_draw_are_counted_separately(self):
        arcade_progress.record_game_result(123, "memory", "solo", [10], status="loss")
        arcade_progress.record_game_result(123, "puissance4", "duel", [10, 20], status="draw")
        stats = {item["game_key"]: item for item in arcade_progress.get_game_stats(123, 10)}
        self.assertEqual(stats["memory"]["losses"], 1)
        self.assertEqual(stats["puissance4"]["draws"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

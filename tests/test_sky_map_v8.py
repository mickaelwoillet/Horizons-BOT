"""Tests isolés de la Carte du Ciel, sans connexion Discord."""
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from cogs import sky_map

class SkyMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.sqlite3"
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE sky_unlocks(guild_id INTEGER,user_id INTEGER,star_key TEXT,unlocked_at TEXT,PRIMARY KEY(guild_id,user_id,star_key))")
        @contextmanager
        def isolated_db():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
        self.patch = patch.object(sky_map, "db", isolated_db)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_quiz_star_is_idempotent(self):
        self.assertTrue(sky_map.grant(1, 10, "origins.quiz"))
        self.assertFalse(sky_map.grant(1, 10, "origins.quiz"))
        self.assertEqual(sky_map.progress(1, 10)["origins"], 1)
        self.assertEqual(sky_map.progress(1, 11)["origins"], 0)

    def test_completion_unlocks_after_all_other_stars(self):
        for key in sky_map.ORIGINS:
            if key != "origins.complete":
                sky_map.grant(1, 10, key)
        result = sky_map.progress(1, 10)
        self.assertEqual(result["origins"], 12)
        self.assertTrue(result["themes_open"])

    def test_unknown_and_derived_stars_cannot_be_granted(self):
        for key in ("origins.complete", "unknown"):
            with self.assertRaises(ValueError):
                sky_map.grant(1, 10, key)

if __name__ == "__main__":
    unittest.main()

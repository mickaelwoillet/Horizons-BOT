"""Tests statiques V9.0 ne nécessitant pas de connexion Discord."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'cogs' / 'chaos_cosmique.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE)

class CosmicTests(unittest.TestCase):
    def test_extension_registered(self):
        self.assertIn('"cogs.chaos_cosmique"', (ROOT / 'bot.py').read_text(encoding='utf-8'))

    def test_persistent_buttons(self):
        self.assertIn('timeout=None', SOURCE)
        for n in range(3):
            self.assertIn(f'cosmic:v90:choice:{n}', SOURCE)

    def test_disabled_by_default(self):
        self.assertIn('paused INTEGER NOT NULL DEFAULT 1', SOURCE)
        self.assertIn('channel_id INTEGER NOT NULL DEFAULT 0', SOURCE)

    def test_event_deduplication(self):
        self.assertIn('UNIQUE(guild_id, day)', SOURCE)
        self.assertIn('BEGIN IMMEDIATE', SOURCE)

    def test_no_legacy_database_mutation(self):
        self.assertIn("chaos_cosmique.sqlite3", SOURCE)
        self.assertNotIn('DROP TABLE', SOURCE)

if __name__ == '__main__':
    unittest.main()

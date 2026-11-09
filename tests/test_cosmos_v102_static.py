import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'cogs' / 'chaos_cosmique.py'
TEXT = SOURCE.read_text(encoding='utf-8')

class TestCosmosV102(unittest.TestCase):
    def test_compiles(self):
        ast.parse(TEXT)
    def test_buttons_persistent(self):
        for action in ('season','rumor','expedition'):
            self.assertIn('cosmic:v102:nox:'+action,TEXT)
        self.assertIn('row=4',TEXT)
    def test_no_destructive_migrations(self):
        self.assertIn('CREATE TABLE IF NOT EXISTS cosmic_expeditions',TEXT)
        self.assertIn('CREATE TABLE IF NOT EXISTS cosmic_expedition_actions',TEXT)
    def test_idempotent_actions(self):
        self.assertIn('INSERT OR IGNORE INTO cosmic_expedition_actions',TEXT)
        self.assertIn('PRIMARY KEY(guild_id,user_id,day,season)',TEXT)
    def test_solo_progress(self):
        self.assertIn('contributions=MIN(12,contributions+1)',TEXT)
        self.assertIn('Même en solo',TEXT)

if __name__ == '__main__': unittest.main()

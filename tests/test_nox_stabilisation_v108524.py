"""Static regression checks requiring no Discord token or discord.py installation."""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestNoxStabilisation(unittest.TestCase):
    def test_python_syntax(self):
        files = list(ROOT.rglob('*.py'))
        self.assertGreater(len(files), 120)
        for path in files:
            with self.subTest(file=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding='utf-8-sig'))

    def test_json_syntax(self):
        files = list(ROOT.rglob('*.json'))
        self.assertGreater(len(files), 40)
        for path in files:
            with self.subTest(file=path.relative_to(ROOT)):
                json.loads(path.read_text(encoding='utf-8-sig'))

    def test_nox_extensions_present_and_ordered(self):
        source = (ROOT / 'bot.py').read_text(encoding='utf-8')
        for name in ('nox_daily_polls', 'nox_daily_challenges', 'nox_daily_12', 'nox_interactions'):
            self.assertIn(f'"cogs.{name}"', source)
            self.assertTrue((ROOT / 'cogs' / f'{name}.py').is_file())
        self.assertLess(source.index('"cogs.nox_daily_polls"'), source.index('"cogs.nox_daily_12"'))
        self.assertLess(source.index('"cogs.nox_daily_challenges"'), source.index('"cogs.nox_daily_12"'))

    def test_persistent_views(self):
        for name, marker in (('nox_daily_polls', 'PollView'), ('nox_daily_challenges', 'ChallengeView')):
            source = (ROOT / 'cogs' / f'{name}.py').read_text(encoding='utf-8')
            self.assertIn(f'bot.add_view({marker}())', source)
            self.assertIn('timeout=None', source)
            self.assertIn('message_id=?', source)

    def test_no_duplicate_slots_and_bounded_publications(self):
        tree = ast.parse((ROOT / 'cogs' / 'nox_daily_12.py').read_text(encoding='utf-8'))
        source = (ROOT / 'cogs' / 'nox_daily_12.py').read_text(encoding='utf-8')
        self.assertIn('if minute >= 23 * 60:', source)
        self.assertIn('release_unsent_reservation()', source)
        self.assertIn('attachment.is_file()', source)
        self.assertIn('except Exception:', source)
        self.assertIn('INSERT OR IGNORE INTO nox_daily_posts', source)
        self.assertIn('ILLUSTRATED_SLOTS = frozenset((0, 2, 4, 6, 8, 10))', source)
        self.assertIsNotNone(tree)

    def test_no_public_reply_content_saved(self):
        source = (ROOT / 'cogs' / 'nox_interactions.py').read_text(encoding='utf-8')
        self.assertNotIn('message.content', source)
        self.assertIn('message.reference.message_id', source)
        self.assertIn('total >= 3', source)

if __name__ == '__main__':
    unittest.main()

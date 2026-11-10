"""Offline source-contract checks; Discord integration requires a staging server."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class NoxDiagnosticsContract(unittest.TestCase):
    def test_syntax_all_python(self):
        for path in ROOT.rglob('*.py'):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

    def test_json_all(self):
        for path in ROOT.rglob('*.json'):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding='utf-8'))

    def test_extension_registered(self):
        self.assertIn('"cogs.nox_diagnostics"', (ROOT / 'bot.py').read_text(encoding='utf-8'))

    def test_admin_and_ephemeral(self):
        source = (ROOT / 'cogs/nox_diagnostics.py').read_text(encoding='utf-8')
        self.assertIn('has_permissions(administrator=True)', source)
        self.assertIn('defer(ephemeral=True', source)
        self.assertNotIn('send_as_nox(', source)
        self.assertNotIn('create_webhook(', source)

    def test_persistent_views_and_webhook_wait(self):
        for name in ('nox_daily_polls.py', 'nox_daily_challenges.py'):
            source = (ROOT / 'cogs' / name).read_text(encoding='utf-8')
            self.assertIn('timeout=None', source)
            self.assertIn('bot.add_view(', source)
        self.assertIn('wait=True', (ROOT / 'cogs/nox_identity.py').read_text(encoding='utf-8'))

    def test_no_automatic_pending_replay(self):
        source = (ROOT / 'cogs/nox_daily_12.py').read_text(encoding='utf-8')
        self.assertIn('INSERT OR IGNORE INTO nox_daily_posts', source)
        self.assertIn('release_unsent_reservation()', source)
        self.assertIn("state='pending'", source)

if __name__ == '__main__':
    unittest.main()

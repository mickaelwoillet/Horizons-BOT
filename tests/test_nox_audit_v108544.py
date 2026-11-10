import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class NoxAuditV108544(unittest.TestCase):
    def test_noxtv_ambiguous_send_keeps_reservation(self):
        source = (ROOT / 'cogs/nox_tv.py').read_text(encoding='utf-8')
        section = source.split('msg=await channel.send(', 1)[1].split('with connect() as db:', 1)[0]
        self.assertIn('réservation automatique est conservée', section)
        self.assertNotIn('DELETE FROM noxtv_posts', section)

    def test_persistent_interactions_registered(self):
        for filename, view in [('nox_tv.py','NoxTVChoices'),('nox_refuge.py','RefugeView'),
                               ('nox_daily_polls.py','PollView'),('nox_daily_challenges.py','ChallengeView')]:
            with self.subTest(filename=filename):
                code = (ROOT / 'cogs' / filename).read_text(encoding='utf-8')
                self.assertIn('add_view('+view+'()', code)
                self.assertIn('timeout=None', code)

    def test_all_python_parses(self):
        for file in ROOT.rglob('*.py'):
            with self.subTest(path=str(file.relative_to(ROOT))):
                ast.parse(file.read_text(encoding='utf-8'), filename=str(file))

if __name__ == '__main__':
    unittest.main()

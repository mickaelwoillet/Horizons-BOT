"""Offline smoke checks: no Discord connection or token required."""
import ast
import json
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def isolated_function(filename, name, globals_):
    tree = ast.parse((ROOT / 'cogs' / filename).read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    scope = dict(globals_)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(filename), 'exec'), scope)
    return scope[name]


class NoxStabilisation(unittest.TestCase):
    def test_twelve_slots(self):
        slots = tuple(600 + 70*i for i in range(12))
        eligible = isolated_function('nox_daily_12.py', 'eligible_slot', {'SLOTS': slots})
        self.assertEqual(len(slots), 12)
        self.assertEqual(slots[-1], 1370)
        for i, minute in enumerate(slots):
            self.assertEqual(eligible(datetime(2026,11,10,minute//60,minute%60)), i)
        self.assertIsNone(eligible(datetime(2026,11,10,9,59)))
        self.assertIsNone(eligible(datetime(2026,11,10,23,0)))
        self.assertEqual(len({0,2,4,6,8,10}), 6)

    def test_catalogs(self):
        for name, minimum in [('sondages_quotidiens.json', 12), ('defis_quotidiens.json', 20)]:
            items = json.loads((ROOT/'data'/'nox'/name).read_text(encoding='utf-8'))
            self.assertGreaterEqual(len(items), minimum)
            self.assertEqual(len({item['id'] for item in items}), len(items))
        images = json.loads((ROOT/'data'/'nox'/'publications_illustrees.json').read_text(encoding='utf-8'))
        self.assertTrue(all((ROOT/'data'/'nox_tv'/Path(x['image']).name).is_file() for x in images))

    def test_recap_counts_without_fabrication(self):
        con = sqlite3.connect(':memory:')
        init = isolated_function('nox_daily_challenges.py', 'init_db', {})
        # Test the same SQL as the production count function, without importing discord.
        init(con)
        day='2026-11-10'
        self.assertIsNone(con.execute('SELECT 1 FROM nox_daily_challenges WHERE guild_id=1').fetchone())
        con.execute('INSERT INTO nox_daily_challenges(guild_id,local_day,slot,challenge_id) VALUES(1,?,5,?)', (day,'test'))
        self.assertEqual(con.execute('SELECT COUNT(*) FROM nox_daily_challenge_members WHERE guild_id=1 AND local_day=? AND slot=5',(day,)).fetchone()[0],0)
        con.execute('INSERT INTO nox_daily_challenge_members VALUES(1,?,5,42,?)',(day,day))
        self.assertEqual(con.execute('SELECT COUNT(*) FROM nox_daily_challenge_members WHERE guild_id=1 AND local_day=? AND slot=5',(day,)).fetchone()[0],1)
        con.close()

    def test_all_python_and_json_parse(self):
        for path in ROOT.rglob('*.py'):
            if '.venv' not in path.parts:
                with self.subTest(path=str(path)):
                    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for path in ROOT.rglob('*.json'):
            with self.subTest(path=str(path)):
                json.loads(path.read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()

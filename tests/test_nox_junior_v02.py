import importlib.util
import tempfile
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'cogs' / 'nox_junior_engine.py'
spec = importlib.util.spec_from_file_location('junior_engine_v02', PATH)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

class JuniorV02Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'junior.sqlite3'
        self.con = engine.connect(self.db)
        self.pet = engine.adopt(self.con, 123, 456, 'Nova', 'violet', True, now=1000000)

    def tearDown(self):
        self.con.close()
        self.temp.cleanup()

    def test_lazy_decay_floor_and_no_repeat(self):
        a = engine.snapshot(self.con, self.pet, 456, 123, now=1000000 + 86400 * 100)
        self.assertGreaterEqual(a['hydratation'], 30)
        b = engine.snapshot(self.con, self.pet, 456, 123, now=1000000 + 86400 * 100)
        self.assertEqual(a['hydratation'], b['hydratation'])

    def test_mood(self):
        a = engine.snapshot(self.con, self.pet, 456, 123, now=1000000)
        self.assertEqual(engine.mood(a)[0], 'heureux')

    def test_six_care_actions(self):
        for i, action in enumerate(engine.CARE):
            self.assertEqual(engine.care(self.con, self.pet, 456, action, now=1000000 + i * 1801, guild_id=123), 0)
        self.assertEqual(len(engine.journal(self.con, self.pet, 456, 123)), 7)

    def test_cooldown_persistent(self):
        engine.care(self.con, self.pet, 456, 'nourrir', now=1000000, guild_id=123)
        self.con.close()
        self.con = engine.connect(self.db)
        self.assertEqual(engine.care(self.con, self.pet, 456, 'laver', now=1000021, guild_id=123), 0)
        self.assertGreater(engine.care(self.con, self.pet, 456, 'laver', now=1000022, guild_id=123), 0)

    def test_owner_isolation(self):
        with self.assertRaises(engine.JuniorError):
            engine.snapshot(self.con, self.pet, 999, 123)
        with self.assertRaises(engine.JuniorError):
            engine.journal(self.con, self.pet, 999, 123)
        with self.assertRaises(engine.JuniorError):
            engine.care(self.con, self.pet, 999, 'jouer', guild_id=123)

    def test_existing_v01_migration(self):
        self.con.execute('ALTER TABLE junior_pets RENAME TO junior_pets_v2')
        self.con.execute('CREATE TABLE junior_pets AS SELECT id,guild_id,owner_id,slot,name,color,created_at,renamed,bond,activities,satiete,hydratation,bonheur,energie,hygiene,last_care,updated_at FROM junior_pets_v2')
        self.con.execute('DROP TABLE junior_pets_v2')
        self.con.close()
        self.con = engine.connect(self.db)
        self.assertIn('last_decay', [r['name'] for r in self.con.execute('PRAGMA table_info(junior_pets)')])

if __name__ == '__main__':
    unittest.main()

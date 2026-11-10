import tempfile
import unittest
from pathlib import Path
from nox_refuge_engine import connect, snapshot, perform, contributions, set_panel, refuge_link

class RefugeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / 'refuge.sqlite3')
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def test_decay_and_guild_isolation(self):
        self.assertEqual(snapshot(self.db, 1, 100)['stats']['faim'], 80)
        self.assertEqual(snapshot(self.db, 1, 3700)['stats']['faim'], 77.5)
        self.assertEqual(snapshot(self.db, 2, 3700)['stats']['faim'], 80)
    def test_action_and_cooldown(self):
        self.assertTrue(perform(self.db, 1, 10, 'nourrir', 100)['ok'])
        self.assertFalse(perform(self.db, 1, 10, 'nourrir', 101)['ok'])
        self.assertTrue(perform(self.db, 1, 11, 'nourrir', 101)['ok'])
        self.assertTrue(perform(self.db, 1, 10, 'nourrir', 1900)['ok'])
        self.assertEqual(dict(contributions(self.db,1,10))['nourrir'], 2)
    def test_panel_link(self):
        set_panel(self.db,1,123,456,100)
        self.assertEqual(snapshot(self.db,1,100)['message_id'],456)
        self.assertEqual(refuge_link(123,1),'https://discord.com/channels/1/123')
    def test_clamp_and_no_death(self):
        self.assertEqual(snapshot(self.db,1,1000000)['stats']['soif'],80)
        self.assertEqual(snapshot(self.db,1,2000000)['stats']['soif'],0)
        self.assertTrue(perform(self.db,1,2,'boire',2000000)['ok'])
        self.assertGreater(snapshot(self.db,1,2000000)['stats']['soif'],0)

if __name__=='__main__': unittest.main()

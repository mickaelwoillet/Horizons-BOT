import sqlite3
import unittest
from cogs.nox_memory import memory_summary, milestone_reply

class NoxMemoryTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.con.row_factory = sqlite3.Row
        self.con.execute('CREATE TABLE nox_refuge_contributions(guild_id INTEGER,user_id INTEGER,action TEXT,count INTEGER)')
        self.con.execute('CREATE TABLE nox_adventures(id INTEGER,guild_id INTEGER,closed_at REAL)')
        self.con.execute('CREATE TABLE nox_adventure_votes(adventure_id INTEGER,user_id INTEGER,choice INTEGER)')
        self.con.executemany('INSERT INTO nox_refuge_contributions VALUES(?,?,?,?)', [(1, 10, 'calin', 5), (1, 11, 'boire', 2), (2, 10, 'calin', 30)])
        self.con.executemany('INSERT INTO nox_adventures VALUES(?,?,?)', [(1, 1, 100), (2, 1, None), (3, 2, 100)])
        self.con.executemany('INSERT INTO nox_adventure_votes VALUES(?,?,?)', [(1,10,0),(2,10,1),(3,10,0)])
    def tearDown(self): self.con.close()
    def test_collective_scoped(self):
        s=memory_summary(self.con,1)
        self.assertEqual((s['total_care'],s['adventures']), (7,1))
    def test_personal_scoped(self):
        s=memory_summary(self.con,1,10)
        self.assertEqual((s['total_care'],s['votes']), (5,2))
    def test_milestones(self):
        self.assertIsNotNone(milestone_reply('calin',5))
        self.assertIsNone(milestone_reply('calin',6))
    def test_missing_adventures_table(self):
        self.con.execute('DROP TABLE nox_adventures')
        self.assertEqual(memory_summary(self.con,1)['adventures'],0)

if __name__=='__main__':unittest.main()

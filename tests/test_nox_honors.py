import sqlite3
import unittest
from cogs.nox_honors import honorary_titles


class HonorsTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.execute('CREATE TABLE nox_refuge_contributions (guild_id INTEGER, user_id INTEGER, action TEXT, count INTEGER)')
        self.db.executemany('INSERT INTO nox_refuge_contributions VALUES (?,?,?,?)',
                            [(1, 10, 'calin', 25), (1, 10, 'nourrir', 5),
                             (1, 11, 'calin', 1), (2, 10, 'nourrir', 200)])

    def tearDown(self):
        self.db.close()

    def test_earned(self):
        result = honorary_titles(self.db, 1, 10)
        ids = {x['id'] for x in result['earned']}
        self.assertTrue({'premier_calin', 'calin_intergalactique', 'gardien_biscuits', 'ami_refuge'} <= ids)
        self.assertNotIn('pilier_refuge', ids)

    def test_isolation(self):
        result = honorary_titles(self.db, 1, 11)
        self.assertEqual(result['total'], 1)
        self.assertEqual([x['id'] for x in result['earned']], ['premier_calin'])
        self.assertEqual(honorary_titles(self.db, 2, 10)['total'], 200)

    def test_newcomer(self):
        result = honorary_titles(self.db, 1, 999)
        self.assertEqual(result['earned'], [])
        self.assertEqual(result['total'], 0)


if __name__ == '__main__':
    unittest.main()

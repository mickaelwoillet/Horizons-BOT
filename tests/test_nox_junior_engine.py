import sqlite3
import tempfile
import unittest
from pathlib import Path
from cogs import nox_junior_engine as e

class JuniorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=e.connect(Path(self.tmp.name)/'junior.sqlite3')
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def test_adoption_limit_and_grant(self):
        first=e.adopt(self.db,1,2,'Nova','violet',True,now=100)
        with self.assertRaises(e.JuniorError): e.adopt(self.db,1,2,'Lumi','bleu',True,now=101)
        e.grant_second(self.db,1,2,999,now=102)
        second=e.adopt(self.db,1,2,'Lumi','bleu',True,now=103)
        self.assertNotEqual(first,second)
        with self.assertRaises(e.JuniorError): e.adopt(self.db,1,2,'Nox','rose',True,now=104)
    def test_eligibility_and_name(self):
        with self.assertRaises(e.JuniorError): e.adopt(self.db,1,2,'Nova','violet',False)
        for name in ('a','@everyone','<@123>'):
            with self.assertRaises(e.JuniorError): e.validate_name(name)
    def test_rename_once(self):
        pet=e.adopt(self.db,1,2,'Nova','violet',True,now=100)
        e.rename(self.db,pet,2,'Luna')
        with self.assertRaises(e.JuniorError): e.rename(self.db,pet,2,'Nova')
    def test_care_cooldown(self):
        pet=e.adopt(self.db,1,2,'Nova','violet',True,now=100)
        self.assertEqual(e.care(self.db,pet,2,'nourrir',now=200),0)
        self.assertEqual(e.care(self.db,pet,2,'boire',now=221),0)
        self.assertGreater(e.care(self.db,pet,2,'boire',now=222),0)
        self.assertEqual(self.db.execute('SELECT bond FROM junior_pets WHERE id=?',(pet,)).fetchone()[0],4)
    def test_stage(self):
        pet=e.adopt(self.db,1,2,'Nova','violet',True,now=100)
        row=self.db.execute('SELECT * FROM junior_pets WHERE id=?',(pet,)).fetchone()
        self.assertEqual(e.stage(row,now=100+40*86400)[0],'oeuf')
        self.db.execute('UPDATE junior_pets SET bond=300,activities=70 WHERE id=?',(pet,))
        row=self.db.execute('SELECT * FROM junior_pets WHERE id=?',(pet,)).fetchone()
        self.assertEqual(e.stage(row,now=100+40*86400)[0],'adulte')
    def test_refuge_count(self):
        self.db.execute('CREATE TABLE nox_refuge_contributions(guild_id INTEGER,user_id INTEGER,action TEXT,count INTEGER)')
        self.db.execute('INSERT INTO nox_refuge_contributions VALUES (1,2,\'calin\',7),(1,2,\'jouer\',3),(1,3,\'calin\',20)')
        self.assertEqual(e.care_count(self.db,1,2),10)

if __name__=='__main__': unittest.main()

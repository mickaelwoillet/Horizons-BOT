import unittest
import tempfile
from pathlib import Path
from cogs import nox_junior_engine as e

class V04(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.con=e.connect(Path(self.tmp.name)/'junior.sqlite3')
        self.pet=e.adopt(self.con,1,2,'Nova','violet',True,now=1000)
    def tearDown(self):
        self.con.close();self.tmp.cleanup()
    def test_all_regions_and_persistence(self):
        for index,region in enumerate(e.REGIONS):
            now=2000+index*2000
            session=e.exploration_start(self.con,self.pet,2,1,region,now=now)
            self.assertEqual(len(session['choices']),3)
            part=e.exploration_step(self.con,session['token'],self.pet,2,1,'0',now=now+1)
            self.assertFalse(part['finished'])
            end=e.exploration_step(self.con,session['token'],self.pet,2,1,'1',now=now+2)
            self.assertTrue(end['finished'])
            self.assertTrue(end['new'])
            with self.assertRaises(e.JuniorError):
                e.exploration_step(self.con,session['token'],self.pet,2,1,'1',now=now+3)
        self.assertEqual(len(e.discoveries(self.con,self.pet,2,1)),5)
    def test_owner_and_cooldown(self):
        session=e.exploration_start(self.con,self.pet,2,1,'foret',now=2000)
        with self.assertRaises(e.JuniorError):
            e.exploration_step(self.con,session['token'],self.pet,3,1,'0',now=2001)
        with self.assertRaises(e.JuniorError):
            e.exploration_start(self.con,self.pet,2,1,'iles',now=2002)
        e.exploration_step(self.con,session['token'],self.pet,2,1,'0',now=2003)
        e.exploration_step(self.con,session['token'],self.pet,2,1,'0',now=2004)
        with self.assertRaises(e.JuniorError):
            e.exploration_start(self.con,self.pet,2,1,'iles',now=2005)
    def test_new_games(self):
        for index,game in enumerate(('cristaux','enigmes','constellations')):
            now=3000+index*1000
            session=e.game_start(self.con,self.pet,2,1,game,now=now)
            self.assertEqual(len(session['choices']),4)
            result=e.game_finish(self.con,session['token'],self.pet,2,1,'0',now=now+1)
            self.assertIsInstance(result[0],bool)
            with self.assertRaises(e.JuniorError):
                e.game_finish(self.con,session['token'],self.pet,2,1,'0',now=now+2)
    def test_expiry(self):
        session=e.exploration_start(self.con,self.pet,2,1,'foret',now=2000)
        with self.assertRaises(e.JuniorError):
            e.exploration_step(self.con,session['token'],self.pet,2,1,'0',now=2601)

if __name__=='__main__':unittest.main()

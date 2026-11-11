import tempfile, unittest
from pathlib import Path
from cogs import nox_junior_engine as e

class MultiRoundV09(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'game.db'
        self.db=e.connect(self.path)
        self.a=e.adopt(self.db,1,10,'Nova','violet',True,now=100)
        self.b=e.adopt(self.db,1,20,'Lumi','bleu',True,now=100)
        self.id=e.encounter_invite(self.db,self.a,10,1,self.b,'duo',now=1000)
        e.encounter_respond(self.db,self.id,20,1,True,now=1001)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def test_waiting_and_resume_after_restart(self):
        e.encounter_play(self.db,self.id,self.a,10,1,0,now=1002)
        self.assertTrue(e.encounter_progress(self.db,self.id,self.a,10,1,now=1003)['waiting'])
        with self.assertRaises(e.JuniorError):e.encounter_play(self.db,self.id,self.a,10,1,2,now=1003)
        self.db.close();self.db=e.connect(self.path)
        e.encounter_play(self.db,self.id,self.b,20,1,1,now=1004)
        self.assertEqual(e.encounter_progress(self.db,self.id,self.a,10,1,now=1005)['round'],2)
    def test_no_reward_until_third_round_and_once(self):
        for i in range(3):
            e.encounter_play(self.db,self.id,self.a,10,1,0,now=1002+i*2)
            result=e.encounter_play(self.db,self.id,self.b,20,1,0,now=1003+i*2)
            self.assertEqual(result['completed'],i==2)
        self.assertEqual(result['reward'],6)
        self.assertEqual(self.db.execute('SELECT activities FROM junior_pets WHERE id=?',(self.a,)).fetchone()[0],1)
        with self.assertRaises(e.JuniorError):e.encounter_play(self.db,self.id,self.a,10,1,0,now=1010)
    def test_access_and_expiry(self):
        with self.assertRaises(e.JuniorError):e.encounter_progress(self.db,self.id,self.a,20,1,now=1002)
        with self.assertRaises(e.JuniorError):e.encounter_play(self.db,self.id,self.a,20,1,0,now=1002)
        with self.assertRaises(e.JuniorError):e.encounter_play(self.db,self.id,self.a,10,1,0,now=90000)
    def test_three_games_have_three_chapters(self):
        for game,chapters in e.SOCIAL_ROUNDS.items():
            self.assertEqual(len(chapters),3)
            self.assertTrue(all(len(options)==3 for _,options in chapters))
if __name__=='__main__':unittest.main()

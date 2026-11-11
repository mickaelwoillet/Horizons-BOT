import tempfile, unittest
from pathlib import Path
from cogs import nox_junior_engine as e

class SocialV07(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.con=e.connect(Path(self.temp.name)/'junior.sqlite3')
        self.a=e.adopt(self.con,1,10,'Nova','violet',True,now=100)
        self.b=e.adopt(self.con,1,20,'Lumi','bleu',True,now=100)
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def test_consent_and_rewards_once(self):
        for game in e.SOCIAL_GAMES:
            t=1000+list(e.SOCIAL_GAMES).index(game)*4000
            invite=e.encounter_invite(self.con,self.a,10,1,self.b,game,now=t)
            self.assertEqual(e.encounter_respond(self.con,invite,20,1,True,now=t+1),'active')
            for round_number in range(1,4):
                self.assertEqual(e.encounter_progress(self.con,invite,self.a,10,1,now=t+round_number)['round'],round_number)
                self.assertFalse(e.encounter_play(self.con,invite,self.a,10,1,0,now=t+round_number*2)['completed'])
                result=e.encounter_play(self.con,invite,self.b,20,1,1,now=t+round_number*2+1)
                self.assertEqual(result['completed'],round_number==3)
            self.assertEqual(result['reward'],12)
            with self.assertRaises(e.JuniorError):e.encounter_play(self.con,invite,self.b,20,1,1,now=t+9)
        self.assertEqual(self.con.execute('SELECT bond FROM junior_pets WHERE id=?',(self.a,)).fetchone()[0],36)
        self.assertEqual(self.con.execute('SELECT bond FROM junior_pets WHERE id=?',(self.b,)).fetchone()[0],36)
    def test_refusal_and_permissions(self):
        i=e.encounter_invite(self.con,self.a,10,1,self.b,'duo',now=1000)
        with self.assertRaises(e.JuniorError):e.encounter_respond(self.con,i,10,1,True,now=1001)
        self.assertEqual(e.encounter_respond(self.con,i,20,1,False,now=1001),'declined')
        with self.assertRaises(e.JuniorError):e.encounter_play(self.con,i,self.a,10,1,0,now=1002)
        with self.assertRaises(e.JuniorError):e.encounter_invite(self.con,self.a,10,1,self.a,'duo',now=1003)
        with self.assertRaises(e.JuniorError):e.encounter_invite(self.con,self.a,20,1,self.b,'duo',now=1004)
    def test_expiration(self):
        i=e.encounter_invite(self.con,self.a,10,1,self.b,'festival',now=1000)
        self.assertEqual(e.encounter_respond(self.con,i,20,1,True,now=1000+86401),'expired')
        with self.assertRaises(e.JuniorError):e.encounter_play(self.con,i,self.a,10,1,0,now=1000+86402)
    def test_pending_and_inbox(self):
        i=e.encounter_invite(self.con,self.a,10,1,self.b,'tresor',now=1000)
        self.assertEqual(len(e.encounter_inbox(self.con,20,1,now=1001)),1)
        self.assertEqual(len(e.encounter_inbox(self.con,30,1,now=1001)),0)
        self.assertEqual(len(e.encounter_inbox(self.con,20,1,now=1000+86401)),0)
        self.assertEqual(e.encounter_respond(self.con,i,20,1,True,now=1002),'active')
        with self.assertRaises(e.JuniorError):e.encounter_respond(self.con,i,20,1,True,now=1003)
if __name__=='__main__': unittest.main()

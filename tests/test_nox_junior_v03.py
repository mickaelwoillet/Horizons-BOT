import importlib.util, tempfile, unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'cogs/nox_junior_engine.py'
spec=importlib.util.spec_from_file_location('nox_junior_engine_v03',p)
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
class GamesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.con=e.connect(Path(self.tmp.name)/'db.sqlite');self.pet=e.adopt(self.con,10,20,'Nova','violet',True)
 def tearDown(self):self.con.close();self.tmp.cleanup()
 def test_reward_once(self):
  session=e.game_start(self.con,self.pet,20,10,'choix');self.assertEqual(e.game_finish(self.con,session['token'],self.pet,20,10,'1')[1],4)
  with self.assertRaises(e.JuniorError):e.game_finish(self.con,session['token'],self.pet,20,10,'1')
  self.assertEqual(e.pets(self.con,10,20)[0]['bond'],4)
 def test_owner_security(self):
  session=e.game_start(self.con,self.pet,20,10,'etoiles')
  with self.assertRaises(e.JuniorError):e.game_finish(self.con,session['token'],self.pet,99,10,'1')
 def test_cooldown(self):
  session=e.game_start(self.con,self.pet,20,10,'choix');e.game_finish(self.con,session['token'],self.pet,20,10,'1')
  with self.assertRaises(e.JuniorError):e.game_start(self.con,self.pet,20,10,'choix')
 def test_persistence(self):
  session=e.game_start(self.con,self.pet,20,10,'choix');self.con.close();self.con=e.connect(Path(self.tmp.name)/'db.sqlite');e.game_finish(self.con,session['token'],self.pet,20,10,'1');self.assertEqual(e.affinities(self.con,self.pet,20,10)['protection'],3)
 def test_expired(self):
  session=e.game_start(self.con,self.pet,20,10,'choix',now=1000)
  with self.assertRaises(e.JuniorError):e.game_finish(self.con,session['token'],self.pet,20,10,'1',now=1301)
 def test_game_types(self):
  for game in e.GAMES:
   con=e.connect(Path(self.tmp.name)/(game+'.sqlite'));pet=e.adopt(con,10,20,'Nova','bleu',True);self.assertEqual(len(e.game_start(con,pet,20,10,game)['choices'])>=3,True);con.close()
if __name__=='__main__':unittest.main()

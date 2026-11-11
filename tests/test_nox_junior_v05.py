import unittest
import tempfile
from pathlib import Path
from cogs import nox_junior_engine as e

class V05(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'junior.sqlite3'
        self.con=e.connect(self.path)
        self.pet=e.adopt(self.con,1,2,'Nova','violet',True,now=1000)
    def tearDown(self):
        self.con.close();self.temp.cleanup()
    def test_notes_crud_persistence_and_permissions(self):
        note=e.note_create(self.con,self.pet,2,1,'Première sortie','Nova a découvert une étoile.',now=2000)
        self.assertEqual(e.note_get(self.con,note,self.pet,2,1)['body'],'Nova a découvert une étoile.')
        self.con.close();self.con=e.connect(self.path)
        self.assertEqual(len(e.note_list(self.con,self.pet,2,1)),1)
        with self.assertRaises(e.JuniorError): e.note_get(self.con,note,self.pet,3,1)
        with self.assertRaises(e.JuniorError): e.note_edit(self.con,note,self.pet,3,1,'Piratage','texte')
        with self.assertRaises(e.JuniorError): e.note_delete(self.con,note,self.pet,2,99)
        e.note_edit(self.con,note,self.pet,2,1,'Nouveau titre','Une belle journée',now=2001)
        self.assertEqual(e.note_get(self.con,note,self.pet,2,1)['title'],'Nouveau titre')
        e.note_delete(self.con,note,self.pet,2,1)
        self.assertFalse(e.note_list(self.con,self.pet,2,1))
    def test_note_validation_and_independent_companions(self):
        with self.assertRaises(e.JuniorError): e.note_create(self.con,self.pet,2,1,'','Texte')
        with self.assertRaises(e.JuniorError): e.note_create(self.con,self.pet,2,1,'Titre','x'*1001)
        with self.assertRaises(e.JuniorError): e.note_create(self.con,self.pet,3,1,'Titre','Texte')
        e.grant_second(self.con,1,2,99)
        other=e.adopt(self.con,1,2,'Luna','rose',True,now=1001)
        e.note_create(self.con,self.pet,2,1,'Titre','Premier compagnon')
        self.assertEqual(len(e.note_list(self.con,other,2,1)),0)
    def test_adventure_games_rewards_and_replay(self):
        for i,game in enumerate(('parcours','cometes','sauvetage')):
            now=2000+i*1200
            session=e.game_start(self.con,self.pet,2,1,game,now=now)
            self.assertEqual(len(session['choices']),3)
            result=e.game_finish(self.con,session['token'],self.pet,2,1,'0',now=now+1)
            self.assertIsInstance(result[0],bool)
            with self.assertRaises(e.JuniorError):
                e.game_finish(self.con,session['token'],self.pet,2,1,'0',now=now+2)
        self.assertEqual(self.con.execute('SELECT COUNT(*) FROM junior_game_sessions WHERE completed_at IS NOT NULL').fetchone()[0],3)

if __name__=='__main__':unittest.main()

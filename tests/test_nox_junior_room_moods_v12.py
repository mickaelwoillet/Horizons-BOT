import tempfile
import unittest
from pathlib import Path
from cogs import nox_junior_engine as e

class RoomMoodTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = e.connect(Path(self.tmp.name) / 'test.sqlite3')
        self.pid = e.adopt(self.con, 1, 2, 'Nova', 'bleu', True, now=100)
        self.con.execute('UPDATE junior_pets SET bond=300,activities=70 WHERE id=?', (self.pid,))
        self.con.execute('INSERT INTO junior_rooms(pet_id,theme,decoration) VALUES(?,?,?)', (self.pid,e.ROOM_THEMES[0],'none'))
    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()
    def equip(self, code):
        self.con.execute('INSERT OR IGNORE INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,1)',(self.pid,code))
        self.con.execute('INSERT OR REPLACE INTO junior_room_slots(pet_id,slot,code) VALUES(?,?,?)',(self.pid,e.DECOR_SLOTS[code],code))
    def test_equipped_only_and_caps(self):
        self.assertEqual(e.room_effects(self.con,self.pid)['energie'],0)
        self.equip('oreiller_douillet')
        self.assertAlmostEqual(e.room_effects(self.con,self.pid)['energie'],0)  # Oreiller gratuit : aucun bonus
        self.equip('coussin_etoile')
        self.assertAlmostEqual(e.room_effects(self.con,self.pid)['energie'],-.15)
        self.equip('mobile_etoiles')
        self.equip('lampe_lunaire')
        self.assertAlmostEqual(e.room_effects(self.con,self.pid)['energie'],-.29)
        self.equip('tapis_constellations')
        self.assertAlmostEqual(e.room_effects(self.con,self.pid)['energie'],-.33)
        self.assertEqual(e.room_ambience(self.con,self.pid)[0], 'apaisé')
    def test_snapshot_decay_with_equipment(self):
        self.con.execute('UPDATE junior_pets SET energie=80,bonheur=80,last_decay=? WHERE id=?',(100+8*86400,self.pid))
        self.equip('coussin_etoile')
        row=e.snapshot(self.con,self.pid,2,1,now=100+8*86400+3600)
        self.assertAlmostEqual(row['energie'],79.53,places=2)
        self.assertAlmostEqual(row['bonheur'],79.55,places=2)
    def test_growth_40_days(self):
        row=self.con.execute('SELECT * FROM junior_pets WHERE id=?',(self.pid,)).fetchone()
        self.assertEqual(e.stage(row,100+7*86400)[0],'bebe')
        self.assertEqual(e.stage(row,100+18*86400)[0],'bebe')
        self.assertEqual(e.stage(row,100+19*86400)[0],'adolescent')
        self.assertEqual(e.stage(row,100+39*86400)[0],'adolescent')
        self.assertEqual(e.stage(row,100+40*86400)[0],'adulte')

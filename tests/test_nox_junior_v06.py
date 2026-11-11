import unittest,tempfile
from pathlib import Path
from cogs import nox_junior_engine as e

class V06(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.con=e.connect(Path(self.tmp.name)/'test.db')
        self.a=e.adopt(self.con,1,2,'Nova','violet',True,now=100)
        self.b=e.adopt(self.con,1,3,'Lumi','bleu',True,now=100)
    def tearDown(self):
        self.con.close();self.tmp.cleanup()
    def test_inventory_room_and_crafting(self):
        e.add_item(self.con,self.a,2,1,'cristal_lunaire',4)
        e.add_item(self.con,self.a,2,1,'poussiere_etoiles',12)
        e.craft(self.con,self.a,2,1,'veilleuse')
        self.assertIsNone(e.room(self.con,self.a,2,1)['theme'])  # Chambre choisie après éclosion
        self.con.execute('UPDATE junior_pets SET bond=300,activities=70 WHERE id=?',(self.a,))
        e.add_item(self.con,self.a,2,1,'coussin_etoile')
        e.decorate(self.con,self.a,2,1,theme=e.ROOM_THEMES[0],decoration='coussin_etoile')
        self.assertEqual(e.room(self.con,self.a,2,1)['slots']['couchage'],'coussin_etoile')
        self.assertEqual(e.room(self.con,self.b,3,1)['decoration'],'none')
        with self.assertRaises(e.JuniorError):e.craft(self.con,self.a,2,1,'veilleuse')
        with self.assertRaises(e.JuniorError):e.decorate(self.con,self.b,3,1,theme=e.ROOM_THEMES[0],decoration='coussin_etoile')
    def test_gift_accept_decline_and_no_replay(self):
        e.add_item(self.con,self.a,2,1,'cristal_lunaire',5)
        g=e.gift_offer(self.con,self.a,2,1,self.b,'cristal_lunaire',3,now=1000)
        self.assertEqual(e.gift_resolve(self.con,g,3,1,True,now=1001),'accepted')
        with self.assertRaises(e.JuniorError):e.gift_resolve(self.con,g,3,1,True,now=1002)
        self.assertEqual({x['code']:x['quantity'] for x in e.inventory(self.con,self.b,3,1)}['cristal_lunaire'],3)
        g=e.gift_offer(self.con,self.a,2,1,self.b,'cristal_lunaire',1,now=1100)
        self.assertEqual(e.gift_resolve(self.con,g,3,1,False,now=1101),'declined')
    def test_restrictions_and_expiry(self):
        e.add_item(self.con,self.a,2,1,'souvenir_eclosion')
        with self.assertRaises(e.JuniorError):e.gift_offer(self.con,self.a,2,1,self.b,'souvenir_eclosion',now=1000)
        e.add_item(self.con,self.a,2,1,'cristal_lunaire',2)
        with self.assertRaises(e.JuniorError):e.gift_offer(self.con,self.a,3,1,self.b,'cristal_lunaire',now=1000)
        g=e.gift_offer(self.con,self.a,2,1,self.b,'cristal_lunaire',2,now=1000)
        with self.assertRaises(e.JuniorError):e.gift_offer(self.con,self.a,2,1,self.b,'cristal_lunaire',1,now=1001)
        self.assertEqual(e.gift_resolve(self.con,g,3,1,True,now=1000+86401),'expired')

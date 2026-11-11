import tempfile
import unittest
from pathlib import Path
from cogs import nox_junior_engine as e

class EconomyV15Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=e.connect(Path(self.tmp.name)/'test.db')
        self.pet=e.adopt(self.db,1,2,'Nova','violet',True,now=100)
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def test_daily_care_cap_and_rewards(self):
        # 40 successful care actions on one UTC date, spaced 30 seconds apart.
        for i in range(40):
            self.assertEqual(e.care(self.db,self.pet,2,'nourrir',now=1000+i*30),0)
            balance=self.db.execute('SELECT balance FROM junior_star_wallet WHERE pet_id=?',(self.pet,)).fetchone()[0]
            self.assertEqual(balance, 0 if i<9 else 1 if i<19 else 2)
        with self.assertRaisesRegex(e.JuniorError,'40 soins'):
            e.care(self.db,self.pet,2,'nourrir',now=1000+40*30)
        self.assertEqual(e.care(self.db,self.pet,2,'nourrir',now=1000+86400),0)
        self.assertEqual(self.db.execute('SELECT balance FROM junior_star_wallet WHERE pet_id=?',(self.pet,)).fetchone()[0],2)
        for i in range(1,10):
            self.assertEqual(e.care(self.db,self.pet,2,'nourrir',now=1000+86400+i*30),0)
        self.assertEqual(self.db.execute('SELECT balance FROM junior_star_wallet WHERE pet_id=?',(self.pet,)).fetchone()[0],3)
    def test_shop_pricing_and_birth_pillow(self):
        self.assertEqual(sum(v[1] for v in e.SHOP.values()),1225)
        self.assertEqual(e.SHOP['coussin_etoile'][1],40)
        self.assertNotIn('oreiller_douillet',e.SHOP)
        self.assertEqual(e.DECOR_EFFECTS['oreiller_douillet'],{})

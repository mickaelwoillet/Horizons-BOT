import ast, json, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class NoxFinalImages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenes = json.loads((ROOT/'data/nox/publications_illustrees.json').read_text(encoding='utf8'))
        cls.source = (ROOT/'cogs/nox_daily_12.py').read_text(encoding='utf8')
    def test_unique_ids(self):
        self.assertEqual(len({s['id'] for s in self.scenes}), len(self.scenes))
    def test_image_files(self):
        for s in self.scenes:
            with self.subTest(s=s['id']):
                self.assertEqual(Path(s['image']).name,s['image'])
                self.assertTrue((ROOT/'data/nox_tv'/s['image']).is_file())
    def test_all_six_themes(self):
        themes={s['theme'] for s in self.scenes}
        self.assertEqual(themes, {'humour','aventure','surprise','insolite','cosmos','tendresse'})
    def test_texts(self):
        self.assertTrue(all(isinstance(s['texte'],str) and 0<len(s['texte'].strip())<=1800 for s in self.scenes))
    def test_no_cross_theme_fallback(self):
        self.assertNotIn('or image_scenes)',self.source)
        self.assertIn('random.choice(unseen or themed) if themed else None',self.source)
        ast.parse(self.source)
if __name__=='__main__': unittest.main()

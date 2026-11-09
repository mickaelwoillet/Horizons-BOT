import ast, json, pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class NoxTVAssets(unittest.TestCase):
 def test_catalogue_assets_exist_and_unique(self):
  items=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text(encoding='utf-8'))
  self.assertEqual(len(items),len({i['id'] for i in items}))
  for item in items:
   self.assertTrue((ROOT/'data/nox_tv'/item['file']).is_file(),item['id'])
   self.assertIn(item['kind'],('nox','canard','grille_pain','paradoxe','gloups','exploration','chronique'))
 def test_new_scenes_have_unique_verdicts(self):
  tree=ast.parse((ROOT/'cogs/nox_tv.py').read_text(encoding='utf-8'))
  vals={}
  for node in ast.walk(tree):
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCENE_VERDICTS' for t in node.targets): vals=ast.literal_eval(node.value)
  for scene in ('paradoxe_horloges_folles','gloups_fiole_rebelle'):
   self.assertEqual(len(vals[scene]),3)
   self.assertEqual(len(set(vals[scene])),3)
 def test_catalogue_json_is_utf8(self):
  raw=(ROOT/'data/nox_tv/catalogue.json').read_bytes()
  self.assertIn('LES HORLOGES'.encode(),raw)
if __name__=='__main__': unittest.main()

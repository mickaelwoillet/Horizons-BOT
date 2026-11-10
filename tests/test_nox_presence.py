import unittest
import ast
from pathlib import Path
source = Path(__file__).resolve().parents[1] / "cogs" / "nox_presence.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "eligible")
namespace = {"QUIET_HOURS": (22, 9), "MIN_INTERVAL": 6*3600, "SAME_NEED_INTERVAL": 18*3600}
exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), namespace)
eligible = namespace["eligible"]

class TestPresence(unittest.TestCase):
    def setUp(self):
        self.state={'message_id': 42,'channel_id': 12,'needs':['faim']}
        self.config={'enabled':1,'last_post':0,'last_need':None,'last_need_at':0}
    def test_eligible(self):
        self.assertEqual(eligible(self.state,self.config,100000,12),'faim')
    def test_quiet(self):
        self.assertIsNone(eligible(self.state,self.config,100000,23))
    def test_cooldown(self):
        self.config['last_post']=99999
        self.assertIsNone(eligible(self.state,self.config,100000,12))
    def test_requires_refuge(self):
        self.state['message_id']=None
        self.assertIsNone(eligible(self.state,self.config,100000,12))

if __name__=='__main__': unittest.main()

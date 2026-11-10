import ast
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=(ROOT/'cogs'/'chaos_cosmique.py').read_text(encoding='utf-8')
class CompleteCosmosTests(unittest.TestCase):
    def test_python_valid(self): ast.parse(SRC)
    def test_16_distinct_anomalies(self):
        tree=ast.parse(SRC)
        keys=[]
        for n in ast.walk(tree):
            if isinstance(n,ast.Tuple) and n.elts and isinstance(n.elts[0],ast.Constant) and isinstance(n.elts[0].value,str):
                if len(n.elts)==5 and isinstance(n.elts[3],ast.Tuple):keys.append(n.elts[0].value)
        self.assertGreaterEqual(len(set(keys)),16)
    def test_commands(self):
        for command in ['installer','soigner','carte','visiter','journal','actualiser','diagnostic']:
            self.assertIn(f"name='{command}'",SRC)
    def test_migrated_buttons(self):
        for label in ['Mon sac', 'Chroniques', 'Nourrir']:
            self.assertIn(label, SRC)
        for command in ['nox', 'sac', 'chroniques']:
            self.assertNotIn(f"@cosmos.command(name='{command}'", SRC)
    def test_separate_database(self):self.assertIn("chaos_cosmique.sqlite3",SRC)
    def test_disabled_by_default(self):self.assertIn('paused INTEGER NOT NULL DEFAULT 1',SRC)
    def test_guild_permissions(self):self.assertIn('has_permissions(manage_guild=True)',SRC)
    def test_limited_daily_actions(self):self.assertIn('PRIMARY KEY(guild_id,user_id,action,day)',SRC)
    def test_no_new_external_dependencies(self):self.assertNotIn('openai',SRC.lower())
if __name__=='__main__':unittest.main()

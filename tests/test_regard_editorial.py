"""Tests autonomes : n'ouvrent aucune connexion Discord ni requête web."""
import ast
from contextlib import contextmanager
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

ROOT=Path(__file__).resolve().parents[1]

def helper():
    spec=importlib.util.spec_from_file_location('regard_editorial_test',ROOT/'cogs'/'regard_editorial.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class EditorialChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=helper()

    def test_source_allowlist(self):
        r=self.r
        self.assertTrue(r.trusted_source('https://www.lemonde.fr/'))
        self.assertTrue(r.trusted_source('https://actu.fr'))
        self.assertFalse(r.trusted_source('https://lemonde.fr.example.com'))
        self.assertFalse(r.trusted_source('http://lemonde.fr'))
        self.assertFalse(r.trusted_source('https://evil.example.com'))

    def test_relevant_and_duplicates(self):
        r=self.r
        self.assertTrue(r.relevant_headline('Discrimination raciste : une décision de justice', 'Discriminations'))
        self.assertFalse(r.relevant_headline('Concert au stade de France', 'LGBTQIA+'))
        self.assertFalse(r.relevant_headline('Un festival de musique solidaire', 'Solidarité'))
        self.assertTrue(r.relevant_headline('Une association lutte contre l’homophobie et pour la solidarité', 'Solidarité'))
        self.assertTrue(r.same_story('Justice : une décision de tribunal à Lyon dans une affaire de racisme',
                                     'Justice : une décision de tribunal à Lyon dans une affaire de racisme'))
        self.assertFalse(r.same_story('Condamnation pour racisme à Nice cette semaine',
                                      'Une affaire de transphobie et discrimination à Paris'))

    def test_dates(self):
        r=self.r
        stamp=r.news_date('Mon, 09 Nov 2026 16:00:00 GMT')
        self.assertEqual(stamp.date(),date(2026,11,9))
        self.assertTrue(r.within_recent_days(stamp,date(2026,11,9)))
        self.assertFalse(r.within_recent_days(stamp,date(2026,11,15)))
        self.assertFalse(r.within_recent_days(None,date(2026,11,9)))

    def test_additive_sqlite_schema(self):
        file=ROOT/'cogs'/'regard_du_jour.py'
        tree=ast.parse(file.read_text(encoding='utf-8'))
        fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='connect')
        with tempfile.TemporaryDirectory() as tmp:
            dbpath=Path(tmp)/'regard.sqlite3'
            ctx={'sqlite3':sqlite3,'DB':dbpath,'contextmanager':contextmanager}
            exec(compile(ast.Module(body=[fn],type_ignores=[]),str(file),'exec'),ctx)
            with ctx['connect']() as db:
                self.assertIn('source',{x['name'] for x in db.execute('PRAGMA table_info(regard_items)')})
                tables={x['name'] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({'regard_proposals','regard_weekly_digests','regard_weekly_songs','regard_xp_audit','regard_thread_parts'} <= tables)
                db.execute("INSERT INTO regard_state(key,value) VALUES('test','persist')")
            with ctx['connect']() as db:
                self.assertEqual(db.execute("SELECT value FROM regard_state WHERE key='test'").fetchone()[0],'persist')

if __name__=='__main__':unittest.main()

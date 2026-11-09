"""Vérifie hors ligne l'unicité du forum et la reprise après redémarrage."""
import ast
from contextlib import contextmanager
import asyncio
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'cogs'/'regard_du_jour.py'

class FakeThread:
    def __init__(self,id,name):self.id=id;self.name=name;self.owner_id=42;self.mention=f'<#{id}>';self.archived=False;self.messages=[]
    async def send(self,content,**kw):
        result=types.SimpleNamespace(id=1000+len(self.messages));self.messages.append((content,kw));return result
    async def edit(self,**kw):self.archived=kw.get('archived',self.archived)
    async def fetch_message(self,id):
        class Starter:
            content='Début du Regard du Jour'
            async def edit(self,content,**kw):self.content=content
        return Starter()

class FakeForum:
    def __init__(self):self.threads=[];self.creations=0
    async def create_thread(self,**kw):
        self.creations+=1
        thread=FakeThread(100+self.creations,kw['name'])
        self.threads.append(thread)
        return types.SimpleNamespace(thread=thread)
    def get_thread(self,id):return next((x for x in self.threads if x.id==id),None)
    async def archived_threads(self,limit=80):
        for x in self.threads:
            if x.archived:yield x

class PublishTest(unittest.TestCase):
    def test_daily_post_and_resume(self):
        spec=importlib.util.spec_from_file_location('regard_editorial_pub_test',ROOT/'cogs'/'regard_editorial.py')
        editorial=importlib.util.module_from_spec(spec);spec.loader.exec_module(editorial)
        fake_util=types.ModuleType('discord.utils');fake_util.escape_markdown=lambda x:x
        fake_discord=types.ModuleType('discord');fake_discord.utils=fake_util;fake_discord.Thread=FakeThread
        fake_discord.AllowedMentions=types.SimpleNamespace(none=lambda:None)
        fake_discord.HTTPException=Exception;fake_discord.Forbidden=Exception
        old_mod=sys.modules.get('discord');old_utils=sys.modules.get('discord.utils')
        sys.modules['discord']=fake_discord;sys.modules['discord.utils']=fake_util
        try:
            tree=ast.parse(FILE.read_text())
            conn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='connect')
            cog=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='RegardDuJour')
            funcs=[x for x in cog.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name in ('publish','followup_link','ensure_post_parts','update_daily_index')]
            with tempfile.TemporaryDirectory() as tmp:
                ctx={'contextmanager':contextmanager,'DB':Path(tmp)/'regard.sqlite3','sqlite3':sqlite3,'datetime':datetime,
                     'timedelta':timedelta,'TZ':timezone.utc,'discord':fake_discord,
                     'GUILD_ID':123,'AUTO_MODE':True,'ARTICLE_MAX':5,'ARTICLE_MIN':3,
                     'article_card':editorial.article_card,'followup_story':editorial.followup_story,
                     'support_resources':editorial.support_resources,'shorten':lambda x,n=180:x[:n],'logger':types.SimpleNamespace(warning=lambda *a:None)}
                tree=ast.fix_missing_locations(ast.Module(body=[conn,ast.ClassDef(name='RegardTest',bases=[],keywords=[],body=funcs,decorator_list=[])],type_ignores=[]))
                exec(compile(tree,str(FILE),'exec'),ctx)
                forum=FakeForum();bot=types.SimpleNamespace(user=types.SimpleNamespace(id=42),get_channel=forum.get_thread)
                subject=ctx['RegardTest']();subject.lock=asyncio.Lock();subject.bot=bot
                async def channels():return forum,None
                async def song(day):return {'title':'Titre validé','artist':'Artiste','url':'https://music.apple.com/','description':'Morceau vérifié'}
                subject.channels=channels;subject.select_music=song
                day='2026-11-09'
                with ctx['connect']() as db:
                    db.execute('INSERT INTO regard_items(day,title,url,category,status,created_at,source,published_at) VALUES(?,?,?,?,?,?,?,?)',
                        (day,'Une affaire de discrimination raciste fait l’objet d’une enquête à Paris','https://news.google.com/rss/articles/1',
                        'Discriminations','approved',day,'Le Monde',day))
                result1=asyncio.run(subject.publish(day))
                result2=asyncio.run(subject.publish(day))
                self.assertEqual(forum.creations,1)
                self.assertIn('<#101>',result1)
                self.assertIn('<#101>',result2)
                self.assertEqual(len(forum.threads[0].messages),5)
                with ctx['connect']() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM regard_thread_parts').fetchone()[0],5)
        finally:
            if old_mod is None:sys.modules.pop('discord',None)
            else:sys.modules['discord']=old_mod
            if old_utils is None:sys.modules.pop('discord.utils',None)
            else:sys.modules['discord.utils']=old_utils

if __name__=='__main__':unittest.main()

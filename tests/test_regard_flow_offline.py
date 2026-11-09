"""Smoke test offline du flux RSS -> SQLite -> sélection sans Discord."""
import ast
from contextlib import contextmanager
import asyncio
import importlib.util
import sqlite3
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from unittest.mock import Mock
import aiohttp

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'cogs'/'regard_du_jour.py'

class FeedResponse:
    def __init__(self, raw):self.raw=raw
    async def __aenter__(self):return self
    async def __aexit__(self,*a):return False
    def raise_for_status(self):pass
    async def read(self):return self.raw

class FeedSession:
    def __init__(self, raw, **kwargs):self.raw=raw
    async def __aenter__(self):return self
    async def __aexit__(self,*a):return False
    def get(self,*args,**kwargs):return FeedResponse(self.raw)

class FlowSmoke(unittest.TestCase):
    def test_collect_select_dedupe(self):
        tree=ast.parse(FILE.read_text(encoding='utf-8'))
        connect=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='connect')
        cog=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='RegardDuJour')
        funcs=[x for x in cog.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name in ('collect','auto_select')]
        spec=importlib.util.spec_from_file_location('regard_editorial_flow_test',ROOT/'cogs'/'regard_editorial.py')
        editorial=importlib.util.module_from_spec(spec);spec.loader.exec_module(editorial)
        today=datetime.now(timezone.utc).date()
        titles=[
            'Une condamnation judiciaire pour discrimination raciste à Paris',
            'Une enquête ouverte pour agression homophobe à Lyon',
            'Un procès portant sur des faits antisémites à Marseille',
            'Une association mène une initiative contre la transphobie et pour la solidarité',
            'Une procédure judiciaire liée à une discrimination pour handicap à Nantes',
            'Une condamnation judiciaire pour discrimination raciste à Paris',
        ]
        news=''.join('<item><title>'+title+'</title><link>https://news.google.com/rss/articles/ID'+str(i)+'</link><source url="https://www.lemonde.fr/">Le Monde</source><pubDate>'+datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')+'</pubDate></item>' for i,title in enumerate(titles))
        rss=('<rss><channel>'+news+'</channel></rss>').encode()
        with tempfile.TemporaryDirectory() as d:
            ctx=dict(contextmanager=contextmanager,sqlite3=sqlite3,DB=Path(d)/'regard.sqlite3',aiohttp=aiohttp,ET=ET,
                datetime=datetime,quote=quote,asyncio=asyncio,TOPICS=[('Discriminations','France racisme')],
                TZ=timezone.utc,logger=Mock(),TRUSTED_EXTRA=frozenset(),
                trusted_source=editorial.trusted_source,news_date=editorial.news_date,
                relevant_headline=editorial.relevant_headline,within_recent_days=editorial.within_recent_days,
                same_story=editorial.same_story,editorial_duplicate=editorial.editorial_duplicate,news_score=editorial.news_score,feed_excerpt=editorial.feed_excerpt,
                timedelta=timedelta,ARTICLE_MAX=5)
            # Direct recompile limited methods; no discord dependency.
            exec(compile(ast.fix_missing_locations(ast.Module(body=[connect,ast.ClassDef(name='Regard',bases=[],keywords=[],body=funcs,decorator_list=[])],type_ignores=[])),str(FILE),'exec'),ctx)
            ctx['shorten']=lambda x,n=180: x[:n]
            ctx['aiohttp']=types.SimpleNamespace(ClientTimeout=aiohttp.ClientTimeout,ClientSession=lambda **kw:FeedSession(rss),ClientError=aiohttp.ClientError)
            cog_instance=ctx['Regard']()
            count=asyncio.run(cog_instance.collect(today.isoformat()))
            selected=cog_instance.auto_select(today.isoformat())
            self.assertEqual(count,6)
            self.assertGreaterEqual(selected,3)
            self.assertLessEqual(selected,5)
            self.assertEqual(cog_instance.auto_select(today.isoformat()),0)
            with ctx['connect']() as db:
                rows=db.execute("SELECT title FROM regard_items WHERE status='approved'").fetchall()
                self.assertEqual(len({x['title'] for x in rows}),len(rows))

if __name__=='__main__':unittest.main()

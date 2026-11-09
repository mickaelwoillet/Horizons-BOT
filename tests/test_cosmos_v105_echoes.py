"""V10.5: pure SQLite tests, no Discord token required."""
import ast
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'cogs' / 'chaos_cosmique.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
NAMES = {'resolve_due_echoes', 'echo_inbox'}
FUNCTIONS = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in NAMES]
NAMESPACE = {'hashlib':hashlib, 'datetime':datetime, 'LOCAL_TIMEZONE':__import__('zoneinfo').ZoneInfo('Europe/Paris'),
             'ECHO_TWISTS':('Premier retour','Deuxième retour','Troisième retour')}
exec(compile(ast.Module(body=FUNCTIONS,type_ignores=[]),str(SOURCE),'exec'),NAMESPACE)

def db():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.execute('CREATE TABLE cosmic_echoes (guild_id INTEGER,user_id INTEGER,source_day TEXT,due_day TEXT,arc_key TEXT,choice INTEGER,status TEXT DEFAULT "pending",result TEXT DEFAULT "",PRIMARY KEY(guild_id,user_id,source_day))')
    conn.execute('CREATE TABLE cosmic_journal (guild_id INTEGER,at TEXT,entry TEXT)')
    return conn

def test_due_once_and_persistent():
    c=db()
    c.execute('INSERT INTO cosmic_echoes(guild_id,user_id,source_day,due_day,arc_key,choice) VALUES(1,2,"2026-11-09","2026-11-11","couronne",1)')
    assert NAMESPACE['resolve_due_echoes'](c,1,'2026-11-10') == []
    first=NAMESPACE['resolve_due_echoes'](c,1,'2026-11-11')
    assert len(first)==1 and first[0][0]==2
    assert NAMESPACE['resolve_due_echoes'](c,1,'2026-11-12') == []
    assert c.execute('SELECT count(*) FROM cosmic_journal').fetchone()[0]==1
    assert 'Écho du 2026-11-09' in NAMESPACE['echo_inbox'](c,1,2,'2026-11-12')

def test_separation_by_guild_and_user():
    c=db()
    for guild,user in [(1,2),(2,3)]:
        c.execute('INSERT INTO cosmic_echoes(guild_id,user_id,source_day,due_day,arc_key,choice) VALUES(?,?,?,?,?,?)',(guild,user,'2026-11-09','2026-11-11','etoile',0))
    assert len(NAMESPACE['resolve_due_echoes'](c,1,'2026-11-12'))==1
    assert 'Aucun écho' in NAMESPACE['echo_inbox'](c,1,99,'2026-11-12')
    assert c.execute('SELECT status FROM cosmic_echoes WHERE guild_id=2').fetchone()[0]=='pending'

def test_dashboard_and_clock_hooks():
    text=SOURCE.read_text(encoding='utf-8')
    assert "custom_id='cosmic:v105:nox:echoes'" in text
    assert 'resolve_due_echoes(conn,guild.id' in text
    assert 'INSERT OR IGNORE INTO cosmic_echoes' in text

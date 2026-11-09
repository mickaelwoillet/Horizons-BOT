import ast, sqlite3, datetime, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'cogs/nox_tv.py').read_text(encoding='utf8')

def resolver():
    tree=ast.parse(SOURCE)
    f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='resolve_old_votes')
    ns={}
    exec(compile(ast.Module(body=[f],type_ignores=[]),'<extracted>','exec'),ns)
    return ns['resolve_old_votes']

def db():
    conn=sqlite3.connect(':memory:'); conn.row_factory=sqlite3.Row
    conn.executescript('''CREATE TABLE noxtv_posts (guild_id INTEGER,day TEXT,visual_id TEXT,message_id INTEGER);
    CREATE TABLE noxtv_votes (message_id INTEGER,user_id INTEGER,guild_id INTEGER,choice INTEGER);
    CREATE TABLE noxtv_outcomes(message_id INTEGER PRIMARY KEY,guild_id INTEGER,winning_choice INTEGER,vote_count INTEGER,resolved_at TEXT,followup_sent INTEGER DEFAULT 0);''')
    return conn

def test_vote_closure_is_persistent_and_deterministic():
    c=db(); c.execute("INSERT INTO noxtv_posts VALUES(1,'2026-11-08','duck',42)")
    c.executemany('INSERT INTO noxtv_votes VALUES(?,?,1,?)',[(42,1,1),(42,2,0),(42,3,1)])
    now=datetime.datetime(2026,11,9,12)
    assert resolver()(c,1,now)==[(42,'duck',1,3)]
    assert resolver()(c,1,now)==[]
    assert c.execute('SELECT COUNT(*) FROM noxtv_outcomes').fetchone()[0]==1

def test_no_votes_close_silently():
    c=db(); c.execute("INSERT INTO noxtv_posts VALUES(1,'2026-11-08','duck',43)")
    assert resolver()(c,1,datetime.datetime(2026,11,9))==[(43,'duck',-1,0)]

def test_current_day_not_closed():
    c=db(); c.execute("INSERT INTO noxtv_posts VALUES(1,'2026-11-09','duck',44)")
    assert resolver()(c,1,datetime.datetime(2026,11,9))==[]

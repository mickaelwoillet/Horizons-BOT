import sqlite3
from cogs import nox_junior_personnalite as p

def test_profile_persistent_and_individual():
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    assert p.profile(con,1)==p.profile(con,1)
    assert p.profile(con,1)!=p.profile(con,2)

def test_progress_daily_once_and_replay():
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    before=p.profile(con,1)
    assert p.record(con,1,'complicite:parler',now=100000)
    assert not p.record(con,1,'complicite:parler',now=100010)
    assert p.profile(con,1)['affection']==before['affection']+1
    assert p.record(con,1,'complicite:parler',now=200000)
    assert p.profile(con,1)['affection']==before['affection']+2

def test_walk_and_invalid_activity():
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    before=p.profile(con,5)
    assert p.record(con,5,'promenade:plage_lunaire',now=100000)
    assert p.profile(con,5)['courage']==before['courage']+1
    try: p.record(con,5,'inconnue',now=100000)
    except ValueError: pass
    else: assert False

def test_cap():
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
    p.profile(con,3)
    con.execute('UPDATE junior_personality SET malice=100 WHERE pet_id=3')
    assert p.record(con,3,'complicite:jouets',now=100000)
    assert p.profile(con,3)['malice']==100

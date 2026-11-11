from cogs import nox_junior_aventures as adventures
from cogs import nox_junior_engine as engine
import pytest

@pytest.mark.parametrize('region',list(adventures.WALKS))
def test_walk_three_steps_and_replay(region):
    def run():
        session=adventures.start(region)
        for i in range(3):
            assert len(adventures.choices(session))==3
            session=adventures.advance(session,i%3)
        assert session['done']
        assert session['souvenir'] in adventures.WALKS[region][2]
        return session['souvenir']
    assert run()==run()

def test_invalid_choice():
    with pytest.raises(ValueError): adventures.advance(adventures.start('jardin'),99)

def test_walk_album_no_economy(tmp_path):
    with engine.connect(tmp_path/'junior.db') as con:
        con.execute('INSERT INTO junior_pets(guild_id,owner_id,slot,name,color,created_at,updated_at) VALUES(1,2,1,\'Nox\',\'bleu\',0,0)')
        pid=con.execute('SELECT id FROM junior_pets').fetchone()['id']
        engine.walk_memory_add(con,pid,2,1,'jardin','La luciole curieuse',now=10)
        engine.walk_memory_add(con,pid,2,1,'jardin','La luciole curieuse',now=20)
        memories=engine.walk_memories(con,pid,2,1)
        assert len(memories)==1 and memories[0]['visits']==2
        assert con.execute('SELECT COUNT(*) AS n FROM junior_star_rewards').fetchone()['n']==0
        assert con.execute('SELECT COUNT(*) AS n FROM junior_daily_care').fetchone()['n']==0

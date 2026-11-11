from cogs import nox_junior_aventures as a
from pathlib import Path

def test_seven_walks_have_images():
    assert len(a.WALKS)==7
    root=Path(__file__).resolve().parents[1]
    for code in a.WALKS:
        assert (root/a.SCENE_IMAGES[code]).is_file()

def test_each_walk_is_replayable():
    for code in a.WALKS:
        session=a.start(code)
        for _ in range(3):
            assert len(a.choices(session))==3
            session=a.advance(session,0)
        assert session['done']
        assert session['souvenir']
        assert a.start(code)['step']==0

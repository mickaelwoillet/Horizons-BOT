import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'data'/'nox_tv'

def test_new_scenes_assets():
    for filename in ('nox_jeu_ballon.png','gloups_planete_fugueuse.png'):
        with Image.open(MEDIA/filename) as image:
            image.verify()
        with Image.open(MEDIA/filename) as image:
            assert image.size == (1200,675)

def test_new_scenes_catalogue_and_routes():
    catalogue=json.loads((MEDIA/'catalogue.json').read_text(encoding='utf-8'))
    assert len(catalogue)>=25
    assert len({x['id'] for x in catalogue})==len(catalogue)
    assert all((MEDIA/x['file']).is_file() for x in catalogue)
    scenes={x['id']:x for x in catalogue}
    assert scenes['nox_jeu_ballon']['kind']=='nox'
    assert scenes['gloups_planete_fugueuse']['kind']=='gloups'

def test_new_scenes_have_verdicts():
    source=(ROOT/'cogs'/'nox_tv.py').read_text(encoding='utf-8')
    assert "'nox_jeu_ballon': (" in source
    assert "'gloups_planete_fugueuse': (" in source

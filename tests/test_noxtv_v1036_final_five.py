import json
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'data'/'nox_tv'
IDS={'nox_biscuits_orbite':'nox','coincoin_couronne_rebelle':'canard','paradoxe_reveil_infini':'paradoxe','grille_pain_tartine_maire':'grille_pain','exploration_portail_chaussettes':'exploration'}

def test_catalogue_30_unique_complete():
    entries=json.loads((MEDIA/'catalogue.json').read_text(encoding='utf-8'))
    assert len(entries)==30
    assert len({x['id'] for x in entries})==30
    assert len({x['file'] for x in entries})==30
    assert all((MEDIA/x['file']).is_file() for x in entries)

def test_five_new_distinct_visuals():
    from PIL import ImageChops
    images=[]
    for sid in IDS:
        with Image.open(MEDIA/(sid+'.png')) as im:
            assert im.size==(1200,675)
            images.append(im.convert('RGB').copy())
    assert all(ImageChops.difference(images[i],images[j]).getbbox() for i in range(5) for j in range(i+1,5))

def test_five_new_routes_and_verdicts():
    entries={x['id']:x for x in json.loads((MEDIA/'catalogue.json').read_text(encoding='utf-8'))}
    source=(ROOT/'cogs'/'nox_tv.py').read_text(encoding='utf-8')
    for sid,kind in IDS.items():
        assert entries[sid]['kind']==kind
        assert repr(sid)+': (' in source

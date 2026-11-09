import json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]

def test_duck_animation_is_genuine_and_small():
    p=ROOT/'data/nox_tv/canard_matraque_anime.gif'
    with Image.open(p) as img:
        assert img.n_frames >= 6
        assert img.width >= 480 and img.height >= 270
        assert abs(img.width / img.height - 16 / 9) < 0.02
    assert p.stat().st_size < 8*1024*1024

def test_catalogue_and_verdicts():
    entries=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text())
    assert len({e['id'] for e in entries}) == len(entries)
    duck=next(e for e in entries if e['id']=='canard_matraque_anime')
    assert duck['kind']=='canard'
    source=(ROOT/'cogs/nox_tv.py').read_text()
    assert "'canard_matraque_anime': (" in source

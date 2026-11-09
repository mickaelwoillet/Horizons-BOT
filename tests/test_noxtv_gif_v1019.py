import json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
MEDIA=ROOT/'data'/'nox_tv'

def test_gif_has_animation():
    with Image.open(MEDIA/'nox_etoile.gif') as image:
        assert image.format=='GIF'
        assert image.n_frames >= 4

def test_catalogue_paths_and_ids():
    items=json.loads((MEDIA/'catalogue.json').read_text(encoding='utf-8'))
    assert len(items)>=16
    assert len({item['id'] for item in items})==len(items)
    assert all(Path(item['file']).name==item['file'] and (MEDIA/item['file']).is_file() for item in items)
    assert next(item for item in items if item['id']=='nox_etoile')['kind']=='nox'

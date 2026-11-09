from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'cogs/nox_tv.py').read_text(encoding='utf-8')

def test_module_syntax():
    ast.parse(SOURCE)

def test_safe_media_is_used_for_publish_and_preview():
    assert SOURCE.count("safe_media_path(item['file'])") == 2
    assert 'MAX_MEDIA_BYTES = 8 * 1024 * 1024' in SOURCE

def test_catalogue_media_present_and_below_limit():
    folder = ROOT / 'data/nox_tv'
    items = json.loads((folder / 'catalogue.json').read_text(encoding='utf-8'))
    assert len(items) >= 16
    assert len({item['id'] for item in items}) == len(items)
    for item in items:
        media = folder / item['file']
        assert media.is_file()
        assert 0 < media.stat().st_size <= 8 * 1024 * 1024

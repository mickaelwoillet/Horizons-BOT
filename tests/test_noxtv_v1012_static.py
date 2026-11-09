import ast,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_catalogue_and_files():
    items=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text())
    assert len(items)>=9
    assert len({x['id'] for x in items})==len(items)
    assert all((ROOT/'data/nox_tv'/x['file']).is_file() for x in items)
def test_migration_and_manual_channel():
    source=(ROOT/'cogs/nox_tv.py').read_text()
    ast.parse(source)
    assert 'ALTER TABLE noxtv_manual_posts ADD COLUMN channel_id' in source
    assert 'created_at,channel_id' in source
    assert 'CASE WHEN m.channel_id>0 THEN m.channel_id ELSE s.channel_id END' in source

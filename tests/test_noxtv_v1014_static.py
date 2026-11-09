from pathlib import Path
import ast, json
ROOT=Path(__file__).resolve().parents[1]
CODE=(ROOT/'cogs/nox_tv.py').read_text()
def test_syntax(): ast.parse(CODE)
def test_catalogue_files():
    entries=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text())
    assert len(entries)>=9
    assert all((ROOT/'data/nox_tv'/x['file']).is_file() for x in entries)
def test_staff_commands():
    assert "name='catalogue'" in CODE
    assert 'visual_id=scene' in CODE
def test_reservation_cleanup():
    assert 'self._release_reservation(guild.id, day, manual)' in CODE

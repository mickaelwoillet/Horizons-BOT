import ast, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def test_valid_python(): ast.parse((ROOT/'cogs/nox_tv.py').read_text(encoding='utf-8'))
def test_mood_coverage():
 entries=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text(encoding='utf-8'))
 assert {'fatigue','calin','panique'} <= {m for e in entries for m in e.get('moods',[])}
def test_files_exist():
 entries=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text(encoding='utf-8'))
 assert all((ROOT/'data/nox_tv'/e['file']).is_file() for e in entries)

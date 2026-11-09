from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def test_two_new_scenes_exist():
    entries=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text())
    assert len(entries)>=13
    assert len({x['id'] for x in entries})==len(entries)
    for entry in entries:
        assert (ROOT/'data/nox_tv'/entry['file']).is_file()

def test_new_scenes_have_verdicts_and_routes():
    source=(ROOT/'cogs/nox_tv.py').read_text()
    for scene in ('paradoxe_mardi_25','gloups_experience_547'):
        assert f"'{scene}': (" in source
    assert "'paradoxe': 'anomalies'" in source
    assert "'gloups': 'observatoire'" in source

def test_preflight_permissions_and_manual_tracking():
    source=(ROOT/'cogs/nox_tv.py').read_text()
    assert 'perms.attach_files' in source
    assert 'INSERT OR IGNORE INTO noxtv_manual_posts' in source
    assert 'self._release_reservation(guild.id, day, manual)' in source

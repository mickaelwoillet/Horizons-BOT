from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_bilan_staff_read_only():
    src=(ROOT/'cogs/nox_tv.py').read_text(encoding='utf-8')
    section=src.split("@noxtv.command(name='bilan'",1)[1].split("@noxtv.command(name='votes'",1)[0]
    assert 'has_permissions(manage_guild=True)' in section
    assert 'ephemeral=True' in section
    assert 'COUNT(DISTINCT user_id)' in section
    assert 'INSERT INTO' not in section and 'UPDATE ' not in section and 'DELETE FROM' not in section

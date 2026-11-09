from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / 'cogs' / 'nox_tv.py').read_text(encoding='utf-8')

def test_persistent_buttons():
    assert 'timeout=None' in SRC
    for name in ('noxtv:vote:0', 'noxtv:vote:1', 'noxtv:vote:2'):
        assert name in SRC

def test_vote_uniqueness_and_restart_registration():
    assert 'PRIMARY KEY(message_id,user_id)' in SRC
    assert 'ON CONFLICT(message_id,user_id) DO UPDATE' in SRC
    assert 'self.bot.add_view(NoxTVChoices())' in SRC

def test_manual_testing_and_permissions_preserved():
    assert "manual=True" in SRC
    assert 'has_permissions(manage_guild=True)' in SRC
    assert 'view=NoxTVChoices()' in SRC

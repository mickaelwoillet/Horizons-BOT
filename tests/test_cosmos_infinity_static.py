"""V10 tests hors connexion, contrôles structurels et de migration."""
import ast
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'cogs'/'chaos_cosmique.py').read_text()
TREE=ast.parse(SOURCE)

def test_legacy_commands_preserved():
    for name in ('installer','histoire','activer','nox','soigner','carte','visiter','sac','chroniques','diagnostic'):
        assert f"name='{name}'" in SOURCE

def test_new_dashboard_registered():
    assert "name='nox', description='👾 Tableau de bord" in SOURCE
    assert 'self.bot.add_view(NoxPanel())' in SOURCE
    assert 'self.bot.add_view(CosmicStoryButtons())' in SOURCE

def test_persistent_buttons_unique():
    import re
    ids=re.findall(r"custom_id='(cosmic:v10:[^']+)'",SOURCE)
    assert len(ids)>=12
    assert len(ids)==len(set(ids))

def test_story_updates_without_duplicate():
    assert 'old_message.edit(embed=embed,view=CosmicStoryButtons()' in SOURCE
    assert "attachments=[discord.File(art" in SOURCE

def test_member_permissions_preserved():
    assert 'add_reactions=True, send_messages=False' in SOURCE

def test_art_present():
    assert (ROOT/'data/chaos_cosmique/histoire_chaos_cosmique.png').stat().st_size>100_000

def test_no_paid_api_needed():
    assert 'openai' not in SOURCE.lower()

from pathlib import Path
import ast

SRC=Path(__file__).resolve().parents[1]/'cogs'/'chaos_cosmique.py'
TEXT=SRC.read_text(encoding='utf-8')
TREE=ast.parse(TEXT)

def test_syntax_and_mission_tables():
    assert 'CREATE TABLE IF NOT EXISTS cosmic_missions' in TEXT
    assert 'CREATE TABLE IF NOT EXISTS cosmic_bonds' in TEXT
    assert 'CREATE TABLE IF NOT EXISTS cosmic_secrets' in TEXT

def test_claim_once_and_action_prerequisite():
    fn=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='claim_mission')
    code=ast.get_source_segment(TEXT,fn)
    assert 'if not completed' in code
    assert 'claimed_at IS NULL' in code
    assert 'if not cur.rowcount' in code

def test_bonds_not_farmable():
    fn=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='encounter_character')
    code=ast.get_source_segment(TEXT,fn)
    assert 'last_meeting!=?' in code
    assert 'INSERT OR IGNORE INTO cosmic_secrets' in code

def test_new_controls_are_persistent_or_ephemeral():
    assert "custom_id='cosmic:v101:nox:mission'" in TEXT
    assert "custom_id='cosmic:v101:nox:secrets'" in TEXT
    assert "custom_id='cosmic:v101:story:mission'" in TEXT
    assert 'view=CosmicMissionClaim(),ephemeral=True' in TEXT

def test_existing_install_and_old_controls_preserved():
    assert "@cosmos.command(name='installer'" in TEXT
    assert "@app_commands.command(name='nox'" in TEXT
    assert "custom_id='cosmic:v10:story:nox'" in TEXT

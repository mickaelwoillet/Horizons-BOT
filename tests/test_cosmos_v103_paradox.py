from pathlib import Path
import ast
p=Path(__file__).resolve().parents[1]/'cogs'/'chaos_cosmique.py'
s=p.read_text(encoding='utf-8')
mod=ast.parse(s)
functions={n.name for n in mod.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
assert {'paradox_scene','paradox_status','choose_paradox','show_paradox'} <= functions
assert 'CREATE TABLE IF NOT EXISTS cosmic_paradox_choices' in s
assert 'PRIMARY KEY(guild_id,user_id,day)' in s
assert 'Portail des paradoxes' in s and 'Portail secret' in s
assert 'custom_id=\'cosmic:v102:nox:rumor\'' in s # preserve existing persistent button identity
print('V10.3 paradox static checks OK')

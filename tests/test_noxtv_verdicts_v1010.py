import ast
from pathlib import Path

SOURCE=Path(__file__).resolve().parents[1]/'cogs'/'nox_tv.py'

def load_verdict():
    tree=ast.parse(SOURCE.read_text(encoding='utf8'))
    keep=[node for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('OUTCOMES','SCENE_VERDICTS') for t in node.targets)]
    keep += [node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='verdict_for']
    scope={}
    exec(compile(ast.Module(body=keep,type_ignores=[]),str(SOURCE),'exec'),scope)
    return scope

def test_each_scene_has_distinct_conclusions():
    scope=load_verdict()
    assert len(scope['SCENE_VERDICTS'])>=5
    assert all(len(v)==3 for v in scope['SCENE_VERDICTS'].values())
    assert len({text for variants in scope['SCENE_VERDICTS'].values() for text in variants})>=15

def test_verdict_fallback_and_no_votes():
    v=load_verdict()['verdict_for']
    assert 'sans suite' in v('nox_faim',-1)
    assert 'collecte' in v('nox_faim',0)
    assert 'décret' in v('unknown',1)

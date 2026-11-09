from pathlib import Path
import json, ast, zipfile
ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'cogs/nox_tv.py').read_text()

def test_preview_command_is_private_and_does_not_publish():
    tree=ast.parse(SOURCE)
    cog=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NoxTV')
    fn=next(n for n in cog.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='apercu')
    code=ast.get_source_segment(SOURCE,fn)
    assert 'ephemeral=True' in code
    assert 'self.publish(' not in code
    assert 'NoxTVChoices' not in code

def test_media_manifest_complete_and_safe():
    data=json.loads((ROOT/'data/nox_tv/catalogue.json').read_text())
    assert len(data)>=16
    assert len({x['id'] for x in data})==len(data)
    for item in data:
        assert Path(item['file']).name==item['file']
        assert (ROOT/'data/nox_tv'/item['file']).is_file()
        assert item['kind'] in {'nox','canard','grille_pain','paradoxe','gloups','exploration','chronique'}

def test_readme_documents_preview():
    assert '/noxtv apercu' in (ROOT/'README.md').read_text()

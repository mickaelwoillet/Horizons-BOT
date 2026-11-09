import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'cogs' / 'nox_tv.py').read_text(encoding='utf-8')
CATALOG = ROOT / 'data' / 'nox_tv' / 'catalogue.json'


def test_audit_command_is_staff_only_and_ephemeral():
    tree = ast.parse(SOURCE)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NoxTV')
    audit = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'audit')
    decorators = ast.get_source_segment(SOURCE, audit)
    assert "report = audit_catalogue()" in decorators
    assert 'ephemeral=True' in decorators
    assert 'has_permissions(manage_guild=True)' in SOURCE


def test_all_catalogue_assets_are_present():
    entries = json.loads(CATALOG.read_text(encoding='utf-8'))
    assert len(entries) >= 16
    assert len({entry['id'] for entry in entries}) == len(entries)
    for entry in entries:
        assert (CATALOG.parent / entry['file']).is_file(), entry['id']


def test_audit_does_not_write_database_or_send_public_message():
    tree = ast.parse(SOURCE)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'audit_catalogue')
    src = ast.get_source_segment(SOURCE, fn)
    assert 'connect(' not in src
    assert 'send(' not in src
    assert 'safe_media_path' in src

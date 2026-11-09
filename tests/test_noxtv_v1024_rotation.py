from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'cogs' / 'nox_tv.py').read_text(encoding='utf-8')


def test_module_compiles():
    ast.parse(SOURCE)


def test_manual_posts_do_not_change_automatic_rotation():
    start = SOURCE.index('            # Les aperçus/tests manuels')
    end = SOURCE.index('            choices=', start)
    query = SOURCE[start:end]
    assert 'FROM noxtv_posts' in query
    assert 'FROM noxtv_manual_posts' not in query
    assert 'ORDER BY day DESC LIMIT 2' in query


def test_catalogue_has_no_duplicate_ids_and_all_media_exist():
    items = json.loads((ROOT / 'data/nox_tv/catalogue.json').read_text(encoding='utf-8'))
    assert len(items) == len({item['id'] for item in items})
    for item in items:
        assert (ROOT / 'data/nox_tv' / item['file']).is_file()


def test_no_unintended_data_files_in_zip_build():
    assert not list(ROOT.rglob('*.sqlite3'))

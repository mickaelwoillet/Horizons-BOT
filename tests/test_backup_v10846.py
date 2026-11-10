"""Tests autonomes du moteur de sauvegarde, sans connexion Discord."""
import ast
from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'cogs' / 'continuity.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
FUNCTIONS = {'sqlite_backup', 'database_health', 'backup_all_databases', 'backup_diagnostic'}
selected = [node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]

class BackupTests(unittest.TestCase):
    def test_multiple_databases_and_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'data'; data.mkdir()
            backup = data / 'backups'
            namespace = dict(Path=Path, datetime=datetime, timezone=timezone, timedelta=timedelta,
                             sqlite3=sqlite3, json=json, os=os, log=logging.getLogger('test'),
                             DATA_DIR=data, DB_PATH=data / 'horizons.sqlite3', BACKUP_DIR=backup,
                             STATUS_PATH=data / 'backup_status.json', RETENTION_DAYS=14)
            exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), 'exec'), namespace)
            for name in ('horizons.sqlite3', 'nox_tv.sqlite3', 'chaos_cosmique.sqlite3'):
                with sqlite3.connect(data / name) as conn:
                    conn.execute('PRAGMA journal_mode=WAL')
                    conn.execute('CREATE TABLE t (value TEXT)')
                    conn.execute('INSERT INTO t VALUES (?)', (name,))
            result = namespace['backup_all_databases'](data, backup)
            self.assertEqual(set(result), {'horizons.sqlite3', 'nox_tv.sqlite3', 'chaos_cosmique.sqlite3'})
            self.assertTrue(all(v == 'ok' for v in result.values()))
            for name in result:
                copies = list(backup.glob(name.removesuffix('.sqlite3') + '-*.sqlite3'))
                self.assertEqual(len(copies), 1)
                with sqlite3.connect(copies[0]) as conn:
                    self.assertEqual(conn.execute('SELECT value FROM t').fetchone()[0], name)
            self.assertEqual(namespace['backup_diagnostic'](data)['databases'], result)
            self.assertEqual(len(list(backup.glob('*.sqlite3'))), 3)

if __name__ == '__main__':
    unittest.main()

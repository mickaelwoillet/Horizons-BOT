"""Contrôles hors ligne avant mise à jour HORIZONS (sans connexion Discord)."""
from pathlib import Path
import ast
import json
import os
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
errors = []
warnings = []

for path in ROOT.rglob('*.py'):
    if any(p in {'.git', '.venv', 'venv'} for p in path.parts):
        continue
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (SyntaxError, UnicodeError) as exc:
        errors.append(f'Python {path.relative_to(ROOT)} : {exc}')

for path in ROOT.rglob('*.json'):
    try:
        with path.open(encoding='utf-8') as stream:
            json.load(stream)
    except (ValueError, UnicodeError, OSError) as exc:
        errors.append(f'JSON {path.relative_to(ROOT)} : {exc}')

example = ROOT / '.env.example'
if not example.is_file():
    warnings.append('Fichier .env.example absent.')
if not (ROOT / '.env').exists() and not os.environ.get('DISCORD_TOKEN'):
    warnings.append('Aucun .env local / DISCORD_TOKEN : configurer le serveur avant le lancement.')
if not (ROOT / 'requirements.txt').is_file():
    errors.append('requirements.txt absent.')

sqlite_path = ROOT / 'data' / 'horizons.sqlite3'
if sqlite_path.exists():
    try:
        con = sqlite3.connect(f'file:{sqlite_path.as_posix()}?mode=ro', uri=True)
        try:
            result = con.execute('PRAGMA quick_check').fetchone()[0]
            if result != 'ok':
                errors.append(f'Base SQLite : {result}')
        finally:
            con.close()
    except sqlite3.Error as exc:
        errors.append(f'Base SQLite : {exc}')
    warnings.append('Base SQLite incluse : ne jamais écraser celle de production sans sauvegarde.')
else:
    warnings.append('Aucune base SQLite fournie : elle peut être créée au démarrage.')

for msg in warnings:
    print('AVERTISSEMENT :', msg)
for msg in errors:
    print('ERREUR :', msg)
print(f'Prévol : {"ÉCHEC" if errors else "OK"} — {len(errors)} erreur(s), {len(warnings)} avertissement(s).')
sys.exit(1 if errors else 0)

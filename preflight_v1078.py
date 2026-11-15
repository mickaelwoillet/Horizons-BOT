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

# Cohérence des extensions, sans importer discord.py ni contacter Discord.
bot_file = ROOT / 'bot.py'
if bot_file.is_file():
    try:
        tree = ast.parse(bot_file.read_text(encoding='utf-8'))
        extensions = None
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'EXTENSIONS':
                extensions = ast.literal_eval(node.value)
                break
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EXTENSIONS' for t in node.targets):
                extensions = ast.literal_eval(node.value)
                break
        if extensions is None:
            warnings.append('Impossible de lire la liste EXTENSIONS de bot.py.')
        else:
            for ext in extensions:
                file = ROOT.joinpath(*ext.split('.')).with_suffix('.py')
                if not file.is_file():
                    errors.append(f'Extension introuvable : {ext} ({file.relative_to(ROOT)})')
            if len(set(extensions)) != len(extensions):
                errors.append('La liste EXTENSIONS contient des doublons.')
            print(f'Extensions déclarées : {len(extensions)}')
    except (SyntaxError, ValueError, TypeError) as exc:
        errors.append(f'Impossible de contrôler les extensions : {exc}')

# Vérification des noms et valeurs des variables du modèle .env.
if example.is_file():
    keys = {}
    for line_number, line in enumerate(example.read_text(encoding='utf-8').splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        key = key.strip()
        if key in keys:
            errors.append(f'.env.example : {key} en double (lignes {keys[key]} et {line_number})')
        keys[key] = line_number
        if key.endswith(('_CHANNEL_ID', '_ROLE_ID', '_CATEGORY_ID')) or key in {'GUILD_ID', 'FOUNDER_ID'}:
            raw = value.split('#', 1)[0].strip().strip('\"\'')
            if raw and not raw.isdecimal():
                warnings.append(f'.env.example ligne {line_number} : {key} n\'est pas un identifiant numérique.')
    print(f'Variables .env.example : {len(keys)}')

# Comparaison facultative des identifiants avec un export du serveur Discord.
# Utilisation : python preflight_v1078.py --structure-export chemin/export.json
# Un export est une photographie à une date donnée : un identifiant absent
# est signalé comme avertissement, jamais comme preuve de suppression.
import argparse
parser = argparse.ArgumentParser(description='Prévol hors ligne du bot HORIZONS')
parser.add_argument('--structure-export', type=Path, help='Export JSON de la structure du serveur')
args = parser.parse_args()
if args.structure_export:
    try:
        structure = json.loads(args.structure_export.read_text(encoding='utf-8'))
        channels = {str(item['id']): item for item in structure['channels']}
        roles = {str(item['id']): item for item in structure['roles']}
        checked = 0
        missing = []
        mismatched = []
        for line in example.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            value = value.split('#', 1)[0].strip().strip('"\'')
            if not value.isdecimal():
                continue
            if key.endswith('_ROLE_ID') or key == 'FOUNDER_ROLE_ID':
                target, expected = roles, 'role'
            elif key.endswith('_CATEGORY_ID'):
                target, expected = channels, 'category'
            elif key.endswith('_CHANNEL_ID'):
                target, expected = channels, 'channel'
            else:
                continue
            checked += 1
            entry = target.get(value)
            if entry is None:
                missing.append(key)
            elif expected == 'category' and entry.get('type') != 'category':
                mismatched.append(f'{key} pointe vers {entry.get("type")} au lieu de category')
            elif expected == 'channel' and entry.get('type') == 'category':
                mismatched.append(f'{key} pointe vers une catégorie au lieu d’un salon')
        print(f'Export Discord : {checked} identifiants comparés, {len(missing)} absents, {len(mismatched)} types incohérents.')
        for key in missing:
            warnings.append(f'Export Discord : {key} introuvable (export potentiellement ancien).')
        for detail in mismatched:
            errors.append(f'Export Discord : {detail}')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'Export Discord illisible ou incompatible : {exc}')

# Vérifications ciblées des composants persistants sensibles.
# Ces contrôles restent statiques : ils ne simulent pas une interaction Discord.
critical_views = {
    'cogs/tickets.py': ('TicketView', 'TicketPanelView'),
    'cogs/staff_recrutement.py': ('Acceptance', 'Decision'),
    'cogs/nox_daily_challenges.py': ('ChallengeView',),
}
for relative, required_classes in critical_views.items():
    path = ROOT / relative
    if not path.is_file():
        errors.append(f'Vue persistante : module absent {relative}')
        continue
    tree = ast.parse(path.read_text(encoding='utf-8'))
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    for name in required_classes:
        if name not in classes:
            errors.append(f'Vue persistante : classe {name} absente dans {relative}')
    source = path.read_text(encoding='utf-8')
    if 'add_view(' not in source:
        errors.append(f'Vue persistante : aucun enregistrement add_view dans {relative}')
    if 'custom_id=' not in source:
        errors.append(f'Vue persistante : aucun custom_id dans {relative}')

# Tester les migrations de stockage sur une base TEMPORAIRE, jamais sur les données réelles.
# La simulation reproduit une ancienne table tickets sans colonne claimed_by.
import tempfile
try:
    storage_file = ROOT / 'cogs' / 'storage.py'
    storage_tree = ast.parse(storage_file.read_text(encoding='utf-8'))
    schema = next(ast.literal_eval(node.value) for node in storage_tree.body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCHEMA' for t in node.targets))
    with tempfile.TemporaryDirectory(prefix='horizons-preflight-') as temp:
        path = Path(temp) / 'migration.sqlite3'
        with sqlite3.connect(path) as con:
            con.executescript(schema)
            con.execute("INSERT INTO tickets(guild_id,channel_id,message_id,opener_id,subject,status,created_at) VALUES(1,2,3,4,'Test','open','2026-01-01')")
            columns = {r[1] for r in con.execute('PRAGMA table_info(tickets)')}
            if 'claimed_by' not in columns:
                con.execute('ALTER TABLE tickets ADD COLUMN claimed_by INTEGER')
            row = con.execute('SELECT opener_id,message_id,claimed_by FROM tickets WHERE channel_id=2').fetchone()
            if row != (4, 3, None):
                errors.append('Migration tickets : une donnée historique a été altérée.')
            con.execute('UPDATE tickets SET claimed_by=5 WHERE channel_id=2 AND claimed_by IS NULL')
            if con.execute('SELECT claimed_by FROM tickets WHERE channel_id=2').fetchone()[0] != 5:
                errors.append('Migration tickets : attribution du responsable impossible.')
            if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                errors.append('Migration tickets : contrôle intégrité SQLite échoué.')
    print('Migration SQLite tickets : OK (base temporaire, données réelles intactes)')
except (OSError, sqlite3.Error, SyntaxError, ValueError, StopIteration) as exc:
    errors.append(f'Migration SQLite tickets : {exc}')

# Vérifier le contrat de restauration des tickets ouverts après redémarrage.
ticket_source = (ROOT / 'cogs' / 'tickets.py').read_text(encoding='utf-8')
if not all(token in ticket_source for token in (
    "WHERE status='open' AND message_id IS NOT NULL",
    'self.bot.add_view(TicketView(row["id"]), message_id=row["message_id"])',
    'ALTER TABLE tickets ADD COLUMN claimed_by INTEGER',
)):
    errors.append('Tickets : migration ou restauration des vues persistantes incomplète.')

# Les décisions Staff doivent être restaurées par identifiant de message.
staff_source = (ROOT / 'cogs' / 'staff_recrutement.py').read_text(encoding='utf-8')
if not all(token in staff_source for token in (
    'ALTER TABLE applications ADD COLUMN decision_message_id INTEGER',
    'self.bot.add_view(Decision(member_id), message_id=message_id)',
)):
    errors.append('Staff : migration ou restauration des décisions persistantes incomplète.')

# Vérifier que les identifiants essentiels du parcours Staff et des tickets
# figurent dans le modèle de configuration, sans exposer de secrets.
required_env = {
    'TICKET_LOG_CHANNEL_ID', 'NOX_DISTINCTIONS_CHANNEL_ID',
    'NOX_TV_ADVENTURES_CHANNEL_ID',
}
if example.is_file():
    missing = required_env - set(keys)
    for key in sorted(missing):
        errors.append(f'.env.example : variable essentielle absente : {key}')

# Dépendances indispensables (vérification non intrusive de leur présence).
import importlib.util
for module, package in [('discord', 'discord.py'), ('dotenv', 'python-dotenv'), ('aiohttp', 'aiohttp'), ('PIL', 'Pillow')]:
    if importlib.util.find_spec(module) is None:
        warnings.append(f'Dépendance non installée ici : {package} (pip install -r requirements.txt).')

for msg in warnings:
    print('AVERTISSEMENT :', msg)
for msg in errors:
    print('ERREUR :', msg)
print(f'Prévol : {"ÉCHEC" if errors else "OK"} — {len(errors)} erreur(s), {len(warnings)} avertissement(s).')
sys.exit(1 if errors else 0)

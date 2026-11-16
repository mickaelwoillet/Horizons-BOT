"""Moteur indépendant de Discord pour les aventures HORIZONS.

Les réponses et secrets résident dans des fichiers d'aventure, jamais dans les
messages publics. Une partie peut appartenir à un joueur ou à une équipe.
"""
from __future__ import annotations
import json
from contextlib import contextmanager
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

class AdventureError(ValueError):
    pass

def normalize(value: str) -> str:
    value = unicodedata.normalize('NFKD', value.casefold())
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', value)

def load_adventure(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('rooms'), list):
        raise AdventureError('Catalogue des salles invalide')
    rooms = data['rooms']
    if not rooms or len({room['id'] for room in rooms}) != len(rooms):
        raise AdventureError('Identifiants de salles invalides')
    ids = {r['id'] for r in rooms}
    for room in rooms:
        if not room.get('title') or not isinstance(room.get('puzzles'), list):
            raise AdventureError('Salle incomplète')
        puzzle_ids = {p.get('id') for p in room['puzzles']}
        if len(puzzle_ids) != len(room['puzzles']):
            raise AdventureError('Identifiants d’énigmes dupliqués')
        for puzzle in room['puzzles']:
            if not set(puzzle.get('requires_solved', [])).issubset(puzzle_ids - {puzzle.get('id')}):
                raise AdventureError('Prérequis d’énigme invalides')
            if not puzzle.get('id') or not puzzle.get('answers'):
                raise AdventureError('Énigme incomplète')
            if puzzle.get('next_room') and puzzle['next_room'] not in ids:
                raise AdventureError('Destination inconnue')
            conditional = puzzle.get('conditional_next_room')
            if conditional and conditional.get('room') not in ids:
                raise AdventureError('Destination secrète inconnue')
    return data

class Engine:
    def __init__(self, database: Path):
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS escape_sessions (
                guild_id INTEGER NOT NULL, adventure TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode IN ('solo','team')),
                owner_id INTEGER NOT NULL, room_id TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(guild_id,adventure,mode,owner_id));
            CREATE TABLE IF NOT EXISTS escape_solved (
                guild_id INTEGER NOT NULL, adventure TEXT NOT NULL,
                mode TEXT NOT NULL, owner_id INTEGER NOT NULL,
                puzzle_id TEXT NOT NULL,
                PRIMARY KEY(guild_id,adventure,mode,owner_id,puzzle_id));
            CREATE TABLE IF NOT EXISTS escape_items (
                guild_id INTEGER NOT NULL, adventure TEXT NOT NULL,
                mode TEXT NOT NULL, owner_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                PRIMARY KEY(guild_id,adventure,mode,owner_id,item_id));
            CREATE TABLE IF NOT EXISTS escape_hints (
                guild_id INTEGER NOT NULL, adventure TEXT NOT NULL,
                mode TEXT NOT NULL, owner_id INTEGER NOT NULL,
                puzzle_id TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(guild_id,adventure,mode,owner_id,puzzle_id));
            ''')

    @contextmanager
    def connect(self):
        """Commit on success, roll back on error, and always close SQLite."""
        conn = sqlite3.connect(self.database, timeout=15)
        try:
            conn.execute('PRAGMA busy_timeout=15000')
            with conn:
                yield conn
        finally:
            conn.close()

    def start(self, guild: int, adventure: str, mode: str, owner: int, first_room: str):
        if mode not in ('solo', 'team'):
            raise AdventureError('Mode invalide')
        with self.connect() as con:
            con.execute('INSERT OR IGNORE INTO escape_sessions(guild_id,adventure,mode,owner_id,room_id) VALUES(?,?,?,?,?)',
                        (guild, adventure, mode, owner, first_room))
        return self.status(guild, adventure, mode, owner)

    def status(self, guild: int, adventure: str, mode: str, owner: int):
        with self.connect() as con:
            row = con.execute('SELECT room_id,completed FROM escape_sessions WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                              (guild, adventure, mode, owner)).fetchone()
            if not row:
                return None
            items = [r[0] for r in con.execute('SELECT item_id FROM escape_items WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=? ORDER BY item_id',
                                               (guild, adventure, mode, owner))]
            solved = [r[0] for r in con.execute('SELECT puzzle_id FROM escape_solved WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=? ORDER BY puzzle_id',
                                               (guild, adventure, mode, owner))]
        return {'room_id': row[0], 'completed': bool(row[1]), 'items': items, 'solved': solved}

    def collect(self, guild: int, adventure: str, mode: str, owner: int, item: str):
        """Grant an item only to an active session, atomically."""
        if not isinstance(item, str) or not item.strip():
            raise AdventureError('Objet invalide')
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            session = con.execute(
                'SELECT completed FROM escape_sessions WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner)).fetchone()
            if not session or session[0]:
                raise AdventureError('Partie inexistante ou terminée')
            con.execute('INSERT OR IGNORE INTO escape_items VALUES(?,?,?,?,?)',
                        (guild, adventure, mode, owner, item))

    def combine(self, guild: int, adventure: str, mode: str, owner: int,
                content: dict, item_a: str, item_b: str) -> dict:
        """Combine two owned items using an explicitly declared room recipe.

        All checks and writes happen in one transaction; a failed attempt never
        changes the shared inventory. Recipes can consume their ingredients.
        """
        if item_a == item_b:
            return {'combined': False, 'reason': 'same_item'}
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            session = con.execute(
                'SELECT room_id,completed FROM escape_sessions WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner)).fetchone()
            if not session or session[1]:
                raise AdventureError('Partie inexistante ou terminée')
            room = next((r for r in content['rooms'] if r['id'] == session[0]), None)
            if room is None:
                raise AdventureError('Salle inconnue')
            owned = {r[0] for r in con.execute(
                'SELECT item_id FROM escape_items WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner))}
            if not {item_a, item_b}.issubset(owned):
                return {'combined': False, 'reason': 'missing_items'}
            recipe = next((r for r in room.get('recipes', [])
                           if set(r['ingredients']) == {item_a, item_b}), None)
            if recipe is None:
                return {'combined': False, 'reason': 'no_recipe'}
            result = recipe['result']
            if result in owned:
                return {'combined': True, 'already_created': True, 'item': result}
            if recipe.get('consume', True):
                for item in (item_a, item_b):
                    con.execute('DELETE FROM escape_items WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=? AND item_id=?',
                                (guild, adventure, mode, owner, item))
            con.execute('INSERT OR IGNORE INTO escape_items VALUES(?,?,?,?,?)',
                        (guild, adventure, mode, owner, result))
        return {'combined': True, 'item': result}

    def inspect(self, guild: int, adventure: str, mode: str, owner: int,
                content: dict, hotspot_id: str) -> dict:
        """Inspect a declared decor hotspot, optionally collecting its reward.

        Hotspots are only available in the current room. Requirements are
        checked before any reward is granted. Repeated inspections are safe.
        """
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            session = con.execute(
                'SELECT room_id,completed FROM escape_sessions WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner)).fetchone()
            if not session or session[1]:
                raise AdventureError('Partie inexistante ou terminée')
            room = next((r for r in content['rooms'] if r['id'] == session[0]), None)
            if room is None:
                raise AdventureError('Salle inconnue')
            hotspot = next((h for h in room.get('hotspots', []) if h['id'] == hotspot_id), None)
            if hotspot is None:
                raise AdventureError('Élément inaccessible dans cette salle')
            solved = {r[0] for r in con.execute(
                'SELECT puzzle_id FROM escape_solved WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner))}
            items = {r[0] for r in con.execute(
                'SELECT item_id FROM escape_items WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                (guild, adventure, mode, owner))}
            if not set(hotspot.get('requires_solved', [])).issubset(solved) or not set(hotspot.get('requires', [])).issubset(items):
                return {'accessible': False, 'reason': 'locked'}
            rewards = hotspot.get('rewards', [])
            newly_found = [item for item in rewards if item not in items]
            for item in newly_found:
                con.execute('INSERT OR IGNORE INTO escape_items VALUES(?,?,?,?,?)',
                            (guild, adventure, mode, owner, item))
            return {'accessible': True, 'description': hotspot.get('description', ''),
                    'new_items': newly_found, 'already_examined': bool(rewards) and not newly_found}

    def scene(self, guild: int, adventure: str, mode: str, owner: int,
              content: dict) -> dict:
        """Resolve a room's evolving narrative without leaking locked stages.

        Stages are derived from persisted puzzle and inventory state, so they
        survive restarts and remain isolated between solo/team sessions.
        Image variants are optional and must be visually audited before use.
        """
        state = self.status(guild, adventure, mode, owner)
        if not state:
            raise AdventureError('Partie inexistante')
        room = next((r for r in content['rooms'] if r['id'] == state['room_id']), None)
        if room is None:
            raise AdventureError('Salle inconnue')
        current = {'id': 'initial', 'description': room.get('description', ''),
                   'image_file': room.get('image_file')}
        for stage in room.get('scene_stages', []):
            if (set(stage.get('requires_solved', [])).issubset(state['solved'])
                    and set(stage.get('requires', [])).issubset(state['items'])):
                current = {'id': stage['id'],
                           'description': stage.get('description', current['description']),
                           'image_file': stage.get('image_file', current['image_file'])}
        return {'room_id': room['id'], **current}

    def narrative_events(self, guild: int, adventure: str, mode: str, owner: int,
                         content: dict) -> dict:
        """Resolve spoiler-safe NOX dialogue and cross-room echoes from saved progress."""
        state = self.status(guild, adventure, mode, owner)
        if not state:
            raise AdventureError('Partie inexistante')
        room = next((r for r in content['rooms'] if r['id'] == state['room_id']), None)
        if room is None:
            raise AdventureError('Salle inconnue')
        solved, items = set(state['solved']), set(state['items'])
        def eligible(event):
            return (set(event.get('requires_solved', [])).issubset(solved)
                    and set(event.get('requires', [])).issubset(items))
        nox = next((event['text'] for event in reversed(room.get('nox_reactions', []))
                    if eligible(event)), None)
        echoes = [{'id': e['id'], 'text': e['text']}
                  for e in room.get('memory_echoes', []) if eligible(e)]
        return {'nox': nox, 'echoes': echoes}

    def answer(self, guild: int, adventure: str, mode: str, owner: int,
               content: dict, puzzle_id: str, response: str) -> dict:
        # Acquire a write reservation before reading progress, preventing two
        # team members from validating the same action on stale state.
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            return self._answer_locked(con, guild, adventure, mode, owner, content, puzzle_id, response)

    def _answer_locked(self, con, guild, adventure, mode, owner, content, puzzle_id, response):
        row = con.execute('SELECT room_id,completed FROM escape_sessions WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                          (guild, adventure, mode, owner)).fetchone()
        status = None
        if row:
            status = {'room_id': row[0], 'completed': bool(row[1]),
                      'items': [r[0] for r in con.execute('SELECT item_id FROM escape_items WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?', (guild, adventure, mode, owner))],
                      'solved': [r[0] for r in con.execute('SELECT puzzle_id FROM escape_solved WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?', (guild, adventure, mode, owner))]}
        if not status or status['completed']:
            raise AdventureError('Partie inexistante ou terminée')
        room = next((r for r in content['rooms'] if r['id'] == status['room_id']), None)
        if room is None:
            raise AdventureError('Salle inconnue')
        puzzle = next((p for p in room['puzzles'] if p['id'] == puzzle_id), None)
        if puzzle is None:
            raise AdventureError('Énigme inaccessible dans cette salle')
        if puzzle_id in status['solved']:
            return {'correct': True, 'already_solved': True, 'next_room': None, 'finished': False}
        if not set(puzzle.get('requires_solved', [])).issubset(status['solved']):
            return {'correct': False, 'reason': 'missing_puzzles'}
        required = set(puzzle.get('requires', []))
        if not required.issubset(status['items']):
            return {'correct': False, 'reason': 'missing_items'}
        if normalize(response) not in {normalize(x) for x in puzzle['answers']}:
            return {'correct': False, 'reason': 'wrong_answer'}
        con.execute('INSERT OR IGNORE INTO escape_solved VALUES(?,?,?,?,?)',
                    (guild, adventure, mode, owner, puzzle_id))
        for item in puzzle.get('rewards', []):
            con.execute('INSERT OR IGNORE INTO escape_items VALUES(?,?,?,?,?)',
                        (guild, adventure, mode, owner, item))
        next_room = puzzle.get('next_room')
        conditional = puzzle.get('conditional_next_room')
        if conditional and set(conditional.get('requires_items', [])).issubset(set(status['items']) | set(puzzle.get('rewards', []))):
            next_room = conditional['room']
        if next_room and not set(puzzle.get('requires_solved', [])).issubset(status['solved']):
            raise AdventureError('Porte non déverrouillée')
        if next_room:
            con.execute('UPDATE escape_sessions SET room_id=?,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=? AND room_id=?',
                        (next_room, guild, adventure, mode, owner, room['id']))
        finished = bool(puzzle.get('finish') or (puzzle.get('finish_if_unqualified') and not next_room))
        if finished:
            con.execute('UPDATE escape_sessions SET completed=1,updated_at=CURRENT_TIMESTAMP WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?',
                        (guild, adventure, mode, owner))
        return {'correct': True, 'next_room': next_room, 'finished': finished}

    def puzzle_access(self, guild: int, adventure: str, mode: str, owner: int,
                      content: dict, puzzle_id: str) -> dict:
        """Validate current-room access before displaying an enigma or hint."""
        state = self.status(guild, adventure, mode, owner)
        if not state or state['completed']:
            raise AdventureError('Partie inexistante ou terminée')
        room = next((r for r in content['rooms'] if r['id'] == state['room_id']), None)
        if room is None:
            raise AdventureError('Salle inconnue')
        puzzle = next((p for p in room['puzzles'] if p['id'] == puzzle_id), None)
        if puzzle is None:
            raise AdventureError('Énigme inaccessible dans cette salle')
        if not set(puzzle.get('requires_solved', [])).issubset(state['solved']):
            return {'accessible': False, 'reason': 'missing_puzzles'}
        if not set(puzzle.get('requires', [])).issubset(state['items']):
            return {'accessible': False, 'reason': 'missing_items'}
        return {'accessible': True, 'puzzle': puzzle}

    def hint_for_current_puzzle(self, guild: int, adventure: str, mode: str,
                                owner: int, content: dict, puzzle_id: str) -> dict:
        access = self.puzzle_access(guild, adventure, mode, owner, content, puzzle_id)
        if not access['accessible']:
            return access
        return {'accessible': True,
                'hint': self.hint(guild, adventure, mode, owner, access['puzzle'])}

    def hint(self, guild: int, adventure: str, mode: str, owner: int,
             puzzle: dict) -> str | None:
        hints = puzzle.get('hints', [])
        if not hints:
            return None
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT level FROM escape_hints WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=? AND puzzle_id=?',
                              (guild, adventure, mode, owner, puzzle['id'])).fetchone()
            level = min(row[0] if row else 0, len(hints) - 1)
            con.execute('INSERT INTO escape_hints VALUES(?,?,?,?,?,?) ON CONFLICT(guild_id,adventure,mode,owner_id,puzzle_id) DO UPDATE SET level=excluded.level',
                        (guild, adventure, mode, owner, puzzle['id'], level + 1))
        return hints[level]

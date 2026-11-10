"""NOX Refuge: pure, persistent state engine (no Discord side effects).

Designed for the HORIZONS V10.85 staged rollout. All actions are server-scoped;
contribution counts never expose chat content. Times use UTC epoch seconds.
"""
from __future__ import annotations
import sqlite3
import time
from pathlib import Path

STATS = ('faim', 'soif', 'bonheur', 'energie', 'hygiene')
DECAY_PER_HOUR = {'faim': 2.5, 'soif': 3.0, 'bonheur': 1.5, 'energie': 1.25, 'hygiene': 1.0}
ACTIONS = {
    'nourrir': ({'faim': 22}, 1800),
    'boire': ({'soif': 25}, 1800),
    'jouer': ({'bonheur': 18, 'energie': -8, 'faim': -4}, 1800),
    'calin': ({'bonheur': 12}, 1800),
    'bain': ({'hygiene': 24, 'bonheur': -3}, 1800),
    'repos': ({'energie': 22, 'bonheur': 3}, 1800),
}


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=15000')
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_refuge_state (
        guild_id INTEGER PRIMARY KEY, faim REAL NOT NULL DEFAULT 80,
        soif REAL NOT NULL DEFAULT 80, bonheur REAL NOT NULL DEFAULT 80,
        energie REAL NOT NULL DEFAULT 80, hygiene REAL NOT NULL DEFAULT 80,
        updated_at REAL NOT NULL, channel_id INTEGER, message_id INTEGER)''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_refuge_contributions (
        guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, action TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0, last_at REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (guild_id, user_id, action))''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_refuge_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, action TEXT NOT NULL, created_at REAL NOT NULL)''')
    con.commit()
    return con


def _clamp(value):
    return max(0.0, min(100.0, float(value)))


def _ensure(con, guild_id, now):
    con.execute('INSERT OR IGNORE INTO nox_refuge_state(guild_id, updated_at) VALUES (?, ?)', (guild_id, now))


def snapshot(con, guild_id, now=None):
    now = time.time() if now is None else float(now)
    with con:
        _ensure(con, guild_id, now)
        row = con.execute('SELECT * FROM nox_refuge_state WHERE guild_id=?', (guild_id,)).fetchone()
        elapsed_hours = max(0, now - row['updated_at']) / 3600
        values = {stat: _clamp(row[stat] - elapsed_hours * DECAY_PER_HOUR[stat]) for stat in STATS}
        if elapsed_hours:
            con.execute('UPDATE nox_refuge_state SET faim=?,soif=?,bonheur=?,energie=?,hygiene=?,updated_at=? WHERE guild_id=?',
                        (*(values[k] for k in STATS), now, guild_id))
    critical = [k for k in STATS if values[k] < 25]
    return {'guild_id': guild_id, 'stats': values, 'needs': critical,
            'mood': 'fatigue' if 'energie' in critical else 'besoin' if critical else 'heureux' if min(values.values()) >= 70 else 'calme',
            'channel_id': row['channel_id'], 'message_id': row['message_id']}


def perform(con, guild_id, user_id, action, now=None):
    if action not in ACTIONS:
        raise ValueError('Action inconnue')
    now = time.time() if now is None else float(now)
    snapshot(con, guild_id, now)
    changes, cooldown = ACTIONS[action]
    with con:
        previous = con.execute('SELECT last_at FROM nox_refuge_contributions WHERE guild_id=? AND user_id=? AND action=?',
                               (guild_id, user_id, action)).fetchone()
        if previous and now - previous['last_at'] < cooldown:
            return {'ok': False, 'remaining_seconds': int(cooldown - (now - previous['last_at']))}
        row = con.execute('SELECT * FROM nox_refuge_state WHERE guild_id=?', (guild_id,)).fetchone()
        values = {k: _clamp(row[k] + changes.get(k, 0)) for k in STATS}
        con.execute('UPDATE nox_refuge_state SET faim=?,soif=?,bonheur=?,energie=?,hygiene=? WHERE guild_id=?',
                    (*(values[k] for k in STATS), guild_id))
        con.execute('''INSERT INTO nox_refuge_contributions(guild_id,user_id,action,count,last_at)
            VALUES (?,?,?,?,?) ON CONFLICT(guild_id,user_id,action)
            DO UPDATE SET count=count+1,last_at=excluded.last_at''', (guild_id,user_id,action,1,now))
        con.execute('INSERT INTO nox_refuge_events(guild_id,user_id,action,created_at) VALUES (?,?,?,?)', (guild_id,user_id,action,now))
    return {'ok': True, 'stats': values}


def contributions(con, guild_id, user_id=None, limit=10):
    if user_id is None:
        return con.execute('''SELECT user_id, SUM(count) total FROM nox_refuge_contributions
            WHERE guild_id=? GROUP BY user_id ORDER BY total DESC, user_id LIMIT ?''', (guild_id,limit)).fetchall()
    return con.execute('SELECT action,count FROM nox_refuge_contributions WHERE guild_id=? AND user_id=? ORDER BY action',
                       (guild_id,user_id)).fetchall()


def set_panel(con, guild_id, channel_id, message_id, now=None):
    now = time.time() if now is None else float(now)
    with con:
        _ensure(con, guild_id, now)
        con.execute('UPDATE nox_refuge_state SET channel_id=?,message_id=? WHERE guild_id=?',
                    (channel_id,message_id,guild_id))


def refuge_link(channel_id, guild_id):
    return f'https://discord.com/channels/{int(guild_id)}/{int(channel_id)}'

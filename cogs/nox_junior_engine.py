"""Persistent, Discord-independent NOX Junior V0.1 foundations."""
from __future__ import annotations
import sqlite3
import time
import math
import random
import secrets
from pathlib import Path

COLORS = ('bleu', 'violet', 'rose', 'rouge', 'orange', 'vert', 'turquoise', 'dore', 'arc_en_ciel')
STAGES = ((0, 0, 0, 'oeuf'), (1, 10, 3, 'nouveau_ne'), (7, 30, 8, 'bebe'), (19, 100, 25, 'adolescent'), (40, 250, 60, 'adulte'))
DECAY_PER_HOUR = {'satiete': 0.75, 'hydratation': 0.95, 'bonheur': 0.45, 'energie': 0.55, 'hygiene': 0.35}
CARE = {'nourrir': ('satiete', 22), 'boire': ('hydratation', 24), 'jouer': ('bonheur', 20), 'calin': ('bonheur', 15), 'laver': ('hygiene', 25), 'repos': ('energie', 25)}

ITEM_CATALOG = (
    ('cristal_lunaire','materiau','Cristal lunaire',1,1),
    ('poussiere_etoiles','materiau','Poussière d’étoiles',1,1),
    ('bois_astral','materiau','Bois astral',1,1),
    ('balle_lunaire','jouet','Balle lunaire',1,0),
    ('peluche_comete','jouet','Peluche comète',1,0),
    ('coussin_etoile','decoration','Coussin étoilé',1,0),
    ('veilleuse','decoration','Veilleuse des étoiles',1,0),
    ('tapis_lunaire','decoration','Tapis lunaire',1,0),
    ('lanterne_astrale','decoration','Lanterne astrale',1,0),
    ('plante_stellaire','decoration','Plante stellaire',1,0),
    ('globe_cosmique','decoration','Globe cosmique',1,0),
    ('peluche_nebuleuse','decoration','Peluche nébuleuse',1,0),
    ('guirlande_lumineuse','decoration','Guirlande lumineuse',1,0),
    ('coffre_cristal','decoration','Coffre de cristal',1,0),
    ('mobile_etoiles','decoration','Mobile d’étoiles',1,0),
    ('oreiller_douillet','decoration','Oreiller douillet',0,0),
    ('plante_lumineuse','decoration','Plante lumineuse',0,0),
    ('lampe_lunaire','decoration','Lampe lunaire',0,0),
    ('cristal_galactique','decoration','Cristal galactique',0,0),
    ('peluche_mini_nox','decoration','Peluche miniature NOX',0,0),
    ('coffre_tresors','decoration','Coffre aux trésors',0,0),
    ('tapis_constellations','decoration','Tapis des constellations',0,0),
    ('fontaine_magique','decoration','Fontaine magique',0,0),
    ('souvenir_eclosion','souvenir','Premier éveil',0,0),
)
RECIPES = {'veilleuse': {'cristal_lunaire':3,'poussiere_etoiles':10}}
# Boutique virtuelle : aucune transaction monétaire réelle.
SHOP = {
 'coussin_etoile': ('Coussin étoilé',40,'couchage'),
 'plante_lumineuse': ('Plante lumineuse',55,'sol_gauche'),
 'lampe_lunaire': ('Lampe lunaire',70,'meuble_gauche'),
 'cristal_galactique': ('Cristal galactique',90,'sol_droit'),
 'peluche_mini_nox': ('Peluche miniature NOX',110,'meuble_droit'),
 'globe_cosmique': ('Globe cosmique',130,'fond_gauche'),
 'coffre_tresors': ('Coffre aux trésors',150,'fond_droit'),
 'tapis_constellations': ('Tapis céleste',170,'sol_centre'),
 'mobile_etoiles': ('Mobile des étoiles',190,'plafond'),
 'fontaine_magique': ('Arc-en-ciel enchanté',220,'coin_droit'),
}
DECOR_SLOTS = {'oreiller_douillet':'couchage', **{code:data[2] for code,data in SHOP.items()}}
SLOT_POSITIONS = {'couchage':(.50,.81),'sol_gauche':(.16,.82),'meuble_gauche':(.18,.55),
 'sol_droit':(.84,.82),'meuble_droit':(.82,.55),'fond_gauche':(.12,.36),
 'fond_droit':(.88,.36),'sol_centre':(.50,.88),'plafond':(.50,.18),'coin_droit':(.91,.73)}
# Passive room effects, expressed as percentage change to hourly decay.
# Negative values protect a gauge, positive values increase its decay.
# Effects apply only while an owned decoration is equipped; no real-world purchases.
DECOR_EFFECTS = {
    'oreiller_douillet': {},
    'coussin_etoile': {'energie': -0.15},
    'plante_lumineuse': {'bonheur': -0.08},
    'lampe_lunaire': {'energie': -0.06, 'bonheur': -0.03},
    'cristal_galactique': {'bonheur': -0.07, 'energie': 0.04},
    'peluche_mini_nox': {'bonheur': -0.14},
    'globe_cosmique': {'bonheur': -0.05},
    'coffre_tresors': {'bonheur': -0.04},
    'tapis_constellations': {'energie': -0.04},
    'mobile_etoiles': {'energie': -0.08},
    'fontaine_magique': {'bonheur': -0.07, 'energie': -0.03},
    # Additional approved visual assets, enabled once added to the shop catalog.
    'tapis_celeste': {'energie': -0.04},
    'arc_en_ciel_enchante': {'bonheur': -0.08},
}
MAX_DECAY_REDUCTION = 0.35
MAX_DECAY_INCREASE = 0.15


def room_effects(con, pet_id):
    """Return effective decay modifiers for currently equipped, owned objects."""
    equipped = con.execute('''SELECT s.slot, s.code FROM junior_room_slots AS s
        JOIN junior_inventory AS i ON i.pet_id=s.pet_id AND i.code=s.code
        WHERE s.pet_id=? AND i.quantity>0''', (pet_id,)).fetchall()
    totals = {stat: 0.0 for stat in DECAY_PER_HOUR}
    for item in equipped:
        if DECOR_SLOTS.get(item['code']) != item['slot']:
            continue
        for stat, value in DECOR_EFFECTS.get(item['code'], {}).items():
            totals[stat] += value
    return {stat: max(-MAX_DECAY_REDUCTION, min(MAX_DECAY_INCREASE, value))
            for stat, value in totals.items()}


def room_ambience(con, pet_id):
    """Descriptive mood, derived from equipped objects without adding fragile DB columns."""
    equipped = {r['code'] for r in con.execute(
        'SELECT s.code FROM junior_room_slots s JOIN junior_inventory i '
        'ON i.pet_id=s.pet_id AND i.code=s.code WHERE s.pet_id=? AND i.quantity>0', (pet_id,))}
    if 'cristal_galactique' in equipped:
        return 'stimulé', '💎 Le cristal éveille la curiosité de NOX.'
    if 'lampe_lunaire' in equipped or 'mobile_etoiles' in equipped:
        return 'apaisé', '🌙 La chambre aide NOX à se détendre.'
    if 'peluche_mini_nox' in equipped or 'plante_lumineuse' in equipped:
        return 'joyeux', '💜 NOX apprécie son environnement.'
    return 'neutre', '✨ NOX découvre sa chambre.'

DAILY_GAME_REWARD_LIMIT = 5

ROOM_THEMES = ('sanctuaire_etoiles','palais_nuages','jardin_lucioles','palais_celeste','observatoire_lunaire','jardin_cristallin')
ROOM_LABELS = ('Sanctuaire des étoiles','Palais des nuages','Jardin des lucioles','Palais céleste','Observatoire lunaire','Jardin cristallin')

class JuniorError(ValueError):
    pass


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=15000')
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS junior_walk_memories (pet_id INTEGER NOT NULL, region TEXT NOT NULL, souvenir TEXT NOT NULL, visits INTEGER NOT NULL DEFAULT 1, last_seen REAL NOT NULL, PRIMARY KEY(pet_id,region,souvenir));
    CREATE TABLE IF NOT EXISTS junior_pets (
      id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
      slot INTEGER NOT NULL CHECK(slot IN (1,2)), name TEXT NOT NULL, color TEXT NOT NULL,
      created_at REAL NOT NULL, renamed INTEGER NOT NULL DEFAULT 0 CHECK(renamed IN (0,1)),
      bond INTEGER NOT NULL DEFAULT 0, activities INTEGER NOT NULL DEFAULT 0,
      satiete REAL NOT NULL DEFAULT 80, hydratation REAL NOT NULL DEFAULT 80,
      bonheur REAL NOT NULL DEFAULT 80, energie REAL NOT NULL DEFAULT 80,
      hygiene REAL NOT NULL DEFAULT 80, last_care REAL NOT NULL DEFAULT 0,
      updated_at REAL NOT NULL, UNIQUE(guild_id,owner_id,slot));
    CREATE TABLE IF NOT EXISTS junior_grants (
      guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL, granted_by INTEGER NOT NULL,
      created_at REAL NOT NULL, PRIMARY KEY(guild_id,owner_id));
    CREATE TABLE IF NOT EXISTS junior_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, pet_id INTEGER NOT NULL REFERENCES junior_pets(id),
      event TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS junior_events_pet ON junior_events(pet_id,created_at);
    ''')
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_game_sessions (
      token TEXT PRIMARY KEY, pet_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
      owner_id INTEGER NOT NULL, game TEXT NOT NULL, question TEXT NOT NULL,
      answer TEXT NOT NULL, choices TEXT NOT NULL, created_at REAL NOT NULL,
      completed_at REAL, selected TEXT);
    CREATE TABLE IF NOT EXISTS junior_affinities (
      pet_id INTEGER PRIMARY KEY, exploration INTEGER NOT NULL DEFAULT 0,
      invention INTEGER NOT NULL DEFAULT 0, reve INTEGER NOT NULL DEFAULT 0,
      protection INTEGER NOT NULL DEFAULT 0, art INTEGER NOT NULL DEFAULT 0,
      farce INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX IF NOT EXISTS junior_game_owner ON junior_game_sessions(owner_id,created_at);
    """)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_expeditions (
      token TEXT PRIMARY KEY, pet_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
      guild_id INTEGER NOT NULL, region TEXT NOT NULL, step INTEGER NOT NULL DEFAULT 0,
      choices_json TEXT NOT NULL, story_json TEXT NOT NULL, created_at REAL NOT NULL,
      completed_at REAL, outcome TEXT);
    CREATE INDEX IF NOT EXISTS junior_expeditions_pet ON junior_expeditions(pet_id,created_at);
    CREATE TABLE IF NOT EXISTS junior_discoveries (
      pet_id INTEGER NOT NULL, region TEXT NOT NULL, discovery TEXT NOT NULL,
      discovered_at REAL NOT NULL, PRIMARY KEY(pet_id,region,discovery));
    """)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_personal_notes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      pet_id INTEGER NOT NULL REFERENCES junior_pets(id),
      guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL,
      title TEXT NOT NULL, body TEXT NOT NULL,
      created_at REAL NOT NULL, updated_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS junior_notes_pet ON junior_personal_notes(pet_id,id DESC);
    """)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_items (
      code TEXT PRIMARY KEY, category TEXT NOT NULL, label TEXT NOT NULL,
      giftable INTEGER NOT NULL CHECK(giftable IN (0,1)), stackable INTEGER NOT NULL CHECK(stackable IN (0,1)));
    CREATE TABLE IF NOT EXISTS junior_inventory (
      pet_id INTEGER NOT NULL REFERENCES junior_pets(id), code TEXT NOT NULL REFERENCES junior_items(code),
      quantity INTEGER NOT NULL CHECK(quantity >= 0), PRIMARY KEY(pet_id,code));
    CREATE TABLE IF NOT EXISTS junior_rooms (
      pet_id INTEGER PRIMARY KEY REFERENCES junior_pets(id), theme TEXT NOT NULL DEFAULT 'cosmos',
      decoration TEXT NOT NULL DEFAULT 'none');
    CREATE TABLE IF NOT EXISTS junior_gifts (
      id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
      sender_pet INTEGER NOT NULL REFERENCES junior_pets(id), recipient_pet INTEGER NOT NULL REFERENCES junior_pets(id),
      code TEXT NOT NULL REFERENCES junior_items(code), quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 50),
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','accepted','declined','expired')),
      created_at REAL NOT NULL, resolved_at REAL);
    CREATE INDEX IF NOT EXISTS junior_gifts_recipient ON junior_gifts(recipient_pet,status);
    """)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_encounters (
      id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
      inviter_pet INTEGER NOT NULL REFERENCES junior_pets(id),
      invited_pet INTEGER NOT NULL REFERENCES junior_pets(id),
      game TEXT NOT NULL CHECK(game IN ('duo','tresor','festival')),
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','completed','declined','expired')),
      created_at REAL NOT NULL, accepted_at REAL, completed_at REAL,
      inviter_choice INTEGER, invited_choice INTEGER,
      CHECK(inviter_pet != invited_pet));
    CREATE INDEX IF NOT EXISTS junior_encounters_inviter ON junior_encounters(inviter_pet,status);
    CREATE INDEX IF NOT EXISTS junior_encounters_invited ON junior_encounters(invited_pet,status);
    """)
    # V0.9: rounds are durable and can be resumed after a restart.
    con.executescript("""
    CREATE TABLE IF NOT EXISTS junior_encounter_rounds (
      encounter_id INTEGER NOT NULL REFERENCES junior_encounters(id),
      round_number INTEGER NOT NULL CHECK(round_number BETWEEN 1 AND 3),
      inviter_choice INTEGER, invited_choice INTEGER,
      PRIMARY KEY(encounter_id,round_number));
    """)
    con.executemany('INSERT OR IGNORE INTO junior_items(code,category,label,giftable,stackable) VALUES(?,?,?,?,?)', ITEM_CATALOG)
    # Idempotent migration for installations created with V0.1.
    columns = {r['name'] for r in con.execute('PRAGMA table_info(junior_pets)')}
    if 'last_decay' not in columns:
        con.execute('ALTER TABLE junior_pets ADD COLUMN last_decay REAL NOT NULL DEFAULT 0')
        con.execute('UPDATE junior_pets SET last_decay=updated_at WHERE last_decay=0')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS junior_star_wallet (
      pet_id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 0 CHECK(balance>=0),
      care_progress INTEGER NOT NULL DEFAULT 0 CHECK(care_progress>=0));
    CREATE TABLE IF NOT EXISTS junior_room_slots (
      pet_id INTEGER NOT NULL, slot TEXT NOT NULL, code TEXT NOT NULL,
      PRIMARY KEY(pet_id,slot));
    CREATE TABLE IF NOT EXISTS junior_shop_purchases (
      pet_id INTEGER NOT NULL, code TEXT NOT NULL, price INTEGER NOT NULL,
      purchased_at REAL NOT NULL, PRIMARY KEY(pet_id,code));
    CREATE TABLE IF NOT EXISTS junior_daily_care (
      pet_id INTEGER NOT NULL, care_date TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(pet_id,care_date));
    CREATE TABLE IF NOT EXISTS junior_activity_windows (
      pet_id INTEGER PRIMARY KEY, started_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS junior_star_rewards (
      session_token TEXT PRIMARY KEY, pet_id INTEGER NOT NULL,
      reward_date TEXT NOT NULL, amount INTEGER NOT NULL);
    ''')
    con.executemany('UPDATE junior_items SET label=?, giftable=0,stackable=0 WHERE code=?',
                    [(data[0],code) for code,data in SHOP.items()])
    return con


def validate_name(name):
    name = ' '.join(name.split())
    if not 2 <= len(name) <= 24 or any(ord(c) < 32 for c in name) or '@' in name or '<' in name or '>' in name or '`' in name:
        raise JuniorError('Le nom doit contenir 2 à 24 caractères, sans mention ni balise Discord.')
    return name


def care_count(refuge_con, guild_id, user_id):
    row = refuge_con.execute('SELECT COALESCE(SUM(count),0) FROM nox_refuge_contributions WHERE guild_id=? AND user_id=?', (guild_id,user_id)).fetchone()
    return int(row[0])


def pets(con, guild_id, owner_id):
    return con.execute('SELECT * FROM junior_pets WHERE guild_id=? AND owner_id=? ORDER BY slot', (guild_id,owner_id)).fetchall()


def adopt(con, guild_id, owner_id, name, color, eligible, now=None):
    name = validate_name(name)
    color = color.lower().strip()
    if color not in COLORS:
        raise JuniorError('Couleur inconnue.')
    if not eligible:
        raise JuniorError('Adoption non autorisée : rôle Lien vivant et 10 soins requis.')
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        rows = con.execute('SELECT slot FROM junior_pets WHERE guild_id=? AND owner_id=?', (guild_id,owner_id)).fetchall()
        used = {r['slot'] for r in rows}
        grant = con.execute('SELECT 1 FROM junior_grants WHERE guild_id=? AND owner_id=?', (guild_id,owner_id)).fetchone()
        slot = next((s for s in range(1, 3 if grant else 2) if s not in used), None)
        if slot is None:
            raise JuniorError('Nombre maximum de compagnons atteint.')
        cur = con.execute('INSERT INTO junior_pets(guild_id,owner_id,slot,name,color,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (guild_id,owner_id,slot,name,color,now,now))
        con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES (?,?,?)', (cur.lastrowid,'adoption',now))
        con.commit()
        return cur.lastrowid
    except BaseException:
        con.rollback()
        raise


def grant_second(con, guild_id, owner_id, founder_id, now=None):
    now = time.time() if now is None else float(now)
    with con:
        con.execute('INSERT OR IGNORE INTO junior_grants(guild_id,owner_id,granted_by,created_at) VALUES (?,?,?,?)', (guild_id,owner_id,founder_id,now))
    return True


def rename(con, pet_id, owner_id, new_name):
    name = validate_name(new_name)
    with con:
        cur = con.execute('UPDATE junior_pets SET name=?,renamed=1 WHERE id=? AND owner_id=? AND renamed=0', (name,pet_id,owner_id))
        if cur.rowcount != 1:
            raise JuniorError('Renommage déjà utilisé ou compagnon introuvable.')
        con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES (?,?,?)', (pet_id,'renommage',time.time()))


def stage(pet, now=None):
    now = time.time() if now is None else float(now)
    days = max(0, int((now-pet['created_at'])//86400))
    result = 'oeuf'
    for min_days, min_bond, min_activities, label in STAGES:
        if days >= min_days and pet['bond'] >= min_bond and pet['activities'] >= min_activities:
            result = label
    return result, days


def mood(pet):
    values = {key: float(pet[key]) for key in DECAY_PER_HOUR}
    if values['energie'] < 30:
        return 'endormi', '💤 Ton compagnon a besoin de repos.'
    if min(values.values()) < 35:
        return 'besoin', '🥺 Ton compagnon a besoin de ton attention.'
    if values['bonheur'] >= 80 and min(values.values()) >= 60:
        return 'heureux', '✨ Ton compagnon rayonne de bonheur !'
    return 'calme', '💙 Ton compagnon profite de ce moment avec toi.'


def snapshot(con, pet_id, owner_id, guild_id=None, now=None):
    """Apply capped, lazy decay once; offline time never destroys a companion."""
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        query = 'SELECT * FROM junior_pets WHERE id=? AND owner_id=?'
        params = [pet_id, owner_id]
        if guild_id is not None:
            query += ' AND guild_id=?'
            params.append(guild_id)
        row = con.execute(query, params).fetchone()
        if row is None:
            raise JuniorError('Compagnon introuvable.')
        elapsed = max(0.0, min(now - (row['last_decay'] or row['created_at']), 72 * 3600)) / 3600
        # Cap to 72 hours; gauges have a floor so absence is not punished indefinitely.
        modifiers = room_effects(con, pet_id) if stage(row, now)[0] != 'oeuf' else {stat: 0.0 for stat in DECAY_PER_HOUR}
        updated = {stat: max(30.0, round(float(row[stat]) - elapsed * rate * (1.0 + modifiers[stat]), 2)) for stat, rate in DECAY_PER_HOUR.items()}
        con.execute('UPDATE junior_pets SET satiete=?, hydratation=?, bonheur=?, energie=?, hygiene=?, last_decay=? WHERE id=?', (*[updated[k] for k in DECAY_PER_HOUR], now, pet_id))
        con.commit()
        return con.execute('SELECT * FROM junior_pets WHERE id=?', (pet_id,)).fetchone()
    except BaseException:
        con.rollback()
        raise


def journal(con, pet_id, owner_id, guild_id, limit=8):
    pet = con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?', (pet_id, owner_id, guild_id)).fetchone()
    if not pet:
        raise JuniorError('Compagnon introuvable.')
    return con.execute('SELECT event,created_at FROM junior_events WHERE pet_id=? ORDER BY id DESC LIMIT ?', (pet_id, max(1,min(20,int(limit))))).fetchall()


def activity_rest_remaining(con, pet_id, now):
    """45 active minutes followed by 15 quiet minutes, per companion.

    Only care/game actions are gated. Reading the profile, visiting the room,
    browsing the shop and journal remain available throughout the quiet period.
    The window starts on the first action rather than at a wall-clock hour.
    """
    row = con.execute('SELECT started_at FROM junior_activity_windows WHERE pet_id=?', (pet_id,)).fetchone()
    if row is None:
        con.execute('INSERT INTO junior_activity_windows(pet_id,started_at) VALUES (?,?)', (pet_id,now))
        return 0
    elapsed = max(0.0, now-float(row['started_at']))
    if elapsed >= 3600:
        con.execute('UPDATE junior_activity_windows SET started_at=? WHERE pet_id=?', (now,pet_id))
        return 0
    return int(max(0, 3600-elapsed)) if elapsed >= 2700 else 0


def care(con, pet_id, owner_id, action, now=None, guild_id=None):
    if action not in CARE:
        raise JuniorError('Soin inconnu.')
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        pet = con.execute('SELECT * FROM junior_pets WHERE id=? AND owner_id=?' + (' AND guild_id=?' if guild_id is not None else ''), (pet_id,owner_id) + ((guild_id,) if guild_id is not None else ())).fetchone()
        if pet is None:
            raise JuniorError('Compagnon introuvable.')
        rest_remaining = activity_rest_remaining(con, pet_id, now)
        remaining = rest_remaining or (max(0, 20-(now-pet['last_care'])) if pet['last_care'] else 0)
        if remaining > 0:
            con.rollback()
            return int(remaining)
        from datetime import datetime, timezone
        care_day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        care_today = con.execute('SELECT count FROM junior_daily_care WHERE pet_id=? AND care_date=?', (pet_id,care_day)).fetchone()
        completed = int(care_today['count']) if care_today else 0
        if completed >= 40:
            raise JuniorError('🛏️ Les 40 soins quotidiens sont atteints. Tu peux toujours consulter NOX et sa chambre.')
        stat, value = CARE[action]
        con.execute(f'UPDATE junior_pets SET {stat}=MIN(100,{stat}+?), bond=bond+2, activities=activities+1, last_care=?,updated_at=? WHERE id=?', (value,now,now,pet_id))
        con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES (?,?,?)', (pet_id,'soin:'+action,now))
        con.execute('INSERT OR IGNORE INTO junior_star_wallet(pet_id) VALUES(?)',(pet_id,))
        con.execute('INSERT INTO junior_daily_care(pet_id,care_date,count) VALUES(?,?,1) ON CONFLICT(pet_id,care_date) DO UPDATE SET count=count+1', (pet_id,care_day))
        # Only care #10 and #20 of each UTC day yield a star dust; #21-40 remain effective.
        reward = 1 if completed + 1 in (10,20) else 0
        con.execute('UPDATE junior_star_wallet SET balance=balance+?,care_progress=? WHERE pet_id=?', (reward, 0 if completed+1>=20 else (completed+1)%10, pet_id))
        con.commit()
        return 0
    except BaseException:
        con.rollback()
        raise


GAME_COOLDOWN = 10  # Anti-spam only; mini-games remain replayable without daily cap.
GAMES = ('etoiles', 'memoire', 'choix', 'cristaux', 'enigmes', 'constellations', 'parcours', 'cometes', 'sauvetage', 'cache_cache', 'cuisine', 'danse')
AFFINITY_LABELS = {'exploration':'Explorateur','invention':'Inventeur','reve':'Rêveur',
                   'protection':'Protecteur','art':'Artiste','farce':'Farceur'}


def game_start(con, pet_id, owner_id, guild_id, game, now=None, rng=None):
    """Create one persistent game session. No reward is granted before completion."""
    import json
    if game not in GAMES:
        raise JuniorError('Mini-jeu inconnu.')
    now = time.time() if now is None else float(now)
    rng = rng or random.SystemRandom()
    con.execute('BEGIN IMMEDIATE')
    try:
        pet = con.execute('SELECT * FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?', (pet_id,owner_id,guild_id)).fetchone()
        if pet is None:
            raise JuniorError('Compagnon introuvable.')
        rest_remaining = activity_rest_remaining(con, pet_id, now)
        if rest_remaining:
            raise JuniorError(f'💤 NOX se repose pendant encore {math.ceil(rest_remaining/60)} minute(s). Tu peux toujours consulter sa chambre et son journal.')
        last = con.execute('SELECT completed_at FROM junior_game_sessions WHERE pet_id=? AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1',(pet_id,)).fetchone()
        if last and now - last['completed_at'] < GAME_COOLDOWN:
            raise JuniorError(f'🎮 Nouvelle partie dans {max(1, math.ceil((GAME_COOLDOWN-(now-last["completed_at"]))/60))} minute(s).')
        pending = con.execute('SELECT token FROM junior_game_sessions WHERE pet_id=? AND completed_at IS NULL AND created_at>? ORDER BY created_at DESC LIMIT 1',(pet_id,now-300)).fetchone()
        if pending:
            raise JuniorError('Une partie est déjà en cours. Termine-la ou attends cinq minutes.')
        if game == 'etoiles':
            answer = str(rng.randrange(1,5))
            choices = ['⭐ Étoile '+str(i) for i in range(1,5)]
            question = 'Une étoile cache un cristal ! Choisis la bonne étoile.'
        elif game == 'memoire':
            symbols = ['🌙','⭐','💎','☄️']
            answer = str(rng.randrange(4))
            choices = [f'{symbols[i]} {i+1}' for i in range(4)]
            question = f'Nova te montre ce symbole : **{symbols[int(answer)]}**. Retrouve-le parmi les choix !'
        elif game == 'cristaux':
            colors = ['🔴 Rouge', '🔵 Bleu', '🟢 Vert', '🟣 Violet']
            answer = str(rng.randrange(4))
            choices = colors
            question = f'Le cristal-guide brille en **{colors[int(answer)]}**. Quel cristal choisir ?'
        elif game == 'enigmes':
            puzzles = [('Je brille la nuit sans être une lampe. Qui suis-je ?', 'La lune', ['Le soleil','Une pierre','La lune','Un nuage']), ('Je traverse le ciel avec une longue traîne lumineuse. Qui suis-je ?', 'Une comète', ['Une comète','Un arbre','Un livre','Une rivière'])]
            question, right, choices = rng.choice(puzzles)
            answer = str(choices.index(right))
        elif game == 'parcours':
            situations = [
                ('Une pluie de météores traverse le parcours. Que faire ?', ['Sauter vers la plateforme sûre', 'Courir au hasard', 'Rester sous les météores'], 0),
                ('Une passerelle est couverte de brume. Que faire ?', ['Foncer sans regarder', 'Avancer doucement en suivant les balises', 'Fermer les yeux'], 1),
                ('Un obstacle tourne devant NOX. Quelle stratégie ?', ['Attendre une ouverture', 'Se jeter dessus', 'Reculer sans observer'], 0),
            ]
            question, choices, correct = rng.choice(situations)
            answer = str(correct)
        elif game == 'cometes':
            situations = [
                ('Une comète accélère dans un virage. Que faire ?', ['Accélérer encore', 'Ralentir et négocier le virage', 'Quitter la piste'], 1),
                ('Un raccourci instable apparaît. Que faire ?', ['Choisir la trajectoire balisée', 'Sauter sans vérifier', 'Ignorer les étoiles de guidage'], 0),
                ('Une rafale stellaire arrive. Que faire ?', ['Rester au centre du courant', 'Se placer derrière un bouclier rocheux', 'Accélérer droit dans la rafale'], 1),
            ]
            question, choices, correct = rng.choice(situations)
            answer = str(correct)
        elif game == 'sauvetage':
            situations = [
                ('Une luciole est perdue près du lac. Comment l’aider ?', ['Lui crier dessus', 'Suivre doucement ses traces lumineuses', 'Partir sans elle'], 1),
                ('Un petit astronaute est coincé sur une branche. Que faire ?', ['Construire un appui stable', 'Secouer l’arbre', 'Lancer un caillou'], 0),
                ('Un bébé comète cherche son chemin. Comment réagir ?', ['Écouter son histoire et regarder la carte', 'Courir au hasard', 'Le laisser seul'], 0),
            ]
            question, choices, correct = rng.choice(situations)
            answer = str(correct)
        elif game == 'cache_cache':
            hiding_places = [
                ('derrière une météorite', '🪨 Météorite'),
                ('dans une nébuleuse', '☁️ Nébuleuse'),
                ('près du grand cristal', '💎 Cristal'),
                ('sous une étoile filante', '🌠 Étoile filante'),
            ]
            correct = rng.randrange(len(hiding_places))
            question = (f'🙈 Cache-cache cosmique ! NOX laisse une trace lumineuse '
                        f'{hiding_places[correct][0]}. Où le retrouver ?')
            choices = [place[1] for place in hiding_places]
            answer = str(correct)
        elif game == 'cuisine':
            recipes = [
                ('une soupe de lune bien chaude', ['🌙 Lait de lune', '🪨 Cailloux', '⚡ Éclairs'], 0),
                ('un gâteau aux étoiles', ['🌊 Eau salée', '⭐ Poudre étoilée', '🌵 Épines'], 1),
                ('un smoothie de comète', ['🧊 Glace cosmique', '🔥 Braises', '🪵 Bois',], 0),
                ('des biscuits arc-en-ciel', ['☁️ Brouillard', '🎨 Sucre multicolore', '🧲 Aimants'], 1),
            ]
            dish, choices, correct = rng.choice(recipes)
            question = f'🧁 Cuisine des étoiles ! NOX prépare {dish}. Quel ingrédient choisir ?'
            answer = str(correct)
        elif game == 'danse':
            rhythms = [
                ('⭐ ⭐ 🌙 ⭐ ⭐ ?', ['⭐ Étoile', '🌙 Lune', '☄️ Comète'], 1),
                ('💜 💙 💜 💙 ?', ['💜 Violet', '💙 Bleu', '💚 Vert'], 0),
                ('👏 👏 🦶 👏 👏 ?', ['👏 Frapper des mains', '🦶 Taper du pied', '💤 Dormir'], 1),
                ('🌈 🌟 🌈 🌟 ?', ['🌟 Briller', '🌈 Tourner', '🪨 S’arrêter'], 1),
            ]
            pattern, choices, correct = rng.choice(rhythms)
            question = f'💃 Danse des constellations ! Complète le rythme de NOX : **{pattern}**'
            answer = str(correct)
        elif game == 'constellations':
            patterns = [('⭐🌙⭐','⭐🌙⭐',['🌙⭐🌙','⭐⭐🌙','⭐🌙⭐','🌙🌙⭐']), ('💎⭐💎','💎⭐💎',['⭐💎⭐','💎⭐💎','💎💎⭐','⭐⭐💎'])]
            question, right, choices = rng.choice(patterns)
            question = f'Retrouve la constellation **{question}**.'
            answer = str(choices.index(right))
        else:
            answer = '1'
            choices = ['Traverser sans regarder', 'Observer les alentours', 'Abandonner immédiatement']
            question = 'Un passage mystérieux apparaît. Que devrait faire ton NOX ?'
        token = secrets.token_urlsafe(18)
        con.execute('INSERT INTO junior_game_sessions(token,pet_id,guild_id,owner_id,game,question,answer,choices,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (token,pet_id,guild_id,owner_id,game,question,answer,json.dumps(choices,ensure_ascii=False),now))
        con.commit()
        return {'token':token,'question':question,'choices':choices,'game':game}
    except BaseException:
        con.rollback()
        raise


def game_finish(con, token, pet_id, owner_id, guild_id, choice, now=None):
    """Idempotent reward transaction; no repeated click can duplicate points."""
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        row = con.execute('SELECT * FROM junior_game_sessions WHERE token=? AND pet_id=? AND owner_id=? AND guild_id=?', (token,pet_id,owner_id,guild_id)).fetchone()
        if row is None:
            raise JuniorError('Partie introuvable.')
        if row['completed_at'] is not None:
            raise JuniorError('Cette partie est déjà terminée.')
        if now - row['created_at'] > 300:
            raise JuniorError('Partie expirée. Relance un mini-jeu.')
        import json
        options = json.loads(row['choices'])
        if not str(choice).isdigit() or not 0 <= int(choice) < len(options):
            raise JuniorError('Réponse invalide.')
        success = str(choice) == row['answer']
        bond = 4 if success else 1
        con.execute('UPDATE junior_game_sessions SET completed_at=?,selected=? WHERE token=? AND completed_at IS NULL', (now,str(choice),token))
        con.execute('UPDATE junior_pets SET bond=bond+?, activities=activities+1, bonheur=MIN(100,bonheur+?),updated_at=? WHERE id=?', (bond, 8 if success else 2, now,pet_id))
        affinity = {'etoiles':'exploration','memoire':'reve','choix':'protection','cristaux':'invention','enigmes':'art','constellations':'reve','parcours':'exploration','cometes':'exploration','sauvetage':'protection','cache_cache':'exploration','cuisine':'invention','danse':'art'}[row['game']]
        con.execute('INSERT OR IGNORE INTO junior_affinities(pet_id) VALUES(?)',(pet_id,))
        con.execute(f'UPDATE junior_affinities SET {affinity}={affinity}+? WHERE pet_id=?',(3 if success else 1,pet_id))
        con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES(?,?,?)',(pet_id,'jeu:'+row['game'],now))
        from datetime import datetime, timezone
        day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
        rewarded = con.execute('SELECT COUNT(*) FROM junior_star_rewards WHERE pet_id=? AND reward_date=?', (pet_id,day)).fetchone()[0]
        if rewarded < 5:
            con.execute('INSERT INTO junior_star_rewards(session_token,pet_id,reward_date,amount) VALUES (?,?,?,2)',(token,pet_id,day))
            con.execute('INSERT OR IGNORE INTO junior_star_wallet(pet_id) VALUES (?)',(pet_id,))
            con.execute('UPDATE junior_star_wallet SET balance=balance+2 WHERE pet_id=?',(pet_id,))
        con.commit()
        return success,bond
    except BaseException:
        con.rollback()
        raise


def affinities(con, pet_id, owner_id, guild_id):
    if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',(pet_id,owner_id,guild_id)).fetchone():
        raise JuniorError('Compagnon introuvable.')
    row = con.execute('SELECT * FROM junior_affinities WHERE pet_id=?',(pet_id,)).fetchone()
    return {key:int(row[key]) if row else 0 for key in AFFINITY_LABELS}


# NOX Junior V0.4 — Expéditions à deux décisions, persistance et découverte unique.
REGIONS = {
    'foret': ('🌲 Forêt astrale', (
        ('Une luciole ouvre trois chemins. Où aller ?', ('Suivre les lucioles', 'Explorer le ruisseau', 'Observer les arbres')),
        ('Un éclat apparaît dans les feuilles. Que faire ?', ('Le ramasser doucement', 'Examiner sa lumière', 'Laisser une offrande'))),
        ('Feuille d’étoile', 'Goutte de lune', 'Lueur sylvestre')),
    'iles': ('☁️ Îles des nuages', (
        ('Trois ponts flottent devant NOX. Lequel choisir ?', ('Pont de brume', 'Pont arc-en-ciel', 'Pont des vents')),
        ('Un nuage chante doucement. Comment répondre ?', ('Chanter avec lui', 'Écouter en silence', 'Danser'))),
        ('Plume de nuage', 'Perle de brume', 'Écho céleste')),
    'grotte': ('💎 Grotte des cristaux', (
        ('Trois reflets éclairent la grotte. Où avancer ?', ('Galerie bleue', 'Galerie violette', 'Galerie dorée')),
        ('Un cristal vibre. Comment réagir ?', ('Le toucher doucement', 'Observer ses facettes', 'Écouter sa vibration'))),
        ('Éclat de cristal', 'Prisme ancien', 'Chant minéral')),
    'vallee': ('🌙 Vallée des rêves', (
        ('Une porte apparaît dans un rêve. Que faire ?', ('Entrer doucement', 'Lire les symboles', 'Suivre les papillons')),
        ('Un souvenir flotte dans les airs. Comment le découvrir ?', ('L’écouter', 'Le dessiner', 'Lui sourire'))),
        ('Fragment de rêve', 'Ruban nocturne', 'Souvenir lumineux')),
    'observatoire': ('🔭 Observatoire des étoiles', (
        ('Une constellation inconnue scintille. Que regarder ?', ('La grande étoile', 'La petite étoile', 'La traînée lumineuse')),
        ('Un télescope révèle une surprise. Comment réagir ?', ('Prendre des notes', 'Faire un vœu', 'Partager la découverte'))),
        ('Carte céleste', 'Poussière cosmique', 'Secret des astres')),
}
EXPLORATION_COOLDOWN = 900


def exploration_start(con, pet_id, owner_id, guild_id, region, now=None, rng=None):
    import json
    if region not in REGIONS:
        raise JuniorError('Région inconnue.')
    now = time.time() if now is None else float(now)
    rng = rng or random.SystemRandom()
    con.execute('BEGIN IMMEDIATE')
    try:
        pet = con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?', (pet_id,owner_id,guild_id)).fetchone()
        if pet is None:
            raise JuniorError('Compagnon introuvable.')
        pending = con.execute('SELECT 1 FROM junior_expeditions WHERE pet_id=? AND completed_at IS NULL AND created_at>?', (pet_id,now-600)).fetchone()
        if pending:
            raise JuniorError('Une expédition est déjà en cours. Attends sa fin ou dix minutes.')
        last = con.execute('SELECT completed_at FROM junior_expeditions WHERE pet_id=? AND completed_at IS NOT NULL ORDER BY completed_at DESC LIMIT 1', (pet_id,)).fetchone()
        if last and now-last['completed_at'] < EXPLORATION_COOLDOWN:
            raise JuniorError(f'🧭 Nouvelle exploration dans {math.ceil((EXPLORATION_COOLDOWN-(now-last["completed_at"]))/60)} minute(s).')
        title, scenes, discoveries = REGIONS[region]
        token = secrets.token_urlsafe(18)
        story = [int(rng.randrange(3)), int(rng.randrange(3))]
        con.execute('INSERT INTO junior_expeditions(token,pet_id,owner_id,guild_id,region,step,choices_json,story_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)', (token,pet_id,owner_id,guild_id,region,0,json.dumps([]),json.dumps(story),now))
        con.commit()
        return {'token':token,'title':title,'question':scenes[0][0],'choices':scenes[0][1], 'step':0}
    except BaseException:
        con.rollback()
        raise


def exploration_step(con, token, pet_id, owner_id, guild_id, choice, now=None):
    import json
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        row = con.execute('SELECT * FROM junior_expeditions WHERE token=? AND pet_id=? AND owner_id=? AND guild_id=?', (token,pet_id,owner_id,guild_id)).fetchone()
        if row is None or row['completed_at'] is not None:
            raise JuniorError('Expédition introuvable ou terminée.')
        if now-row['created_at']>600:
            raise JuniorError('Expédition expirée. Relance une exploration.')
        if str(choice) not in ('0','1','2'):
            raise JuniorError('Choix invalide.')
        title, scenes, discoveries = REGIONS[row['region']]
        step = row['step']
        selected = json.loads(row['choices_json'])
        selected.append(int(choice))
        if step == 0:
            con.execute('UPDATE junior_expeditions SET step=1,choices_json=? WHERE token=? AND step=0', (json.dumps(selected),token))
            con.commit()
            return {'finished':False,'title':title,'question':scenes[1][0],'choices':scenes[1][1],'step':1}
        if step != 1:
            raise JuniorError('Étape invalide.')
        story = json.loads(row['story_json'])
        discovery = discoveries[(sum(selected)+story[0]+story[1])%len(discoveries)]
        cur = con.execute('INSERT OR IGNORE INTO junior_discoveries(pet_id,region,discovery,discovered_at) VALUES(?,?,?,?)', (pet_id,row['region'],discovery,now))
        new = cur.rowcount == 1
        con.execute('UPDATE junior_expeditions SET step=2,choices_json=?,completed_at=?,outcome=? WHERE token=? AND completed_at IS NULL', (json.dumps(selected),now,discovery,token))
        con.execute('UPDATE junior_pets SET bond=bond+3,activities=activities+1,bonheur=MIN(100,bonheur+5),updated_at=? WHERE id=?', (now,pet_id))
        con.execute('INSERT OR IGNORE INTO junior_affinities(pet_id) VALUES(?)',(pet_id,))
        con.execute('UPDATE junior_affinities SET exploration=exploration+2 WHERE pet_id=?',(pet_id,))
        con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES(?,?,?)',(pet_id,'exploration:'+row['region'],now))
        # Material reward is part of the same transaction as expedition completion.
        material = ('cristal_lunaire','poussiere_etoiles','bois_astral')[(sum(selected)+story[0])%3]
        con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,1) ON CONFLICT(pet_id,code) DO UPDATE SET quantity=quantity+1',(pet_id,material))
        con.commit()
        return {'finished':True,'title':title,'discovery':discovery,'new':new,'bond':3}
    except BaseException:
        con.rollback()
        raise


def walk_memory_add(con, pet_id, owner_id, guild_id, region, souvenir, now=None):
    """Record a walk once per completed scene; no star-dust or care changes."""
    now=time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',(pet_id,owner_id,guild_id)).fetchone():
            raise JuniorError('Compagnon introuvable.')
        con.execute('INSERT INTO junior_walk_memories(pet_id,region,souvenir,visits,last_seen) VALUES(?,?,?,1,?) ON CONFLICT(pet_id,region,souvenir) DO UPDATE SET visits=visits+1,last_seen=excluded.last_seen',(pet_id,region,souvenir,now))
        con.commit()
    except BaseException:
        con.rollback()
        raise


def walk_memories(con, pet_id, owner_id, guild_id):
    if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',(pet_id,owner_id,guild_id)).fetchone():
        raise JuniorError('Compagnon introuvable.')
    return con.execute('SELECT region,souvenir,visits,last_seen FROM junior_walk_memories WHERE pet_id=? ORDER BY last_seen DESC LIMIT 30',(pet_id,)).fetchall()


def discoveries(con, pet_id, owner_id, guild_id):
    if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',(pet_id,owner_id,guild_id)).fetchone():
        raise JuniorError('Compagnon introuvable.')
    return con.execute('SELECT region,discovery,discovered_at FROM junior_discoveries WHERE pet_id=? ORDER BY discovered_at DESC',(pet_id,)).fetchall()


# V0.5 — Journal personnel, privé et propre à chaque compagnon.
NOTE_TITLE_LIMIT = 80
NOTE_BODY_LIMIT = 1000
NOTE_LIMIT_PER_PET = 200


def _owned_pet(con, pet_id, owner_id, guild_id):
    if not con.execute('SELECT 1 FROM junior_pets WHERE id=? AND owner_id=? AND guild_id=?',
                       (pet_id, owner_id, guild_id)).fetchone():
        raise JuniorError('Compagnon introuvable ou accès refusé.')


def _note_text(title, body):
    title, body = title.strip(), body.strip()
    if not 1 <= len(title) <= NOTE_TITLE_LIMIT or not 1 <= len(body) <= NOTE_BODY_LIMIT:
        raise JuniorError('Titre : 1 à 80 caractères ; texte : 1 à 1 000 caractères.')
    if any(ord(c) < 32 and c not in '\n\t' for c in title + body):
        raise JuniorError('Caractère de contrôle interdit.')
    return title, body


def note_create(con, pet_id, owner_id, guild_id, title, body, now=None):
    title, body = _note_text(title, body)
    now = time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        _owned_pet(con, pet_id, owner_id, guild_id)
        count = con.execute('SELECT COUNT(*) FROM junior_personal_notes WHERE pet_id=?', (pet_id,)).fetchone()[0]
        if count >= NOTE_LIMIT_PER_PET:
            raise JuniorError('Le journal contient déjà 200 notes. Supprime une ancienne note pour continuer.')
        cur = con.execute('INSERT INTO junior_personal_notes(pet_id,guild_id,owner_id,title,body,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                          (pet_id,guild_id,owner_id,title,body,now,now))
        con.commit()
        return cur.lastrowid
    except BaseException:
        con.rollback()
        raise


def note_list(con, pet_id, owner_id, guild_id, limit=10):
    _owned_pet(con, pet_id, owner_id, guild_id)
    return con.execute('SELECT * FROM junior_personal_notes WHERE pet_id=? AND owner_id=? AND guild_id=? ORDER BY id DESC LIMIT ?',
                       (pet_id,owner_id,guild_id,max(1,min(25,int(limit))))).fetchall()


def note_get(con, note_id, pet_id, owner_id, guild_id):
    _owned_pet(con, pet_id, owner_id, guild_id)
    row = con.execute('SELECT * FROM junior_personal_notes WHERE id=? AND pet_id=? AND owner_id=? AND guild_id=?',
                      (note_id,pet_id,owner_id,guild_id)).fetchone()
    if row is None:
        raise JuniorError('Note introuvable.')
    return row


def note_edit(con, note_id, pet_id, owner_id, guild_id, title, body, now=None):
    title, body = _note_text(title, body)
    now = time.time() if now is None else float(now)
    with con:
        _owned_pet(con, pet_id, owner_id, guild_id)
        cur = con.execute('UPDATE junior_personal_notes SET title=?,body=?,updated_at=? WHERE id=? AND pet_id=? AND owner_id=? AND guild_id=?',
                          (title,body,now,note_id,pet_id,owner_id,guild_id))
        if cur.rowcount != 1:
            raise JuniorError('Note introuvable.')


def note_delete(con, note_id, pet_id, owner_id, guild_id):
    with con:
        _owned_pet(con, pet_id, owner_id, guild_id)
        cur = con.execute('DELETE FROM junior_personal_notes WHERE id=? AND pet_id=? AND owner_id=? AND guild_id=?',
                          (note_id,pet_id,owner_id,guild_id))
        if cur.rowcount != 1:
            raise JuniorError('Note introuvable.')


# V0.6: inventory, rooms, and consent-based gifts. All mutations use SQLite transactions.
def inventory(con, pet_id, owner_id, guild_id):
    _owned_pet(con,pet_id,owner_id,guild_id)
    return con.execute("SELECT i.code,i.category,i.label,i.giftable,v.quantity FROM junior_inventory v JOIN junior_items i ON i.code=v.code WHERE v.pet_id=? AND v.quantity>0 ORDER BY i.category,i.label",(pet_id,)).fetchall()


def add_item(con, pet_id, owner_id, guild_id, code, quantity=1):
    # Internal reward hook: never expose directly through a public Discord button.
    _owned_pet(con,pet_id,owner_id,guild_id)
    item=con.execute('SELECT stackable FROM junior_items WHERE code=?',(code,)).fetchone()
    if not item or not isinstance(quantity,int) or not 1<=quantity<=50:
        raise JuniorError('Objet ou quantité invalide.')
    con.execute('BEGIN IMMEDIATE')
    try:
        current=con.execute('SELECT quantity FROM junior_inventory WHERE pet_id=? AND code=?',(pet_id,code)).fetchone()
        if current and not item['stackable']:
            raise JuniorError('Cet objet unique est déjà possédé.')
        con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,?) ON CONFLICT(pet_id,code) DO UPDATE SET quantity=quantity+excluded.quantity',(pet_id,code,quantity))
        con.commit()
    except BaseException:
        con.rollback();raise


def craft(con,pet_id,owner_id,guild_id,code):
    if code not in RECIPES: raise JuniorError('Recette inconnue.')
    con.execute('BEGIN IMMEDIATE')
    try:
        _owned_pet(con,pet_id,owner_id,guild_id)
        if con.execute('SELECT 1 FROM junior_inventory WHERE pet_id=? AND code=? AND quantity>0',(pet_id,code)).fetchone():
            raise JuniorError('Décoration déjà fabriquée.')
        for ingredient,amount in RECIPES[code].items():
            row=con.execute('SELECT quantity FROM junior_inventory WHERE pet_id=? AND code=?',(pet_id,ingredient)).fetchone()
            if not row or row['quantity']<amount: raise JuniorError('Matériaux insuffisants.')
        for ingredient,amount in RECIPES[code].items():
            con.execute('UPDATE junior_inventory SET quantity=quantity-? WHERE pet_id=? AND code=?',(amount,pet_id,ingredient))
        con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,1)',(pet_id,code))
        con.commit()
    except BaseException:
        con.rollback();raise


def wallet(con,pet_id,owner_id,guild_id):
    _owned_pet(con,pet_id,owner_id,guild_id)
    row=con.execute('SELECT balance,care_progress FROM junior_star_wallet WHERE pet_id=?',(pet_id,)).fetchone()
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    care_row = con.execute('SELECT count FROM junior_daily_care WHERE pet_id=? AND care_date=?',(pet_id,today)).fetchone()
    care_today = int(care_row['count']) if care_row else 0
    return {'balance':int(row['balance']) if row else 0,'care_progress':care_today%10 if care_today<20 else 0,'care_today':care_today,'care_remaining':max(0,40-care_today),'care_reward_remaining':max(0,20-care_today)}


def room(con,pet_id,owner_id,guild_id):
    _owned_pet(con,pet_id,owner_id,guild_id)
    row=con.execute('SELECT theme,decoration FROM junior_rooms WHERE pet_id=?',(pet_id,)).fetchone()
    slots={r['slot']:r['code'] for r in con.execute('SELECT slot,code FROM junior_room_slots WHERE pet_id=?',(pet_id,))}
    if row and row['decoration'] not in ('none',None) and not slots:
        code=row['decoration']
        if code in DECOR_SLOTS: slots[DECOR_SLOTS[code]]=code
    return {'theme':row['theme'] if row else None,'decoration':row['decoration'] if row else 'none','slots':slots}


def decorate(con,pet_id,owner_id,guild_id,theme=None,decoration=None):
    con.execute('BEGIN IMMEDIATE')
    try:
        _owned_pet(con,pet_id,owner_id,guild_id)
        pet=con.execute('SELECT * FROM junior_pets WHERE id=?',(pet_id,)).fetchone()
        current=room(con,pet_id,owner_id,guild_id)
        theme=current['theme'] if theme is None else theme
        if theme not in ROOM_THEMES: raise JuniorError('Thème inconnu.')
        if stage(pet)[0]=='oeuf': raise JuniorError('La chambre se choisit après l’éclosion de l’œuf.')
        first_choice=con.execute('SELECT 1 FROM junior_rooms WHERE pet_id=?',(pet_id,)).fetchone() is None
        con.execute('INSERT INTO junior_rooms(pet_id,theme,decoration) VALUES(?,?,?) ON CONFLICT(pet_id) DO UPDATE SET theme=excluded.theme',(pet_id,theme,'none'))
        if first_choice:
            con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,1) ON CONFLICT(pet_id,code) DO UPDATE SET quantity=MAX(quantity,1)',(pet_id,'oreiller_douillet'))
            con.execute('INSERT OR REPLACE INTO junior_room_slots(pet_id,slot,code) VALUES(?,?,?)',(pet_id,'couchage','oreiller_douillet'))
        if decoration is not None:
            if decoration=='none':
                con.execute('DELETE FROM junior_room_slots WHERE pet_id=?',(pet_id,))
            else:
                if decoration not in DECOR_SLOTS: raise JuniorError('Décoration non compatible avec la chambre.')
                owned=con.execute('SELECT 1 FROM junior_inventory WHERE pet_id=? AND code=? AND quantity>0',(pet_id,decoration)).fetchone()
                if not owned: raise JuniorError('Décoration non possédée.')
                con.execute('INSERT OR REPLACE INTO junior_room_slots(pet_id,slot,code) VALUES(?,?,?)',(pet_id,DECOR_SLOTS[decoration],decoration))
        con.commit()
    except BaseException:
        con.rollback();raise


def purchase_decoration(con,pet_id,owner_id,guild_id,code,now=None):
    if code not in SHOP: raise JuniorError('Cet objet n’est pas vendu en boutique.')
    now=time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        _owned_pet(con,pet_id,owner_id,guild_id)
        if con.execute('SELECT 1 FROM junior_shop_purchases WHERE pet_id=? AND code=?',(pet_id,code)).fetchone():
            raise JuniorError('Tu possèdes déjà cette décoration.')
        if con.execute('SELECT 1 FROM junior_inventory WHERE pet_id=? AND code=? AND quantity>0',(pet_id,code)).fetchone():
            raise JuniorError('Tu possèdes déjà cette décoration.')
        price=SHOP[code][1]
        changed=con.execute('UPDATE junior_star_wallet SET balance=balance-? WHERE pet_id=? AND balance>=?',(price,pet_id,price)).rowcount
        if not changed: raise JuniorError(f'Il faut {price} poussières d’étoiles pour cet objet.')
        con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,1)',(pet_id,code))
        con.execute('INSERT INTO junior_shop_purchases(pet_id,code,price,purchased_at) VALUES(?,?,?,?)',(pet_id,code,price,now))
        if con.execute('SELECT 1 FROM junior_rooms WHERE pet_id=?',(pet_id,)).fetchone():
            con.execute('INSERT OR REPLACE INTO junior_room_slots(pet_id,slot,code) VALUES(?,?,?)',(pet_id,SHOP[code][2],code))
        con.commit()
        return price
    except BaseException:
        con.rollback();raise


def gift_offer(con,sender_pet,owner_id,guild_id,recipient_pet,code,quantity=1,now=None):
    now=time.time() if now is None else float(now)
    if sender_pet==recipient_pet or not isinstance(quantity,int) or not 1<=quantity<=50:
        raise JuniorError('Cadeau invalide.')
    con.execute('BEGIN IMMEDIATE')
    try:
        _owned_pet(con,sender_pet,owner_id,guild_id)
        recipient=con.execute('SELECT owner_id FROM junior_pets WHERE id=? AND guild_id=?',(recipient_pet,guild_id)).fetchone()
        if not recipient or recipient['owner_id']==owner_id: raise JuniorError('Destinataire invalide.')
        item=con.execute('SELECT giftable FROM junior_items WHERE code=?',(code,)).fetchone()
        if not item or not item['giftable']: raise JuniorError('Objet non transférable.')
        stock=con.execute('SELECT quantity FROM junior_inventory WHERE pet_id=? AND code=?',(sender_pet,code)).fetchone()
        reserved=con.execute("SELECT COALESCE(SUM(quantity),0) FROM junior_gifts WHERE sender_pet=? AND code=? AND status='pending' AND created_at>?",(sender_pet,code,now-86400)).fetchone()[0]
        if not stock or stock['quantity']-reserved<quantity: raise JuniorError('Stock disponible insuffisant.')
        if con.execute("SELECT COUNT(*) FROM junior_gifts WHERE sender_pet=? AND status='pending' AND created_at>?",(sender_pet,now-86400)).fetchone()[0]>=5:
            raise JuniorError('Trop de cadeaux en attente.')
        cur=con.execute('INSERT INTO junior_gifts(guild_id,sender_pet,recipient_pet,code,quantity,created_at) VALUES(?,?,?,?,?,?)',(guild_id,sender_pet,recipient_pet,code,quantity,now))
        con.commit();return cur.lastrowid
    except BaseException:
        con.rollback();raise


def gift_resolve(con,gift_id,recipient_owner_id,guild_id,accept,now=None):
    now=time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        gift=con.execute('SELECT g.*,p.owner_id recipient_owner FROM junior_gifts g JOIN junior_pets p ON p.id=g.recipient_pet WHERE g.id=? AND g.guild_id=?',(gift_id,guild_id)).fetchone()
        if not gift or gift['recipient_owner']!=recipient_owner_id: raise JuniorError('Cadeau introuvable ou accès refusé.')
        if gift['status']!='pending': raise JuniorError('Cadeau déjà traité.')
        if now-gift['created_at']>86400:
            status='expired'
        elif not accept:
            status='declined'
        else:
            stock=con.execute('SELECT quantity FROM junior_inventory WHERE pet_id=? AND code=?',(gift['sender_pet'],gift['code'])).fetchone()
            item=con.execute('SELECT stackable FROM junior_items WHERE code=?',(gift['code'],)).fetchone()
            recipient_stock=con.execute('SELECT quantity FROM junior_inventory WHERE pet_id=? AND code=?',(gift['recipient_pet'],gift['code'])).fetchone()
            if not stock or stock['quantity']<gift['quantity'] or (not item['stackable'] and recipient_stock):
                raise JuniorError('Transfert impossible : objet indisponible ou déjà possédé.')
            con.execute('UPDATE junior_inventory SET quantity=quantity-? WHERE pet_id=? AND code=?',(gift['quantity'],gift['sender_pet'],gift['code']))
            con.execute('INSERT INTO junior_inventory(pet_id,code,quantity) VALUES(?,?,?) ON CONFLICT(pet_id,code) DO UPDATE SET quantity=quantity+excluded.quantity',(gift['recipient_pet'],gift['code'],gift['quantity']))
            status='accepted'
        con.execute('UPDATE junior_gifts SET status=?,resolved_at=? WHERE id=?',(status,now,gift_id))
        con.commit();return status
    except BaseException:
        con.rollback();raise


def gifts_received(con,owner_id,guild_id):
    return con.execute("SELECT g.id,g.code,g.quantity,g.created_at,p.name sender_name FROM junior_gifts g JOIN junior_pets p ON p.id=g.sender_pet JOIN junior_pets r ON r.id=g.recipient_pet WHERE r.owner_id=? AND g.guild_id=? AND g.status='pending' ORDER BY g.id DESC LIMIT 20",(owner_id,guild_id)).fetchall()


# V0.7: Two-player, consent-based activities. Both players choose independently.
SOCIAL_GAMES = {
    'duo': ('Duo des étoiles', 'Une porte céleste exige deux gestes complémentaires.',
            ('Activer le cristal bleu', 'Activer le cristal violet', 'Attendre le signal')),
    'tresor': ('Chasse au trésor collective', 'Deux indices révèlent une cachette mystérieuse.',
               ('Examiner la carte', 'Observer les constellations', 'Suivre les empreintes')),
    'festival': ('Festival cosmique', 'Préparons ensemble un spectacle pour le festival !',
                 ('Installer les lanternes', 'Préparer la musique', 'Accueillir les visiteurs')),
}
SOCIAL_COOLDOWN = 1800
SOCIAL_EXPIRY = 86400


def encounter_invite(con, inviter_pet, owner_id, guild_id, invited_pet, game, now=None):
    now = time.time() if now is None else float(now)
    if game not in SOCIAL_GAMES: raise JuniorError('Activité sociale inconnue.')
    con.execute('BEGIN IMMEDIATE')
    try:
        a = _owned_pet(con,inviter_pet,owner_id,guild_id)
        b = con.execute('SELECT * FROM junior_pets WHERE id=? AND guild_id=?',(invited_pet,guild_id)).fetchone()
        if b is None or b['owner_id']==owner_id: raise JuniorError('Invite un compagnon appartenant à un autre membre du serveur.')
        active = con.execute("SELECT COUNT(*) n FROM junior_encounters WHERE inviter_pet=? AND status IN ('pending','active') AND created_at>?",(inviter_pet,now-SOCIAL_EXPIRY)).fetchone()['n']
        if active >= 3: raise JuniorError('Trois invitations ou rencontres sont déjà en attente.')
        duplicate=con.execute("SELECT 1 FROM junior_encounters WHERE inviter_pet=? AND invited_pet=? AND status IN ('pending','active') AND created_at>? LIMIT 1",(inviter_pet,invited_pet,now-SOCIAL_EXPIRY)).fetchone()
        if duplicate: raise JuniorError('Une invitation existe déjà pour ce duo.')
        recent = con.execute("SELECT completed_at FROM junior_encounters WHERE (inviter_pet=? OR invited_pet=?) AND status='completed' ORDER BY completed_at DESC LIMIT 1",(inviter_pet,inviter_pet)).fetchone()
        if recent and now-recent['completed_at']<SOCIAL_COOLDOWN: raise JuniorError('Ton compagnon doit patienter avant une nouvelle rencontre récompensée.')
        con.execute('INSERT INTO junior_encounters(guild_id,inviter_pet,invited_pet,game,created_at) VALUES(?,?,?,?,?)',(guild_id,inviter_pet,invited_pet,game,now))
        encounter_id=con.execute('SELECT last_insert_rowid()').fetchone()[0]
        con.commit();return encounter_id
    except BaseException:
        con.rollback();raise


def encounter_inbox(con,owner_id,guild_id,now=None):
    now=time.time() if now is None else float(now)
    return con.execute("""SELECT e.*,a.name inviter_name,b.name invited_name,a.owner_id inviter_owner,b.owner_id invited_owner
      FROM junior_encounters e JOIN junior_pets a ON a.id=e.inviter_pet
      JOIN junior_pets b ON b.id=e.invited_pet
      WHERE e.guild_id=? AND (a.owner_id=? OR b.owner_id=?)
        AND ((e.status='pending' AND e.created_at>?) OR (e.status='active' AND e.accepted_at>?))
      ORDER BY e.id DESC LIMIT 24""",(guild_id,owner_id,owner_id,now-SOCIAL_EXPIRY,now-SOCIAL_EXPIRY)).fetchall()


def encounter_respond(con,encounter_id,owner_id,guild_id,accept,now=None):
    now=time.time() if now is None else float(now)
    con.execute('BEGIN IMMEDIATE')
    try:
        row=con.execute("""SELECT e.*,p.owner_id invited_owner FROM junior_encounters e
           JOIN junior_pets p ON p.id=e.invited_pet WHERE e.id=? AND e.guild_id=?""",(encounter_id,guild_id)).fetchone()
        if row is None or row['invited_owner']!=owner_id: raise JuniorError('Invitation inaccessible.')
        if row['status']!='pending': raise JuniorError('Invitation déjà traitée.')
        status='expired' if now-row['created_at']>SOCIAL_EXPIRY else ('active' if accept else 'declined')
        con.execute('UPDATE junior_encounters SET status=?,accepted_at=? WHERE id=?',(status,now if status=='active' else None,encounter_id))
        con.commit();return status
    except BaseException:
        con.rollback();raise


# Three narrative chapters per game, each with three choices.
SOCIAL_ROUNDS = {
    'duo': (
        ('Le portail s’éveille : comment l’approcher ?', ('Observer les runes', 'Écouter les vibrations', 'Chercher une clé')),
        ('Deux cristaux résonnent ensemble.', ('Stabiliser la lumière', 'Synchroniser les gestes', 'Protéger le passage')),
        ('Une dernière onde traverse le portail.', ('Guider son ami', 'Réunir les cristaux', 'Sceller les runes')),
    ),
    'tresor': (
        ('La carte révèle une piste.', ('Lire les symboles', 'Suivre les étoiles', 'Examiner le sol')),
        ('Un carrefour sépare les deux chemins.', ('Partager les indices', 'Explorer la grotte', 'Suivre la brise')),
        ('Le coffre attend derrière une énigme.', ('Déchiffrer le sceau', 'Assembler les fragments', 'Chercher un mécanisme')),
    ),
    'festival': (
        ('Le festival ouvre bientôt.', ('Installer les lanternes', 'Répéter la musique', 'Préparer les costumes')),
        ('Une pluie d’étoiles surprend les invités.', ('Abriter les visiteurs', 'Improviser un spectacle', 'Sauver les décorations')),
        ('Le grand final approche.', ('Lancer les lumières', 'Inviter tout le monde', 'Jouer la mélodie finale')),
    ),
}
SOCIAL_ROUND_COUNT = 3


def encounter_progress(con, encounter_id, pet_id, owner_id, guild_id, now=None):
    now = time.time() if now is None else float(now)
    row = con.execute("""SELECT e.*,a.owner_id a_owner,b.owner_id b_owner FROM junior_encounters e
        JOIN junior_pets a ON a.id=e.inviter_pet JOIN junior_pets b ON b.id=e.invited_pet
        WHERE e.id=? AND e.guild_id=?""",(encounter_id,guild_id)).fetchone()
    if row is None or (row['inviter_pet']!=pet_id or row['a_owner']!=owner_id) and (row['invited_pet']!=pet_id or row['b_owner']!=owner_id):
        raise JuniorError('Rencontre inaccessible.')
    if row['status']!='active' or row['accepted_at'] is None or now-row['accepted_at']>SOCIAL_EXPIRY:
        raise JuniorError('Rencontre indisponible ou expirée.')
    side='inviter_choice' if row['inviter_pet']==pet_id else 'invited_choice'
    for number in range(1,SOCIAL_ROUND_COUNT+1):
        r=con.execute('SELECT * FROM junior_encounter_rounds WHERE encounter_id=? AND round_number=?',(encounter_id,number)).fetchone()
        if r is None or r[side] is None:
            prompt, choices=SOCIAL_ROUNDS[row['game']][number-1]
            return {'round':number,'total':SOCIAL_ROUND_COUNT,'prompt':prompt,'choices':choices,'waiting':False}
        if r['inviter_choice'] is None or r['invited_choice'] is None:
            return {'round':number,'total':SOCIAL_ROUND_COUNT,'waiting':True}
    return {'round':SOCIAL_ROUND_COUNT,'total':SOCIAL_ROUND_COUNT,'waiting':True}


def encounter_play(con,encounter_id,pet_id,owner_id,guild_id,choice,now=None):
    now=time.time() if now is None else float(now)
    if not isinstance(choice,int) or choice not in (0,1,2): raise JuniorError('Choix invalide.')
    con.execute('BEGIN IMMEDIATE')
    try:
        progress=encounter_progress(con,encounter_id,pet_id,owner_id,guild_id,now=now)
        if progress['waiting']: raise JuniorError('Ton choix est enregistré : attends ton partenaire.')
        number=progress['round']
        row=con.execute('SELECT * FROM junior_encounters WHERE id=? AND guild_id=?',(encounter_id,guild_id)).fetchone()
        col='inviter_choice' if row['inviter_pet']==pet_id else 'invited_choice'
        con.execute('INSERT OR IGNORE INTO junior_encounter_rounds(encounter_id,round_number) VALUES(?,?)',(encounter_id,number))
        updated=con.execute(f'UPDATE junior_encounter_rounds SET {col}=? WHERE encounter_id=? AND round_number=? AND {col} IS NULL',(choice,encounter_id,number)).rowcount
        if updated!=1: raise JuniorError('Cette manche est déjà jouée.')
        round_row=con.execute('SELECT * FROM junior_encounter_rounds WHERE encounter_id=? AND round_number=?',(encounter_id,number)).fetchone()
        if round_row['inviter_choice'] is None or round_row['invited_choice'] is None:
            con.commit();return {'completed':False,'round_complete':False,'round':number,'reward':0}
        if number<SOCIAL_ROUND_COUNT:
            con.commit();return {'completed':False,'round_complete':True,'round':number,'next_round':number+1,'reward':0}
        rounds=con.execute('SELECT * FROM junior_encounter_rounds WHERE encounter_id=? ORDER BY round_number',(encounter_id,)).fetchall()
        if len(rounds)!=SOCIAL_ROUND_COUNT: raise JuniorError('Des manches sont manquantes.')
        distinct=sum(r['inviter_choice']!=r['invited_choice'] for r in rounds)
        reward=6+distinct*2
        updated=con.execute("UPDATE junior_encounters SET status='completed',completed_at=? WHERE id=? AND status='active'",(now,encounter_id)).rowcount
        if updated!=1: raise JuniorError('Rencontre déjà terminée.')
        for pid in (row['inviter_pet'],row['invited_pet']):
            con.execute('UPDATE junior_pets SET bond=bond+?,activities=activities+1,bonheur=MIN(100,bonheur+8),updated_at=? WHERE id=?',(reward,now,pid))
            con.execute('INSERT OR IGNORE INTO junior_affinities(pet_id) VALUES(?)',(pid,))
            field={'duo':'protection','tresor':'exploration','festival':'art'}[row['game']]
            con.execute(f'UPDATE junior_affinities SET {field}={field}+3 WHERE pet_id=?',(pid,))
            con.execute('INSERT INTO junior_events(pet_id,event,created_at) VALUES(?,?,?)',(pid,'rencontre:'+row['game']+':3_manches',now))
        con.commit();return {'completed':True,'round_complete':True,'round':number,'reward':reward,'bonus':distinct*2}
    except BaseException:
        con.rollback();raise

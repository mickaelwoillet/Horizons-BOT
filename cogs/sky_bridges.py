"""Passerelles du Ciel V8.5 : préférences volontaires, privées et révocables."""
from datetime import datetime, timezone
from .storage import db

INTERESTS = {
    'jeux': '🎮 Jeux', 'musique': '🎵 Musique', 'lecture': '📚 Lecture',
    'cinema': '🎬 Cinéma', 'discussions': '💬 Discussions',
    'creativite': '🎨 Créativité', 'decouvertes': '🔭 Découvertes',
    'activites': '🤝 Activités collectives',
}

def profile(guild_id: int, user_id: int) -> dict:
    with db() as conn:
        row = conn.execute('SELECT enabled FROM bridge_profiles WHERE guild_id=? AND user_id=?', (guild_id,user_id)).fetchone()
        interests = conn.execute('SELECT interest FROM bridge_interests WHERE guild_id=? AND user_id=? ORDER BY interest', (guild_id,user_id)).fetchall()
    return {'enabled': bool(row['enabled']) if row else False, 'interests': [r['interest'] for r in interests]}

def save(guild_id: int, user_id: int, interests: list[str]) -> None:
    values = list(dict.fromkeys(interests))
    if not values or len(values)>5 or any(k not in INTERESTS for k in values):
        raise ValueError('Choisis entre 1 et 5 centres d’intérêt proposés.')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT INTO bridge_profiles(guild_id,user_id,enabled,updated_at) VALUES(?,?,1,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET enabled=1,updated_at=excluded.updated_at', (guild_id,user_id,datetime.now(timezone.utc).isoformat()))
        conn.execute('DELETE FROM bridge_interests WHERE guild_id=? AND user_id=?', (guild_id,user_id))
        conn.executemany('INSERT INTO bridge_interests(guild_id,user_id,interest) VALUES(?,?,?)', ((guild_id,user_id,k) for k in values))

def disable(guild_id: int, user_id: int) -> bool:
    """Efface les préférences et le consentement, sans conserver de profil exploitable."""
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        removed = conn.execute('DELETE FROM bridge_profiles WHERE guild_id=? AND user_id=?', (guild_id,user_id)).rowcount
        conn.execute('DELETE FROM bridge_interests WHERE guild_id=? AND user_id=?', (guild_id,user_id))
        conn.execute('DELETE FROM bridge_requests WHERE guild_id=? AND (requester_id=? OR recipient_id=?)', (guild_id,user_id,user_id))
    return bool(removed)

def suggestions(guild_id: int, user_id: int) -> list[tuple[str,int]]:
    """Comptage anonyme des intérêts partagés ; aucun identifiant d'autre membre exposé."""
    own = profile(guild_id,user_id)
    if not own['enabled'] or not own['interests']:
        return []
    with db() as conn:
        rows = conn.execute('''SELECT i.interest,COUNT(*) AS members FROM bridge_interests i
          JOIN bridge_profiles p ON p.guild_id=i.guild_id AND p.user_id=i.user_id AND p.enabled=1
          WHERE i.guild_id=? AND i.user_id<>? AND i.interest IN (%s)
          GROUP BY i.interest ORDER BY members DESC,i.interest LIMIT 5''' % ','.join('?' for _ in own['interests']),
          (guild_id,user_id,*own['interests'])).fetchall()
    return [(r['interest'],r['members']) for r in rows]

def request_connection(guild_id: int, user_id: int) -> bool:
    """Invite anonymement un volontaire partageant un intérêt, sans MP automatique."""
    own = profile(guild_id, user_id)
    if not own['enabled'] or not own['interests']:
        raise ValueError('Active tes Passerelles et choisis des centres d’intérêt.')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT 1 FROM bridge_requests WHERE guild_id=? AND requester_id=? AND status='pending'",(guild_id,user_id)).fetchone():
            raise ValueError('Une invitation est déjà en attente. Tu peux l’annuler.')
        marks = ','.join('?' for _ in own['interests'])
        sql = ("SELECT p.user_id,COUNT(*) common FROM bridge_profiles p "
               "JOIN bridge_interests i ON i.guild_id=p.guild_id AND i.user_id=p.user_id "
               "WHERE p.guild_id=? AND p.enabled=1 AND p.user_id<>? AND i.interest IN ("+marks+") "
               "AND NOT EXISTS (SELECT 1 FROM bridge_requests r WHERE r.guild_id=p.guild_id AND "
               "((r.requester_id=? AND r.recipient_id=p.user_id) OR (r.recipient_id=? AND r.requester_id=p.user_id))) "
               "GROUP BY p.user_id ORDER BY common DESC,p.user_id LIMIT 1")
        target = conn.execute(sql,(guild_id,user_id,*own['interests'],user_id,user_id)).fetchone()
        if not target:
            return False
        conn.execute('INSERT INTO bridge_requests(guild_id,requester_id,recipient_id,created_at) VALUES(?,?,?,?)',
                     (guild_id,user_id,target['user_id'],datetime.now(timezone.utc).isoformat()))
        return True

def inbox(guild_id: int, user_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT id,created_at FROM bridge_requests WHERE guild_id=? AND recipient_id=? AND status='pending' ORDER BY id DESC LIMIT 10",(guild_id,user_id)).fetchall()
    return [dict(row) for row in rows]

def connections(guild_id: int, user_id: int) -> list[int]:
    with db() as conn:
        rows = conn.execute("SELECT requester_id,recipient_id FROM bridge_requests WHERE guild_id=? AND status='accepted' AND (requester_id=? OR recipient_id=?) ORDER BY id DESC LIMIT 15",(guild_id,user_id,user_id)).fetchall()
    return [r['recipient_id'] if r['requester_id']==user_id else r['requester_id'] for r in rows]

def decide(guild_id: int, user_id: int, request_id: int, accept: bool) -> bool:
    if accept and not profile(guild_id,user_id)['enabled']:
        raise ValueError('Active tes Passerelles avant d’accepter une invitation.')
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT requester_id FROM bridge_requests WHERE id=? AND guild_id=? AND recipient_id=? AND status='pending'",(request_id,guild_id,user_id)).fetchone()
        if not row:
            return False
        if accept:
            sender = conn.execute('SELECT enabled FROM bridge_profiles WHERE guild_id=? AND user_id=?',(guild_id,row['requester_id'])).fetchone()
            if not sender or not sender['enabled']:
                accept=False
        conn.execute('UPDATE bridge_requests SET status=?,decided_at=? WHERE id=?',('accepted' if accept else 'declined',datetime.now(timezone.utc).isoformat(),request_id))
        return True

def cancel_pending(guild_id: int, user_id: int) -> int:
    with db() as conn:
        return conn.execute("DELETE FROM bridge_requests WHERE guild_id=? AND requester_id=? AND status='pending'",(guild_id,user_id)).rowcount

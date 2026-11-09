"""V8.6 : vues personnelles sur les données existantes, sans modifier les salons."""
from datetime import datetime, timedelta, timezone
import discord
from .storage import db
from .sky_bridges import profile, INTERESTS


def _table(conn, name):
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _safe(value, length=70):
    return discord.utils.escape_mentions(discord.utils.escape_markdown(str(value)[:length])).replace("\n", " ")


def community_snapshot(guild_id, user_id):
    result = {'circles': [], 'ideas': [], 'missions': 'Aucune étape enregistrée.', 'arcade': 'Aucune partie enregistrée.'}
    with db() as conn:
        if _table(conn, 'circle_proposals'):
            rows = conn.execute("SELECT name,status FROM circle_proposals WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 4", (guild_id,user_id)).fetchall()
            result['circles'].extend(f"Proposé : {_safe(r['name'])} · {r['status']}" for r in rows)
            if _table(conn,'circle_interests'):
                rows = conn.execute("SELECT c.name FROM circle_interests i JOIN circle_proposals c ON c.id=i.circle_id WHERE c.guild_id=? AND i.user_id=? AND c.status='approved' ORDER BY i.created_at DESC LIMIT 5",(guild_id,user_id)).fetchall()
                result['circles'].extend(f"Intéressé·e : {_safe(r['name'])}" for r in rows)
        if _table(conn,'community_ideas'):
            rows=conn.execute("SELECT id,status FROM community_ideas WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 6",(guild_id,user_id)).fetchall()
            labels={'received':'Reçue','pending':'À l’étude','review':'À l’étude','accepted':'Acceptée','approved':'Acceptée','done':'Réalisée','implemented':'Réalisée','rejected':'Refusée'}
            result['ideas']=[f"Idée #{r['id']} · {labels.get(r['status'],_safe(r['status'],30))}" for r in rows]
        if _table(conn,'horizons_path_progress'):
            n=conn.execute("SELECT COUNT(*) FROM horizons_path_progress WHERE guild_id=? AND user_id=?",(guild_id,user_id)).fetchone()[0]
            result['missions']=f"{n} étape(s) de parcours enregistrée(s)."
        if _table(conn,'celestial_game_player_stats'):
            rows=conn.execute("SELECT game_key,played,wins FROM celestial_game_player_stats WHERE guild_id=? AND user_id=? ORDER BY updated_at DESC LIMIT 4",(guild_id,user_id)).fetchall()
            result['arcade']='\n'.join(f"{_safe(r['game_key'],32)} : {r['played']} partie(s), {r['wins']} victoire(s)" for r in rows) or result['arcade']
    return result


def compatible_activities(guild_id,user_id):
    """Suggestions basées sur les centres d'intérêt déclarés, sans révéler de membres."""
    own=profile(guild_id,user_id)
    if not own['enabled'] or not own['interests']:
        return []
    # Des mots-clés génériques, pas d'inférence sur les émotions ni le profil.
    words={'jeux':['jeu','quiz','arcade'],'musique':['musique','chant','blind test'],'lecture':['livre','lecture'],'cinema':['cinéma','film'],'discussions':['discussion','débat'],'creativite':['dessin','créati','atelier'],'decouvertes':['découvert','culture'],'activites':['activité','ensemble','rencontre']}
    terms=[w for key in own['interests'] for w in words.get(key,())]
    result=[]
    with db() as conn:
        if _table(conn,'events'):
            rows=conn.execute("SELECT title,starts_at FROM events WHERE guild_id=? AND status='open' AND starts_at>=? ORDER BY starts_at LIMIT 30",(guild_id,datetime.now(timezone.utc).isoformat())).fetchall()
            for r in rows:
                if any(w in r['title'].lower() for w in terms):
                    result.append(f"📅 {_safe(r['title'],70)} · {r['starts_at'][:10]}")
                    if len(result)>=3: break
        if len(result)<5 and _table(conn,'circle_proposals'):
            rows=conn.execute("SELECT name,theme FROM circle_proposals WHERE guild_id=? AND status='approved' ORDER BY id DESC LIMIT 30",(guild_id,)).fetchall()
            for r in rows:
                if any(w in (r['name']+' '+r['theme']).lower() for w in terms):
                    result.append(f"🌙 Cercle : {_safe(r['name'])}")
                    if len(result)>=5: break
    return result


def mood_enable(guild_id,user_id):
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS centre_mood_optin(guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,PRIMARY KEY(guild_id,user_id))')
        conn.execute('INSERT OR IGNORE INTO centre_mood_optin(guild_id,user_id) VALUES(?,?)',(guild_id,user_id))


def mood_clear(guild_id,user_id):
    with db() as conn:
        conn.execute('DELETE FROM mood_entries WHERE guild_id=? AND user_id=?',(guild_id,user_id))
        conn.execute('CREATE TABLE IF NOT EXISTS centre_mood_optin(guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,PRIMARY KEY(guild_id,user_id))')
        conn.execute('DELETE FROM centre_mood_optin WHERE guild_id=? AND user_id=?',(guild_id,user_id))


def mood_summary(guild_id,user_id):
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS centre_mood_optin(guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,PRIMARY KEY(guild_id,user_id))')
        enabled=bool(conn.execute('SELECT 1 FROM centre_mood_optin WHERE guild_id=? AND user_id=?',(guild_id,user_id)).fetchone())
        entries=[]
        if enabled:
            since=(datetime.now(timezone.utc)-timedelta(days=7)).date().isoformat()
            rows=conn.execute('SELECT mood_date,mood FROM mood_entries WHERE guild_id=? AND user_id=? AND mood_date>=? ORDER BY mood_date DESC LIMIT 7',(guild_id,user_id,since)).fetchall()
            entries=[f"{r['mood_date']} · {_safe(r['mood'],40)}" for r in rows]
    return {'enabled':enabled,'entries':entries}

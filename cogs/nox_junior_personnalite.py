"""Persistent, non-monetary NOX Junior personality; daily progress is idempotent."""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone

TRAITS = ('curiosite', 'affection', 'malice', 'courage')
LABELS = {'curiosite':'🔭 Curiosité', 'affection':'💜 Affection', 'malice':'✨ Malice', 'courage':'🛡️ Courage'}
ACTIVITY_TRAITS = {'parler':'affection', 'histoires':'curiosite', 'jouets':'malice', 'calme':'affection'}
WALK_TRAITS = {'jardin_lucioles':'curiosite', 'plage_lunaire':'courage', 'prairie_cometes':'malice', 'bibliotheque_celeste':'curiosite'}


def _schema(con):
    con.execute('''CREATE TABLE IF NOT EXISTS junior_personality (
        pet_id INTEGER PRIMARY KEY, curiosite INTEGER NOT NULL, affection INTEGER NOT NULL,
        malice INTEGER NOT NULL, courage INTEGER NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS junior_personality_progress (
        pet_id INTEGER NOT NULL, activity TEXT NOT NULL, day TEXT NOT NULL,
        PRIMARY KEY (pet_id, activity, day))''')


def _initial(pet_id):
    digest = hashlib.sha256(f'horizons-nox-junior:{int(pet_id)}'.encode()).digest()
    return {trait: 25 + digest[i] % 16 for i, trait in enumerate(TRAITS)}


def profile(con, pet_id):
    _schema(con)
    row = con.execute('SELECT * FROM junior_personality WHERE pet_id=?', (pet_id,)).fetchone()
    if row is None:
        values = _initial(pet_id)
        con.execute('INSERT OR IGNORE INTO junior_personality VALUES (?,?,?,?,?)',
                    (pet_id, *(values[t] for t in TRAITS)))
        row = con.execute('SELECT * FROM junior_personality WHERE pet_id=?', (pet_id,)).fetchone()
    return {t: int(row[t]) for t in TRAITS}


def record(con, pet_id, activity, *, now=None):
    """Award one personality point per distinct completed activity per UTC day.

    Replays remain unlimited and do not award currency or care actions.
    """
    if activity.startswith('complicite:'):
        trait = ACTIVITY_TRAITS.get(activity.split(':', 1)[1])
    elif activity.startswith('promenade:'):
        trait = WALK_TRAITS.get(activity.split(':', 1)[1])
    else:
        trait = None
    if trait is None:
        raise ValueError('Activité inconnue pour la personnalité')
    profile(con, pet_id)
    date = datetime.fromtimestamp(now, timezone.utc).date().isoformat() if now is not None else datetime.now(timezone.utc).date().isoformat()
    cursor = con.execute('INSERT OR IGNORE INTO junior_personality_progress VALUES (?,?,?)', (pet_id, activity, date))
    if cursor.rowcount:
        con.execute(f'UPDATE junior_personality SET {trait}=MIN(100,{trait}+1) WHERE pet_id=?', (pet_id,))
    return bool(cursor.rowcount)


def favorite(values):
    return max(TRAITS, key=lambda t: (values[t], -TRAITS.index(t)))


def description(values):
    trait = favorite(values)
    return {
        'curiosite':'NOX aime découvrir, observer et poser mille questions.',
        'affection':'NOX adore les moments partagés et la douceur.',
        'malice':'NOX invente des jeux et de petites farces cosmiques.',
        'courage':'NOX aime partir à l’aventure et essayer de nouvelles choses.',
    }[trait]


def reaction(values, activity):
    trait = favorite(values)
    return {
        'curiosite':'🔭 NOX se demande déjà ce que vous découvrirez ensuite !',
        'affection':'💜 NOX se rapproche de toi avec un sourire.',
        'malice':'✨ NOX te lance un regard malicieux.',
        'courage':'🛡️ NOX se tient fièrement prêt pour la suite.',
    }[trait]

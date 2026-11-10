"""Mémoire factuelle de NOX : uniquement actions du Refuge et aventures.

Aucun contenu de message n'est lu, conservé ou analysé.
"""
from __future__ import annotations

from . import nox_refuge_engine as engine

CARE_NAMES = {
    'nourrir': 'repas', 'boire': 'verres d’eau', 'jouer': 'parties',
    'calin': 'câlins', 'bain': 'bains', 'repos': 'siestes',
}


def memory_summary(con, guild_id: int, user_id: int | None = None):
    """Retourne une mémoire sobre, dérivée des faits déjà stockés en SQLite."""
    if user_id is None:
        rows = con.execute('''SELECT action, SUM(count) AS n FROM nox_refuge_contributions
            WHERE guild_id=? GROUP BY action''', (guild_id,)).fetchall()
    else:
        rows = con.execute('''SELECT action, count AS n FROM nox_refuge_contributions
            WHERE guild_id=? AND user_id=?''', (guild_id, user_id)).fetchall()
    care = {r['action']: int(r['n']) for r in rows if r['action'] in CARE_NAMES}
    adventure_count = 0
    vote_count = 0
    try:
        if user_id is None:
            adventure_count = con.execute('''SELECT COUNT(*) FROM nox_adventures
                WHERE guild_id=? AND closed_at IS NOT NULL''', (guild_id,)).fetchone()[0]
        else:
            vote_count = con.execute('''SELECT COUNT(DISTINCT v.adventure_id)
                FROM nox_adventure_votes v JOIN nox_adventures a ON a.id=v.adventure_id
                WHERE a.guild_id=? AND v.user_id=?''', (guild_id, user_id)).fetchone()[0]
    except Exception as exc:
        # Les aventures n'ont pas forcément encore été initialisées sur ce serveur.
        if 'no such table' not in str(exc).lower():
            raise
    return {'care': care, 'total_care': sum(care.values()),
            'adventures': int(adventure_count), 'votes': int(vote_count)}


def milestone_reply(action: str, count: int) -> str | None:
    """Récompense ponctuelle sans publication publique supplémentaire."""
    if count not in (5, 10, 25, 50, 100):
        return None
    return (f'🌟 NOX a une mémoire de petit astronaute : c’est ton {count}ᵉ '
            f'{CARE_NAMES.get(action, "soin")} ! Il vient de te décerner '
            'le titre imaginaire de « Complice cosmique ». 💛')

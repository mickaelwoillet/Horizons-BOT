"""Distinctions symboliques de NOX, calculées depuis les contributions existantes.

Aucun rôle Discord, aucune écriture de données et aucun classement compétitif.
"""
from __future__ import annotations

HONORS = (
    ('premier_calin', '💛 Premier câlin cosmique', 'calin', 1),
    ('gardien_biscuits', '🍪 Gardien des biscuits', 'nourrir', 5),
    ('fontaine_etoiles', '💧 Fontaine d’étoiles', 'boire', 5),
    ('complice_jeu', '🎮 Complice des bêtises', 'jouer', 5),
    ('protecteur_bulles', '🛁 Protecteur des bulles', 'bain', 5),
    ('veilleur_lunes', '🌙 Veilleur des lunes', 'repos', 5),
    ('calin_intergalactique', '🫶 Câlineur intergalactique', 'calin', 25),
    ('ami_refuge', '🌟 Ami fidèle du Refuge', None, 25),
    ('pilier_refuge', '🏅 Pilier du Refuge', None, 100),
)


def honorary_titles(con, guild_id: int, user_id: int):
    """Retourne les distinctions acquises et les progrès, par serveur et membre."""
    rows = con.execute(
        'SELECT action, count FROM nox_refuge_contributions WHERE guild_id=? AND user_id=?',
        (guild_id, user_id),
    ).fetchall()
    counts = {row['action']: int(row['count']) for row in rows}
    total = sum(counts.values())
    earned, upcoming = [], []
    for key, title, action, threshold in HONORS:
        count = total if action is None else counts.get(action, 0)
        if count >= threshold:
            earned.append({'id': key, 'title': title})
        else:
            upcoming.append({'id': key, 'title': title, 'current': count, 'required': threshold})
    return {'earned': earned, 'upcoming': upcoming, 'total': total}

"""Carte du Ciel V8.1 : référentiel stable et lecture de progression réelle.

Les déblocages sont déclenchés exclusivement par les modules métier au moment
ou une action est vérifiée. Ne jamais attribuer une étoile sur simple consultation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .storage import db

ORIGINS = {
    "origins.centre": "Premier Horizon",
    "origins.discussion": "Première Voix",
    "origins.quiz": "Esprit Curieux",
    "origins.activity": "Main Tendue",
    "origins.circle": "Explorateur",
    "origins.recognition": "Éclat Partagé",
    "origins.mission": "Aventurier",
    "origins.capsule": "Mémoire du Ciel",
    "origins.game": "Étoile du Jeu",
    "origins.idea": "Porteur d'Idées",
    "origins.connection": "Lien Vivant",
    "origins.complete": "Constellation",
}
THEMES = {
    "exploration": "Exploration", "bienveillance": "Bienveillance",
    "creativite": "Créativité", "rencontres": "Rencontres", "aventure": "Aventure",
}
# Les cinq séries suivantes sont définies sans objectifs artificiels : les
# déclencheurs seront branchés sur des actions vérifiées dans les modules V8.6.
THEME_KEYS = {theme: tuple(f"{theme}.{i}" for i in range(1, 6)) for theme in THEMES}
ALL_KEYS = frozenset(ORIGINS) | frozenset(k for keys in THEME_KEYS.values() for k in keys)


def unlocked(guild_id: int, user_id: int) -> set[str]:
    with db() as conn:
        return {row["star_key"] for row in conn.execute(
            "SELECT star_key FROM sky_unlocks WHERE guild_id=? AND user_id=?",
            (guild_id, user_id))}


def grant(guild_id: int, user_id: int, star_key: str) -> bool:
    """Déblocage idempotent : True uniquement lors de la première attribution."""
    if star_key not in ALL_KEYS or star_key == "origins.complete":
        raise ValueError("Étoile inconnue ou calculée automatiquement")
    with db() as conn:
        result = conn.execute(
            "INSERT OR IGNORE INTO sky_unlocks(guild_id,user_id,star_key,unlocked_at) VALUES(?,?,?,?)",
            (guild_id, user_id, star_key, datetime.now(timezone.utc).isoformat()))
        if star_key.startswith("origins."):
            count = conn.execute("SELECT COUNT(*) FROM sky_unlocks WHERE guild_id=? AND user_id=? AND star_key LIKE 'origins.%' AND star_key != 'origins.complete'", (guild_id,user_id)).fetchone()[0]
            if count == 11:
                conn.execute("INSERT OR IGNORE INTO sky_unlocks(guild_id,user_id,star_key,unlocked_at) VALUES(?,?,?,?)", (guild_id,user_id,"origins.complete",datetime.now(timezone.utc).isoformat()))
        return result.rowcount == 1


def progress(guild_id: int, user_id: int) -> dict:
    keys = unlocked(guild_id, user_id)
    origin_count = len(keys.intersection(ORIGINS))
    return {"origins": origin_count, "origins_total": len(ORIGINS),
            "themes_open": origin_count == len(ORIGINS),
            "themes": {theme: len(keys.intersection(stars)) for theme, stars in THEME_KEYS.items()}}

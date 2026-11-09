"""V8.3 : lecture du Coffre depuis les Trésors du Ciel existants.

Aucune monnaie, carte ou tirage supplémentaire : ce tableau de bord réutilise
exclusivement les tables et règles du module celestial_treasures.
"""
from __future__ import annotations

from .storage import db
from .celestial_treasures import STARS, CONSTELLATIONS, today_key


def snapshot(guild_id: int, user_id: int) -> dict:
    """Instantané privé du coffre ; ne consomme jamais de carte."""
    with db() as conn:
        stars = {r[0] for r in conn.execute(
            "SELECT star_key FROM celestial_stars WHERE guild_id=? AND user_id=?", (guild_id, user_id))}
        dust = conn.execute("SELECT dust FROM celestial_dust WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()
        fragments = conn.execute("SELECT fragments FROM celestial_fragments WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()
        used = conn.execute("SELECT 1 FROM celestial_daily_cards WHERE guild_id=? AND user_id=? AND card_date=? AND used_at IS NOT NULL", (guild_id, user_id, today_key())).fetchone()
        gifts = conn.execute("SELECT COUNT(*) FROM celestial_gift_cards WHERE guild_id=? AND user_id=? AND used_at IS NULL", (guild_id, user_id)).fetchone()[0]
        memories = {r[0] for r in conn.execute("SELECT reward_key FROM celestial_collection_unlocks WHERE guild_id=? AND user_id=?", (guild_id, user_id))}
    complete = [label for _key, (label, keys, _role) in CONSTELLATIONS.items() if set(keys).issubset(stars)]
    return {
        "stars": len(stars & STARS.keys()), "total_stars": len(STARS),
        "dust": int(dust[0]) if dust else 0,
        "fragments": int(fragments[0]) if fragments else 0,
        "daily_available": not bool(used), "gift_cards": int(gifts),
        "constellations": complete, "memories": len(memories),
    }

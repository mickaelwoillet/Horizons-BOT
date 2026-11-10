"""Bilan quotidien de NOX : uniquement des participations réellement enregistrées."""
from __future__ import annotations
import random

OPENINGS = (
    "🌙 Journal de bord cosmique de NOX !",
    "✨ Dernière transmission du vaisseau pour aujourd'hui !",
    "🦆 Coincoin a réclamé le micro pour le bilan du soir !",
    "🌌 Le ciel s'assombrit, mais le Refuge brille encore !",
)
ENDING = (
    "Merci d'être là, même quand tu préfères simplement lire. À demain ! 💛",
    "Le vaisseau passe en mode nuit. Prenez soin de vous, mes étoiles ! 🌟",
    "Je range mes biscuits et je vous retrouve demain pour une nouvelle aventure ! 🍪",
    "Coincoin souhaite une douce soirée à tout le monde. Oui, même au grille-pain. 🦆",
)
SINGULAR = (
    "Une étoile courageuse a rejoint le défi du jour. Une participation, c'est déjà une aventure !",
    "Une personne a relevé mon défi aujourd'hui : mission courage validée !",
)
PLURAL = (
    "{count} étoiles ont relevé le défi du jour ! Mon tableau de bord scintille. ✨",
    "{count} membres ont rejoint la mission du jour. Coincoin demande une médaille ! 🦆",
    "{count} participations au défi ! C'est plus que mon stock de biscuits... enfin, presque. 🍪",
)
ZERO = (
    "Personne n'a rejoint le défi aujourd'hui, et c'est très bien aussi : on avance à son rythme.",
    "Le défi du jour est resté tranquille. Même les aventuriers cosmiques ont le droit de souffler.",
)


def challenge_count(con, guild_id: int, day: str) -> int | None:
    """None means no challenge was scheduled; never invent participation."""
    from .nox_daily_challenges import init_db, CHALLENGE_SLOT
    init_db(con)
    exists = con.execute(
        "SELECT 1 FROM nox_daily_challenges WHERE guild_id=? AND local_day=? AND slot=?",
        (guild_id, day, CHALLENGE_SLOT),
    ).fetchone()
    if not exists:
        return None
    return int(con.execute(
        "SELECT COUNT(*) FROM nox_daily_challenge_members WHERE guild_id=? AND local_day=? AND slot=?",
        (guild_id, day, CHALLENGE_SLOT),
    ).fetchone()[0])


def build_evening_recap(con, guild_id: int, day: str) -> str:
    """Deterministic per server/day: restart-safe and no member names exposed."""
    rng = random.Random(f"nox-recap:{guild_id}:{day}")
    count = challenge_count(con, guild_id, day)
    if count is None:
        middle = "Aujourd'hui, pas de défi à comptabiliser dans mon journal. L'aventure continue demain !"
    elif count == 0:
        middle = rng.choice(ZERO)
    elif count == 1:
        middle = rng.choice(SINGULAR)
    else:
        middle = rng.choice(PLURAL).format(count=count)
    from .nox_collective_celebrations import recap_celebration
    celebration = recap_celebration(count, rng)
    sections = [rng.choice(OPENINGS), middle]
    if celebration:
        sections.append(celebration)
    sections.append(rng.choice(ENDING))
    return "\n\n".join(sections)

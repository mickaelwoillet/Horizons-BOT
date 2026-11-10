"""Célébrations sans publication supplémentaire ni classement individuel."""
from __future__ import annotations
import random

# Ces seuils concernent le défi du jour, pas les XP ni les rôles.
MILESTONES = (3, 5, 10, 15, 20, 30, 50, 100)
MILESTONE_TEXTS = {
    3: "Trois étoiles dans l'équipage ! Coincoin commence à distribuer les casques. 🦆",
    5: "Cinq aventuriers ! Le grille-pain vient de demander un badge de capitaine. 🍞",
    10: "Dix personnes réunies ! Mon radar affiche une constellation entière. ✨",
    15: "Quinze volontaires ! Le vaisseau réclame une salle de réunion plus grande. 🚀",
    20: "Vingt étoiles ! Même Saturne nous fait coucou. 🪐",
    30: "Trente explorateurs ! Coincoin a perdu le compte de ses plumes. 🦆",
    50: "Cinquante membres ! Mon cœur cosmique fait des loopings. 💛",
    100: "Cent participations ! Alerte : la galaxie applaudit ! 🌌",
}
RECAP_LINES = (
    "Aujourd'hui, notre petite mission a pris des airs de grande aventure collective. 🚀",
    "Coincoin est fier de cet équipage. Il a même promis de ne pas toucher aux commandes ce soir. 🦆",
    "Ce n'est pas une compétition : chaque participation compte, et chacune est la bienvenue. 💛",
    "On a prouvé qu'un simple clic pouvait rassembler tout un équipage. ✨",
)


def participation_reply(total: int) -> str:
    """Réponse privée au participant : aucune annonce publique additionnelle."""
    if total in MILESTONE_TEXTS:
        return f"🐾 **Palier collectif : {total} !** {MILESTONE_TEXTS[total]} Merci d'avoir participé !"
    return f"🐾 Bravo ! NOX t'inscrit dans son équipage cosmique. Vous êtes maintenant **{total}** à relever le défi !"


def recap_celebration(count: int | None, rng: random.Random) -> str | None:
    """Complément du bilan de 22h50, uniquement si un palier a été atteint."""
    if count is None or count < MILESTONES[0]:
        return None
    milestone = max(n for n in MILESTONES if n <= count)
    return f"🏅 **Palier collectif atteint : {milestone} !** {MILESTONE_TEXTS[milestone]}\n{rng.choice(RECAP_LINES)}"

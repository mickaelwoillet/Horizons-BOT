"""Module retiré : la structure Arcade et Trésors du Ciel existe déjà.

La commande historique /ajoutstructure a été retirée. Les identifiants et
paramètres de structure déjà enregistrés dans SQLite sont conservés.
Ce module reste temporairement comme stub de compatibilité ; il n'est plus
chargé par bot.py et ne déclare aucune commande Discord.
"""

from discord.ext import commands


async def setup(bot: commands.Bot) -> None:
    """Extension inactive conservée pour compatibilité avec d'anciens déploiements."""
    return None

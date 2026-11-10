"""Consultation privée des distinctions symboliques du Refuge de NOX."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .nox_refuge import DB
from . import nox_refuge_engine as engine
from .nox_honors import honorary_titles


class NoxHonors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxtitres(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message('Commande réservée au serveur.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            with engine.connect(DB) as con:
                result = honorary_titles(con, interaction.guild.id, interaction.user.id)
        except Exception:
            await interaction.followup.send('Le carnet de NOX est momentanément indisponible.', ephemeral=True)
            return
        lines = ['🐾 **Les distinctions de NOX**',
                 '« Mes amis méritent des étoiles. Et des biscuits. Surtout des biscuits. »', '']
        if result['earned']:
            lines.extend(['**Tes distinctions :**'] + [item['title'] for item in result['earned']])
        else:
            lines.append('Aucune distinction pour le moment : ton aventure commence ! 💛')
        if result['upcoming']:
            next_title = min(result['upcoming'], key=lambda x: (x['required']-x['current'], x['required']))
            lines.append(f'\n✨ **Prochain souvenir :** {next_title["title"]} '
                         f'({next_title["current"]}/{next_title["required"]})')
        lines.append('\n*Titres symboliques : aucun XP ni rôle Discord attribué.*')
        await interaction.followup.send('\n'.join(lines), ephemeral=True,
                                        allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(NoxHonors(bot))

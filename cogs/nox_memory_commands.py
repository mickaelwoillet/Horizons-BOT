"""Consultation volontaire de la mémoire factuelle de NOX."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .nox_refuge import DB
from . import nox_refuge_engine as engine
from .nox_memory import memory_summary, CARE_NAMES


class NoxMemory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxmemoire(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('Commande réservée au serveur.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        with engine.connect(DB) as con:
            collective = memory_summary(con, interaction.guild.id)
            personal = memory_summary(con, interaction.guild.id, interaction.user.id)
        if not collective['total_care'] and not collective['adventures']:
            message = '🐾 NOX ouvre son carnet cosmique… Il est encore tout neuf !'
        else:
            message = (f'🐾 **Le carnet cosmique de NOX**\n'
                       f'💛 {collective["total_care"]} soins collectifs enregistrés\n'
                       f'🌌 {collective["adventures"]} aventures terminées\n'
                       f'✨ Tu as participé à {personal["votes"]} aventure(s) '
                       f'et offert {personal["total_care"]} soin(s) à NOX.')
            if personal['care']:
                details = ', '.join(f'{CARE_NAMES[action]} : {count}' for action, count in personal['care'].items())
                message += f'\n📖 Tes souvenirs : {details}.'
        await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    await bot.add_cog(NoxMemory(bot))

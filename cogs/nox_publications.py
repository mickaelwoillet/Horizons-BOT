"""Publications manuelles de NOX, avec 20 choix et salon au choix (administrateurs)."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR
from . import nox_refuge_engine as refuge_engine
from .nox_identity import send_as_nox
import logging
log = logging.getLogger(__name__)

CATALOGUE = Path(__file__).resolve().parent.parent / 'data' / 'nox' / 'messages_manuels.json'

class NoxPublications(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def me(self, interaction: discord.Interaction, texte: app_commands.Range[str, 1, 1800], salon: discord.TextChannel | None = None):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild:
            return
        target = salon or interaction.channel
        if not isinstance(target, discord.TextChannel) or target.guild.id != interaction.guild.id:
            await interaction.followup.send('Choisis un salon texte de ce serveur.', ephemeral=True)
            return
        try:
            posted = await send_as_nox(target, content=str(texte))
            log.info('NOX /me : admin=%s guild=%s salon=%s message=%s', interaction.user.id, interaction.guild.id, target.id, posted.id)
            await interaction.followup.send(f'🐾 NOX a parlé dans {target.mention} : {posted.jump_url}', ephemeral=True)
        except discord.HTTPException:
            log.exception('Publication /me impossible')
            await interaction.followup.send('Impossible de publier. Vérifie les permissions Gérer les webhooks et Envoyer des messages.', ephemeral=True)

    async def noxpublier(self, interaction: discord.Interaction, message: app_commands.Choice[str], salon: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None or salon.guild.id != interaction.guild.id:
            await interaction.followup.send('Salon invalide pour ce serveur.', ephemeral=True)
            return
        me = interaction.guild.me
        if me is None or not salon.permissions_for(me).send_messages or not salon.permissions_for(me).embed_links:
            await interaction.followup.send('Je ne peux pas publier dans ce salon (messages et intégrations requis).', ephemeral=True)
            return
        try:
            entries = json.loads(CATALOGUE.read_text(encoding='utf-8'))
            item = next((x for x in entries if x['id'] == message.value), None)
            if item is None:
                await interaction.followup.send('Réplique introuvable dans le catalogue.', ephemeral=True)
                return
            embed = discord.Embed(description=item['message'], color=0xD6AD55)
            embed.set_author(name='NOX · La mascotte d’HORIZONS')
            embed.set_footer(text='NOX · Un peu de chaos, beaucoup de tendresse')
            # Si un Refuge existe, tout appel aux soins y renvoie directement.
            if message.value in {'nox_01','nox_02','nox_03','nox_04','nox_05','nox_11','nox_20'}:
                try:
                    from .nox_refuge import DB
                    with refuge_engine.connect(DB) as con:
                        state = refuge_engine.snapshot(con, interaction.guild.id)
                    if state['channel_id'] and state['message_id']:
                        url = f'https://discord.com/channels/{interaction.guild.id}/{state["channel_id"]}/{state["message_id"]}'
                        embed.add_field(name='🐾 Prendre soin de NOX', value=f'[Rejoindre son Refuge]({url})', inline=False)
                except (OSError, ValueError, sqlite3.Error):
                    pass
            posted = await send_as_nox(salon, embed=embed)
            await interaction.followup.send(f'🐾 NOX a publié « {item["titre"]} » dans {salon.mention} : {posted.jump_url}', ephemeral=True)
        except (discord.HTTPException, OSError, ValueError, KeyError) as exc:
            await interaction.followup.send(f'Publication impossible : {type(exc).__name__}. Vérifie notamment la permission Gérer les webhooks.', ephemeral=True)

async def setup(bot):
    await bot.add_cog(NoxPublications(bot))

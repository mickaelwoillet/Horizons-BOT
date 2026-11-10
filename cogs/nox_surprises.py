"""Surprises collectives manuelles de NOX, sans analyse des conversations."""
from __future__ import annotations
import json
import logging
import random
import sqlite3
import time
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from config import DATA_DIR
from .nox_identity import send_as_nox
from .nox_refuge import DB
from . import nox_refuge_engine as engine

log = logging.getLogger(__name__)
BANK = Path(DATA_DIR) / 'nox' / 'surprises_collectives.json'


def choose_new(items, previous):
    candidates = [x for x in items if x != previous]
    return random.choice(candidates or items)


class NoxSurprises(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxsurprise(self, interaction: discord.Interaction, theme: app_commands.Choice[str], salon: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or salon.guild.id != interaction.guild.id:
            await interaction.followup.send('Choisis un salon de ce serveur.', ephemeral=True)
            return
        me = interaction.guild.me
        perms = salon.permissions_for(me) if me else None
        if not perms or not (perms.view_channel and perms.send_messages and perms.manage_webhooks):
            await interaction.followup.send('Permissions Voir le salon, Envoyer des messages et Gérer les webhooks nécessaires.', ephemeral=True)
            return
        try:
            data = json.loads(BANK.read_text(encoding='utf-8'))
            items = data.get(theme.value, [])
            if not items:
                await interaction.followup.send('Aucune surprise disponible pour ce thème.', ephemeral=True)
                return
            with engine.connect(DB) as con:
                con.execute('CREATE TABLE IF NOT EXISTS nox_surprise_history (guild_id INTEGER NOT NULL, theme TEXT NOT NULL, last_text TEXT NOT NULL, last_at REAL NOT NULL, PRIMARY KEY (guild_id, theme))')
                row = con.execute('SELECT last_text FROM nox_surprise_history WHERE guild_id=? AND theme=?', (interaction.guild.id, theme.value)).fetchone()
                previous = row[0] if row else None
            text = choose_new(items, previous)
            posted = await send_as_nox(salon, content=text, allowed_mentions=discord.AllowedMentions.none())
            with engine.connect(DB) as con:
                con.execute('INSERT INTO nox_surprise_history VALUES (?,?,?,?) ON CONFLICT(guild_id,theme) DO UPDATE SET last_text=excluded.last_text,last_at=excluded.last_at', (interaction.guild.id, theme.value, text, time.time()))
                con.commit()
            log.info('NOX surprise : guild=%s admin=%s salon=%s theme=%s message=%s', interaction.guild.id, interaction.user.id, salon.id, theme.value, posted.id)
            await interaction.followup.send(f'🐾 Surprise publiée dans {salon.mention} : {posted.jump_url}', ephemeral=True)
        except (discord.HTTPException, OSError, ValueError, KeyError, sqlite3.Error):
            log.exception('Échec surprise NOX')
            await interaction.followup.send('Publication impossible. Vérifie le webhook et la configuration.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxSurprises(bot))

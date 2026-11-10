"""Interventions rares de NOX dans La place, avec lien vers le Refuge.

Activation explicite par un administrateur ; aucune publication au démarrage.
"""
from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from .nox_identity import send_as_nox
from .nox_refuge import DB, NEEDS
from . import nox_refuge_engine as engine

log = logging.getLogger(__name__)
MIN_INTERVAL = 6 * 3600
SAME_NEED_INTERVAL = 18 * 3600
QUIET_HOURS = (22, 9)  # heure française


def ensure_presence(con: sqlite3.Connection):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_presence_config (
        guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 0, last_post REAL NOT NULL DEFAULT 0,
        last_need TEXT, last_need_at REAL NOT NULL DEFAULT 0)''')
    con.commit()


def eligible(state, config, now, hour):
    """Politique anti-spam testable sans connexion Discord."""
    if not config or not config['enabled'] or not state['message_id'] or not state['channel_id']:
        return None
    if hour >= QUIET_HOURS[0] or hour < QUIET_HOURS[1]:
        return None
    if now - config['last_post'] < MIN_INTERVAL:
        return None
    for need in state['needs']:
        if need != config['last_need'] or now - config['last_need_at'] >= SAME_NEED_INTERVAL:
            return need
    return None


class NoxPresence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()
        self.presence_loop.start()

    def cog_unload(self):
        self.presence_loop.cancel()

    async def noxpresence(self, interaction: discord.Interaction, salon: discord.TextChannel, actif: bool):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or salon.guild.id != interaction.guild.id:
            await interaction.followup.send('Choisis un salon du serveur.', ephemeral=True)
            return
        me = interaction.guild.me
        if not me or not salon.permissions_for(me).manage_webhooks:
            await interaction.followup.send('NOX a besoin de la permission Gérer les webhooks dans ce salon.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            ensure_presence(con)
            con.execute('''INSERT INTO nox_presence_config(guild_id, channel_id, enabled)
                VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET
                channel_id=excluded.channel_id, enabled=excluded.enabled''',
                (interaction.guild.id, salon.id, int(actif)))
            con.commit()
        await interaction.followup.send(
            f'🐾 Interventions de NOX {"activées" if actif else "suspendues"} dans {salon.mention}. '
            'NOX n’écrit que lorsqu’une jauge est basse, avec un lien vers son Refuge, '
            'au maximum une fois toutes les 6 heures et jamais entre 22 h et 9 h (Paris).',
            ephemeral=True)

    @tasks.loop(minutes=30)
    async def presence_loop(self):
        now = time.time()
        hour = datetime.now(ZoneInfo('Europe/Paris')).hour
        async with self.lock:
            with engine.connect(DB) as con:
                ensure_presence(con)
                configs = [dict(row) for row in con.execute('SELECT * FROM nox_presence_config WHERE enabled=1')]
                try:
                    life_posts = {r['guild_id']: r['last_post'] for r in con.execute('SELECT guild_id,last_post FROM nox_life_config')}
                except sqlite3.OperationalError:
                    life_posts = {}
            for config in configs:
                try:
                    with engine.connect(DB) as con:
                        state = engine.snapshot(con, config['guild_id'], now)
                    need = eligible(state, config, now, hour)
                    if not need or now - life_posts.get(config['guild_id'], 0) < 2 * 3600:
                        continue
                    channel = self.bot.get_channel(config['channel_id'])
                    if not isinstance(channel, discord.TextChannel):
                        continue
                    url = f'https://discord.com/channels/{config["guild_id"]}/{state["channel_id"]}/{state["message_id"]}'
                    message = f'{random.choice(NEEDS[need])}\n\n🐾 **[Venez m’aider dans mon Refuge !]({url})**'
                    # Un échec de publication ne consomme pas le délai anti-spam.
                    await send_as_nox(channel, content=message)
                    with engine.connect(DB) as con:
                        ensure_presence(con)
                        con.execute('''UPDATE nox_presence_config SET last_post=?, last_need=?, last_need_at=?
                            WHERE guild_id=?''', (now, need, now, config['guild_id']))
                        con.commit()
                except (discord.HTTPException, sqlite3.Error, OSError):
                    log.exception('Intervention de NOX impossible (serveur %s)', config['guild_id'])

    @presence_loop.before_loop
    async def before_presence(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NoxPresence(bot))

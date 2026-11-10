"""Vie spontanée de NOX : optionnelle, non intrusive, sans analyse des messages."""
from __future__ import annotations
import json
import logging
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR
from .nox_identity import send_as_nox
from .nox_refuge import DB
from . import nox_refuge_engine as engine

log = logging.getLogger(__name__)
DIALOGUES = Path(DATA_DIR) / 'nox' / 'dialogues_vie.json'
INTERVAL = 22 * 3600


def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS nox_life_config (
        guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 0,
        last_post REAL NOT NULL DEFAULT 0,
        last_dialogue TEXT NOT NULL DEFAULT '')""")
    con.commit()


def can_post(config, now, hour):
    return bool(config and config['enabled'] and 9 <= hour < 22
                and now - config['last_post'] >= INTERVAL)


class NoxLife(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.life_loop.start()

    def cog_unload(self):
        self.life_loop.cancel()

    async def noxvie(self, interaction: discord.Interaction, salon: discord.TextChannel, actif: bool):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or salon.guild.id != interaction.guild.id:
            await interaction.followup.send('Choisis un salon de ce serveur.', ephemeral=True)
            return
        me = interaction.guild.me
        if not me or not salon.permissions_for(me).manage_webhooks:
            await interaction.followup.send('Permission Gérer les webhooks manquante.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            ensure_table(con)
            con.execute("""INSERT INTO nox_life_config (guild_id, channel_id, enabled)
                VALUES (?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET
                channel_id=excluded.channel_id, enabled=excluded.enabled""",
                (interaction.guild.id, salon.id, int(actif)))
            con.commit()
        await interaction.followup.send(
            f'🐾 Vie spontanée de NOX {"activée" if actif else "désactivée"} dans {salon.mention}. '
            'Au maximum une intervention toutes les 22 heures, uniquement entre 9 h et 22 h (Paris).',
            ephemeral=True)

    @tasks.loop(hours=2)
    async def life_loop(self):
        now = time.time()
        hour = datetime.now(ZoneInfo('Europe/Paris')).hour
        with engine.connect(DB) as con:
            ensure_table(con)
            rows = [dict(r) for r in con.execute('SELECT * FROM nox_life_config WHERE enabled=1')]
            try:
                needs_posts = {r['guild_id']: r['last_post'] for r in con.execute('SELECT guild_id,last_post FROM nox_presence_config')}
            except sqlite3.OperationalError:
                needs_posts = {}
        if not rows:
            return
        try:
            dialogues = json.loads(DIALOGUES.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            log.exception('Catalogue NOX inaccessible')
            return
        for row in rows:
            if not can_post(row, now, hour) or now - needs_posts.get(row['guild_id'], 0) < 2 * 3600:
                continue
            channel = self.bot.get_channel(row['channel_id'])
            if not isinstance(channel, discord.TextChannel) or not dialogues:
                continue
            choices = [d for d in dialogues if d.get('id') != row['last_dialogue']]
            if not choices:
                choices = dialogues  # Un catalogue d'une seule réplique doit rester utilisable.
            item = random.choice(choices)
            try:
                await send_as_nox(channel, content=item['texte'])
            except (discord.HTTPException, OSError, ValueError):
                log.exception('NOX ne peut pas intervenir dans %s', row['channel_id'])
                continue
            with engine.connect(DB) as con:
                ensure_table(con)
                # Ne réactive jamais un réglage désactivé pendant la publication.
                con.execute("UPDATE nox_life_config SET last_post=?, last_dialogue=? WHERE guild_id=? AND enabled=1", (now, item['id'], row['guild_id']))
                con.commit()

    @life_loop.before_loop
    async def before_life(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NoxLife(bot))

"""Aventures participatives de NOX : une aventure active par serveur, votes persistants."""
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
BANK = Path(DATA_DIR) / 'nox' / 'aventures.json'
DURATION = 1800


def init_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS nox_adventures (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message_id INTEGER, scenario_id TEXT NOT NULL, opened_at REAL NOT NULL, closed_at REAL, result INTEGER)')
    con.execute('CREATE TABLE IF NOT EXISTS nox_adventure_votes (adventure_id INTEGER NOT NULL, user_id INTEGER NOT NULL, choice INTEGER NOT NULL, PRIMARY KEY(adventure_id,user_id))')


def active(con, guild_id):
    return con.execute('SELECT id,channel_id,message_id,scenario_id,opened_at FROM nox_adventures WHERE guild_id=? AND closed_at IS NULL ORDER BY id DESC LIMIT 1', (guild_id,)).fetchone()


class AdventureView(discord.ui.View):
    def __init__(self, cog, adventure_id, scenario):
        super().__init__(timeout=None)
        self.cog = cog
        self.adventure_id = adventure_id
        for idx, label in enumerate(scenario['choices']):
            button = discord.ui.Button(label=label[:80], style=discord.ButtonStyle.primary, custom_id=f'nox:adventure:{adventure_id}:{idx}', row=0)
            async def callback(interaction, selected=idx):
                await self.cog.vote(interaction, self.adventure_id, selected)
            button.callback = callback
            self.add_item(button)


class NoxAdventures(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scenarios = {x['id']: x for x in json.loads(BANK.read_text(encoding='utf-8'))}

    async def cog_load(self):
        with engine.connect(DB) as con:
            init_db(con)
            rows = con.execute('SELECT id,scenario_id FROM nox_adventures WHERE closed_at IS NULL').fetchall()
            con.commit()
        for adventure_id, scenario_id in rows:
            scenario = self.scenarios.get(scenario_id)
            if scenario:
                self.bot.add_view(AdventureView(self, adventure_id, scenario))

    async def vote(self, interaction: discord.Interaction, adventure_id: int, choice: int):
        if not interaction.guild or interaction.user.bot:
            await interaction.response.send_message('Vote réservé aux membres du serveur.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            init_db(con)
            row = con.execute('SELECT guild_id,opened_at,closed_at,scenario_id FROM nox_adventures WHERE id=?', (adventure_id,)).fetchone()
            if not row or row[0] != interaction.guild.id or row[2] is not None or time.time() - row[1] > DURATION:
                await interaction.response.send_message('Cette aventure est terminée. 🌙', ephemeral=True)
                return
            scenario = self.scenarios.get(row[3])
            if not scenario or choice not in range(len(scenario['choices'])):
                await interaction.response.send_message('Choix indisponible.', ephemeral=True)
                return
            con.execute('INSERT INTO nox_adventure_votes(adventure_id,user_id,choice) VALUES(?,?,?) ON CONFLICT(adventure_id,user_id) DO UPDATE SET choice=excluded.choice', (adventure_id, interaction.user.id, choice))
            con.commit()
        await interaction.response.send_message('🐾 NOX a enregistré ton choix ! Tu peux le modifier avant la fin.', ephemeral=True)

    async def noxaventure(self, interaction: discord.Interaction, action: app_commands.Choice[str], salon: discord.TextChannel | None = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        with engine.connect(DB) as con:
            init_db(con)
            current = active(con, guild.id)
        if action.value == 'conclure':
            if not current:
                await interaction.followup.send('Aucune aventure en cours.', ephemeral=True)
                return
            await self.finish(interaction, current)
            return
        if current:
            await interaction.followup.send('Une aventure est déjà en cours. Termine-la avec `/noxaventure conclure`.', ephemeral=True)
            return
        salon = salon or interaction.channel
        if not isinstance(salon, discord.TextChannel) or salon.guild.id != guild.id:
            await interaction.followup.send('Choisis un salon texte de ce serveur.', ephemeral=True)
            return
        perms = salon.permissions_for(guild.me)
        if not (perms.view_channel and perms.send_messages and perms.manage_webhooks):
            await interaction.followup.send('Permissions Voir le salon, Envoyer des messages et Gérer les webhooks nécessaires.', ephemeral=True)
            return
        scenario = random.choice(list(self.scenarios.values()))
        with engine.connect(DB) as con:
            init_db(con)
            cur = con.execute('INSERT INTO nox_adventures(guild_id,channel_id,scenario_id,opened_at) VALUES(?,?,?,?)', (guild.id, salon.id, scenario['id'], time.time()))
            adventure_id = cur.lastrowid
            con.commit()
        view = AdventureView(self, adventure_id, scenario)
        try:
            message = await send_as_nox(salon, content=scenario['intro'] + '\n\n🐾 **Choisissez la suite de mon aventure !** (30 minutes)', view=view, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            with engine.connect(DB) as con:
                con.execute('UPDATE nox_adventures SET closed_at=? WHERE id=?', (time.time(), adventure_id))
                con.commit()
            log.exception('Impossible de publier aventure NOX')
            await interaction.followup.send('Impossible de publier. Vérifie les permissions du salon.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            con.execute('UPDATE nox_adventures SET message_id=? WHERE id=?', (message.id, adventure_id))
            con.commit()
        await interaction.followup.send(f'🌌 Aventure lancée : {message.jump_url}', ephemeral=True)

    async def finish(self, interaction, current):
        adventure_id, channel_id, message_id, scenario_id, _ = current
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            await interaction.followup.send('Scénario introuvable.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            rows = con.execute('SELECT choice,COUNT(*) FROM nox_adventure_votes WHERE adventure_id=? GROUP BY choice ORDER BY COUNT(*) DESC,choice ASC', (adventure_id,)).fetchall()
            winner = rows[0][0] if rows else None
            cur = con.execute('UPDATE nox_adventures SET closed_at=?,result=? WHERE id=? AND closed_at IS NULL', (time.time(), winner, adventure_id))
            con.commit()
            if not cur.rowcount:
                await interaction.followup.send('Aventure déjà terminée.', ephemeral=True)
                return
        channel = interaction.guild.get_channel(channel_id)
        if channel is None:
            await interaction.followup.send('Aventure clôturée, mais salon introuvable.', ephemeral=True)
            return
        # Désactiver les boutons sur le message original lorsque Discord le permet.
        try:
            hooks = await channel.webhooks()
            hook = next((h for h in hooks if h.name == 'NOX' and h.user and h.user.id == interaction.guild.me.id), None)
            if hook and message_id:
                await hook.edit_message(message_id, view=None)
        except discord.HTTPException:
            log.warning('Impossible de retirer les boutons de l’aventure %s', adventure_id)
        total = sum(count for _, count in rows)
        outcome = scenario['results'][winner] if winner is not None else scenario['no_votes']
        try:
            posted = await send_as_nox(channel, content=f'🌟 **FIN DE L’AVENTURE !** ({total} participant(s))\n\n{outcome}', allowed_mentions=discord.AllowedMentions.none())
            await interaction.followup.send(f'Résultat publié : {posted.jump_url}', ephemeral=True)
        except discord.HTTPException:
            log.exception('Impossible de publier le résultat NOX %s', adventure_id)
            await interaction.followup.send('Aventure clôturée, mais publication du résultat impossible.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxAdventures(bot))

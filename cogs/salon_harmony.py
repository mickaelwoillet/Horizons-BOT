"""Harmonisation ciblée de salons existants, sans création de salon.

Les panneaux sont identifiés en SQLite et récupérés dans l'historique si besoin.
"""
from __future__ import annotations
import logging
import discord
from discord.ext import commands
from config import (GUILD_ID, AFFINITY_CHANNEL_ID, MOOD_CHANNEL_ID,
                    IDEAS_CHANNEL_ID, SOLIDARITY_CHANNEL_ID,
                    FIND_PARTNER_CHANNEL_ID, COLLECTIVE_CHALLENGES_CHANNEL_ID)
from .storage import db
from .embed_theme import wait_for_logo_ready

log = logging.getLogger(__name__)
# Identifiants constants : aucun salon ni permission n'est recréé.
NAMES = {
    AFFINITY_CHANNEL_ID: '🧩・connexions-du-ciel',
    MOOD_CHANNEL_ID: '💗・meteo-des-emotions',
    IDEAS_CHANNEL_ID: '💡・boite-a-idees',
    SOLIDARITY_CHANNEL_ID: '💜・eclats-de-reconnaissance',
    FIND_PARTNER_CHANNEL_ID: '🤝・activites-ensemble',
    COLLECTIVE_CHALLENGES_CHANNEL_ID: '🌟・defis-collectifs',
}

EXPLANATIONS = {
    FIND_PARTNER_CHANNEL_ID: (
        '🤝 Activités ensemble · Rencontres amicales',
        'Propose une activité ouverte aux autres membres : jeu, discussion ou moment convivial.\n\n'
        'Utilise le panneau **Que faire aujourd’hui ?** pour proposer une activité. '
        'Les membres intéressés peuvent répondre librement à une annonce.\n\n'
        'Aucune prise de contact privée automatique ; respecte le consentement et les règles du serveur.'
    ),
    COLLECTIVE_CHALLENGES_CHANNEL_ID: (
        '🌟 Défis collectifs · Ensemble, plus loin',
        'Participe aux défis communs d’HORIZONS à ton rythme.\n\n'
        'Les défis et les objectifs sont présentés ici ; suis les boutons des publications '
        'pour participer lorsque disponibles. Le panneau **Que faire aujourd’hui ?** '
        'propose aussi un petit défi quotidien.\n\n'
        'La participation est facultative et ne donne lieu à aucune compétition sociale.'
    ),
}

class SalonHarmony(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._done = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self._done:
            return
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        await wait_for_logo_ready()
        # Les salons sont renommés une seule fois par configuration souhaitée.
        # Aucun renommage de catégorie ou modification de permissions.
        for channel_id, desired in NAMES.items():
            if not channel_id:
                continue
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                log.warning('Harmonisation ignorée : salon textuel %s introuvable.', channel_id)
                continue
            if channel.name != desired:
                try:
                    await channel.edit(name=desired, reason='HORIZONS V7 : harmonisation des noms de salons')
                except (discord.Forbidden, discord.HTTPException):
                    log.exception('Impossible de renommer le salon %s.', channel_id)
            if channel_id in EXPLANATIONS:
                await self.ensure_panel(channel, *EXPLANATIONS[channel_id])
        self._done = True

    async def ensure_panel(self, channel: discord.TextChannel, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        embed.set_footer(text='HORIZONS • Panneau explicatif permanent')
        key = f'v7_harmony_panel_{channel.id}'
        with db() as conn:
            row = conn.execute('SELECT value FROM bot_settings WHERE key=?', (key,)).fetchone()
        message = None
        if row:
            try:
                message = await channel.fetch_message(int(row['value']))
                if message.author.id != self.bot.user.id:
                    message = None
            except (ValueError, TypeError, discord.NotFound):
                pass
            except (discord.Forbidden, discord.HTTPException):
                return
        if message is None:
            try:
                async for candidate in channel.history(limit=150):
                    if candidate.author.id == self.bot.user.id and any(e.title == title for e in candidate.embeds):
                        message = candidate
                        break
            except (discord.Forbidden, discord.HTTPException):
                return
        try:
            if message is None:
                message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            elif not message.embeds or message.embeds[0].to_dict() != embed.to_dict():
                await message.edit(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            log.exception('Panneau explicatif impossible dans %s.', channel.id)
            return
        with db() as conn:
            conn.execute('INSERT INTO bot_settings(key,value) VALUES(?,?) '
                         'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(message.id)))

async def setup(bot: commands.Bot):
    await bot.add_cog(SalonHarmony(bot))

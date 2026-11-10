"""Read-only daily schedule overview for HORIZONS administrators."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from .nox_daily_12 import SLOTS, SLOT_THEMES, ILLUSTRATED_SLOTS
from .nox_refuge import DB
from . import nox_refuge_engine as engine

PARIS = ZoneInfo('Europe/Paris')


def schedule_lines(rows):
    """Render fixed slots using only locally recorded delivery states."""
    states = {int(r['slot']): r['state'] for r in rows}
    lines = []
    for index, minute in enumerate(SLOTS):
        hour, minute_part = divmod(minute, 60)
        kind = ('🖼️ Illustration' if index in ILLUSTRATED_SLOTS else
                '🗳️ Sondage' if index in (1, 7) else
                '🌟 Défi' if index == 5 else
                '🌙 Bilan' if index == 11 else '💬 Texte')
        state = states.get(index)
        symbol = '✅' if state == 'sent' else '⚠️' if state else '▫️'
        lines.append(f'{symbol} **{hour:02d}h{minute_part:02d}** · {kind} · {SLOT_THEMES[index]}')
    return lines


class NoxPlanning(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxplanning(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message('Commande réservée aux serveurs.', ephemeral=True)
            return
        day = datetime.now(PARIS).date().isoformat()
        try:
            with engine.connect(DB) as con:
                # Read-only inspection: no reservation, scheduling or send side effect.
                config_exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nox_daily_config'").fetchone()
                posts_exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nox_daily_posts'").fetchone()
                config = (con.execute('SELECT channel_id,enabled FROM nox_daily_config WHERE guild_id=?', (interaction.guild.id,)).fetchone()
                          if config_exists else None)
                rows = (con.execute('SELECT slot,state FROM nox_daily_posts WHERE guild_id=? AND local_day=?',
                                    (interaction.guild.id, day)).fetchall() if posts_exists else [])
            status = 'activé' if config and config['enabled'] else 'désactivé'
            destination = f'<#{config["channel_id"]}>' if config else 'non configuré'
            content = (f'**🐾 Planning NOX — {day} (heure de Paris)**\n'
                       f'Programmateur : **{status}** · Salon : {destination}\n\n'
                       + '\n'.join(schedule_lines(rows))
                       + '\n\n▫️ Aucun envoi enregistré · ⚠️ Réservation non confirmée · ✅ Envoyé'
                       + '\n*Lecture seule : aucune publication ni réservation créée.*')
            await interaction.response.send_message(content, ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            await interaction.response.send_message('Impossible de lire le planning NOX. Vérifier les journaux.', ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxPlanning(bot))

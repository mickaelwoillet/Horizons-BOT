"""Mini-sondages NOX intégrés à deux publications quotidiennes, sans messages supplémentaires."""
from __future__ import annotations
import json
import logging
import random
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from config import DATA_DIR
from .nox_refuge import DB
from . import nox_refuge_engine as engine

LOG = logging.getLogger(__name__)
CATALOG = Path(DATA_DIR) / 'nox' / 'sondages_quotidiens.json'
PARIS = ZoneInfo('Europe/Paris')
POLL_SLOTS = frozenset((1, 7))


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_polls (
        guild_id INTEGER NOT NULL, local_day TEXT NOT NULL, slot INTEGER NOT NULL,
        poll_id TEXT NOT NULL, message_id INTEGER,
        PRIMARY KEY(guild_id,local_day,slot))''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_poll_votes (
        guild_id INTEGER NOT NULL, local_day TEXT NOT NULL, slot INTEGER NOT NULL,
        user_id INTEGER NOT NULL, choice INTEGER NOT NULL,
        PRIMARY KEY(guild_id,local_day,slot,user_id))''')
    con.commit()


def load_catalog():
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(data, list) or not data:
        raise ValueError('Catalogue de sondages vide')
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('question'), str):
            raise ValueError('Sondage mal formé')
        if not isinstance(item.get('choix'), list) or len(item['choix']) != 3 or any(not isinstance(c, str) or len(c) > 80 for c in item['choix']):
            raise ValueError('Chaque sondage exige exactement trois choix de 80 caractères maximum')
    return data


def select_poll(con, guild_id, day, slot):
    initialize(con)
    existing = con.execute('SELECT poll_id FROM nox_daily_polls WHERE guild_id=? AND local_day=? AND slot=?',
                           (guild_id, day, slot)).fetchone()
    catalog = load_catalog()
    if existing:
        return next((p for p in catalog if p['id'] == existing[0]), None)
    recent = {r[0] for r in con.execute('''SELECT poll_id FROM nox_daily_polls
        WHERE guild_id=? ORDER BY local_day DESC,slot DESC LIMIT 8''', (guild_id,))}
    pool = [p for p in catalog if p['id'] not in recent] or catalog
    chosen = random.choice(pool)
    con.execute('INSERT OR IGNORE INTO nox_daily_polls(guild_id,local_day,slot,poll_id) VALUES(?,?,?,?)',
                (guild_id, day, slot, chosen['id']))
    con.commit()
    return chosen


class VoteButton(discord.ui.Button):
    def __init__(self, choice: int):
        super().__init__(label=('🌟 Option A', '🚀 Option B', '💛 Option C')[choice],
                         style=discord.ButtonStyle.secondary,
                         custom_id=f'horizons:nox:sondage:{choice}')
        self.choice = choice

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.message:
            await interaction.response.send_message('Ce sondage n’est plus accessible.', ephemeral=True)
            return
        now = datetime.now(PARIS)
        with engine.connect(DB) as con:
            initialize(con)
            row = con.execute('''SELECT local_day,slot,poll_id FROM nox_daily_polls
                WHERE guild_id=? AND message_id=?''',
                (interaction.guild.id, interaction.message.id)).fetchone()
            if not row:
                await interaction.response.send_message('Sondage introuvable.', ephemeral=True)
                return
            day, slot, poll_id = row
            if day != now.date().isoformat() or now.hour >= 23:
                await interaction.response.send_message('Ce sondage est terminé. À demain ! 🐾', ephemeral=True)
                return
            con.execute('''INSERT INTO nox_daily_poll_votes(guild_id,local_day,slot,user_id,choice)
                VALUES(?,?,?,?,?) ON CONFLICT(guild_id,local_day,slot,user_id)
                DO UPDATE SET choice=excluded.choice''',
                (interaction.guild.id, day, slot, interaction.user.id, self.choice))
            con.commit()
            totals = [0, 0, 0]
            for r in con.execute('''SELECT choice,COUNT(*) FROM nox_daily_poll_votes
                WHERE guild_id=? AND local_day=? AND slot=? GROUP BY choice''',
                (interaction.guild.id, day, slot)):
                totals[r[0]] = r[1]
        try:
            poll = next(p for p in load_catalog() if p['id'] == poll_id)
            answer = poll['choix'][self.choice]
        except (OSError, ValueError, StopIteration, KeyError):
            answer = f'Option {self.choice + 1}'
        await interaction.response.send_message(
            f'🐾 NOX a enregistré ton choix : **{answer}** !\n'
            f'Résultats provisoires : A **{totals[0]}** · B **{totals[1]}** · C **{totals[2]}**. '
            'Tu peux changer ton vote jusqu’à 23 h.', ephemeral=True)


class PollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(3):
            self.add_item(VoteButton(i))


class NoxDailyPolls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(PollView())


async def setup(bot):
    await bot.add_cog(NoxDailyPolls(bot))

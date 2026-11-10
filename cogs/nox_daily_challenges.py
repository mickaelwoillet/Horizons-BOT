"""Défi participatif quotidien : un créneau existant, un clic par membre."""
from __future__ import annotations
import json
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands
from config import DATA_DIR
from .nox_refuge import DB
from . import nox_refuge_engine as engine

CATALOG = Path(DATA_DIR) / 'nox' / 'defis_quotidiens.json'
PARIS = ZoneInfo('Europe/Paris')
CHALLENGE_SLOT = 5  # 15 h 50 : remplace le défi textuel


def init_db(con):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_challenges (
        guild_id INTEGER NOT NULL, local_day TEXT NOT NULL, slot INTEGER NOT NULL,
        challenge_id TEXT NOT NULL, message_id INTEGER,
        PRIMARY KEY(guild_id,local_day,slot))''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_daily_challenge_members (
        guild_id INTEGER NOT NULL, local_day TEXT NOT NULL, slot INTEGER NOT NULL,
        user_id INTEGER NOT NULL, joined_at TEXT NOT NULL,
        PRIMARY KEY(guild_id,local_day,slot,user_id))''')
    con.commit()


def catalog():
    entries = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(entries, list) or not entries:
        raise ValueError('Défis quotidiens absents')
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('texte'), str) or not (1 <= len(item['texte']) <= 1700):
            raise ValueError('Défi quotidien invalide')
    return entries


def select_challenge(con, guild_id, day, slot=CHALLENGE_SLOT):
    init_db(con)
    existing = con.execute('SELECT challenge_id FROM nox_daily_challenges WHERE guild_id=? AND local_day=? AND slot=?', (guild_id, day, slot)).fetchone()
    entries = catalog()
    if existing:
        return next((x for x in entries if x['id'] == existing[0]), None)
    recent = {r[0] for r in con.execute('SELECT challenge_id FROM nox_daily_challenges WHERE guild_id=? ORDER BY local_day DESC LIMIT 8', (guild_id,))}
    pool = [x for x in entries if x['id'] not in recent] or entries
    item = random.choice(pool)
    con.execute('INSERT OR IGNORE INTO nox_daily_challenges(guild_id,local_day,slot,challenge_id) VALUES(?,?,?,?)', (guild_id,day,slot,item['id']))
    con.commit()
    return item


class JoinChallenge(discord.ui.Button):
    def __init__(self):
        super().__init__(label='🌟 Je relève le défi !', style=discord.ButtonStyle.success, custom_id='horizons:nox:defi:participer')

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.message or interaction.user.bot:
            await interaction.response.send_message('Participation réservée aux membres.', ephemeral=True)
            return
        now = datetime.now(PARIS)
        with engine.connect(DB) as con:
            init_db(con)
            row = con.execute('SELECT local_day,slot FROM nox_daily_challenges WHERE guild_id=? AND message_id=?', (interaction.guild.id, interaction.message.id)).fetchone()
            if not row or row[0] != now.date().isoformat() or now.hour >= 23:
                await interaction.response.send_message('Ce défi est terminé. Reviens demain ! 🌙', ephemeral=True)
                return
            cur = con.execute('INSERT OR IGNORE INTO nox_daily_challenge_members(guild_id,local_day,slot,user_id,joined_at) VALUES(?,?,?,?,?)', (interaction.guild.id,row[0],row[1],interaction.user.id,now.isoformat()))
            total = con.execute('SELECT COUNT(*) FROM nox_daily_challenge_members WHERE guild_id=? AND local_day=? AND slot=?', (interaction.guild.id,row[0],row[1])).fetchone()[0]
            con.commit()
        if cur.rowcount:
            from .nox_collective_celebrations import participation_reply
            reply = participation_reply(total)
        else:
            reply = f'🐾 Tu participes déjà ! **{total}** membres ont rejoint le défi aujourd’hui.'
        await interaction.response.send_message(reply, ephemeral=True)


class ChallengeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(JoinChallenge())


class NoxDailyChallenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(ChallengeView())


async def setup(bot):
    await bot.add_cog(NoxDailyChallenges(bot))

"""Rare, bounded NOX reactions to direct replies to scheduled posts.

Does not read or analyze the reply text; only Discord reply references are used.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from .nox_identity import send_as_nox
from .nox_refuge import DB
from . import nox_refuge_engine as engine

LOG = logging.getLogger(__name__)
PARIS = ZoneInfo('Europe/Paris')
REPLIES = (
    'J’ai vu ta réponse ! Mon antenne à gentillesse vient de faire *bip*. 💛',
    'Une participation de plus dans mon carnet cosmique ! Je note ça avec une patte pleine de miettes. 🍪',
    'Je voulais répondre avec beaucoup de sérieux, mais Coincoin a volé mon stylo. 🦆',
    'Merci d’avoir joué le jeu ! Mon vaisseau vient de gagner un sourire. 🚀',
    'Ooooh, quelqu’un a répondu ! Je fais ma danse des petites étoiles. ✨',
    'J’adore quand les habitants d’HORIZONS donnent vie à mes idées. 🫶',
    'Message reçu cinq sur cinq, capitaine ! Enfin… plutôt quatre sur cinq, j’ai mangé le cinquième. 🍪',
    'Je garde cette belle énergie pour ma prochaine aventure. 🌟',
    'C’est officiellement un petit moment de vie cosmique. Merci ! 💫',
    'Ma boîte à sourires vient de se remplir un peu plus. 💛',
    'Je transmets ta participation au conseil des chaussettes interstellaires. 🧦',
    'Mon radar détecte une présence sympathique. C’est toi ! 🐾',
)


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_interaction_posts (
        guild_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL, day TEXT NOT NULL,
        PRIMARY KEY (guild_id, message_id))''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_interaction_replies (
        guild_id INTEGER NOT NULL, day TEXT NOT NULL, user_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL, replied_at INTEGER NOT NULL,
        PRIMARY KEY (guild_id, day, user_id))''')
    con.execute('''CREATE INDEX IF NOT EXISTS idx_nox_interactions_day
        ON nox_interaction_replies(guild_id, day)''')
    con.commit()


def record_post(guild_id: int, channel_id: int, message_id: int, day: str):
    with engine.connect(DB) as con:
        initialize(con)
        con.execute('''INSERT OR IGNORE INTO nox_interaction_posts
            (guild_id,message_id,channel_id,day) VALUES(?,?,?,?)''',
            (guild_id, message_id, channel_id, day))
        con.execute('''DELETE FROM nox_interaction_posts
            WHERE guild_id=? AND day < ?''', (guild_id, day))
        con.commit()


def reserve_reply(con, guild_id, day, user_id, message_id, now):
    """Max 3 responses/guild/day, one/user/day, at least 20min apart."""
    total, latest = con.execute('''SELECT COUNT(*), MAX(replied_at)
        FROM nox_interaction_replies WHERE guild_id=? AND day=?''',
        (guild_id, day)).fetchone()
    if total >= 3 or (latest is not None and now - latest < 1200):
        return False
    cur = con.execute('''INSERT OR IGNORE INTO nox_interaction_replies
        (guild_id,day,user_id,message_id,replied_at) VALUES(?,?,?,?,?)''',
        (guild_id, day, user_id, message_id, now))
    con.commit()
    return bool(cur.rowcount)


class NoxInteractions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.webhook_id:
            return
        if not message.reference or not message.reference.message_id:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        now = datetime.now(PARIS)
        if not (10 <= now.hour < 23):
            return
        day = now.date().isoformat()
        with engine.connect(DB) as con:
            initialize(con)
            row = con.execute('''SELECT 1 FROM nox_interaction_posts
                WHERE guild_id=? AND channel_id=? AND message_id=? AND day=?''',
                (message.guild.id, message.channel.id, message.reference.message_id, day)).fetchone()
            if not row or random.random() >= 0.35:
                return
            if not reserve_reply(con, message.guild.id, day, message.author.id,
                                 message.id, int(now.timestamp())):
                return
        try:
            await send_as_nox(message.channel, content=random.choice(REPLIES))
        except (discord.Forbidden, discord.HTTPException):
            LOG.exception('NOX n’a pas pu réagir dans %s', message.channel.id)


async def setup(bot):
    await bot.add_cog(NoxInteractions(bot))

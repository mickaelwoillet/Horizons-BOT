"""Réactions événementielles de NOX, opt-in, sans second bot.

Les anniversaires remplacent le message classique lorsqu'ils sont activés.
Les quiz conservent leur classement et ajoutent au plus une réaction par session.
"""
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
BANK = Path(DATA_DIR) / 'nox' / 'reactions_evenements.json'

def ensure(con):
    con.execute('''CREATE TABLE IF NOT EXISTS nox_event_config (
        guild_id INTEGER PRIMARY KEY, birthdays INTEGER NOT NULL DEFAULT 0,
        quizzes INTEGER NOT NULL DEFAULT 0)''')
    con.execute('''CREATE TABLE IF NOT EXISTS nox_event_posts (
        guild_id INTEGER NOT NULL, event_key TEXT NOT NULL,
        created_at REAL NOT NULL, PRIMARY KEY(guild_id,event_key))''')
    con.commit()

def enabled(guild_id: int, kind: str) -> bool:
    if kind not in ('birthdays', 'quizzes'): return False
    with engine.connect(DB) as con:
        ensure(con)
        row = con.execute('SELECT birthdays, quizzes FROM nox_event_config WHERE guild_id=?', (guild_id,)).fetchone()
        return bool(row and row[kind])

def choose(kind: str) -> str:
    data = json.loads(BANK.read_text(encoding='utf-8'))
    return random.choice(data[kind])

async def birthday(channel: discord.TextChannel, member: discord.Member, age_text: str) -> bool:
    """True uniquement si l'annonce NOX a été effectivement publiée."""
    if not enabled(channel.guild.id, 'birthdays'): return False
    try:
        content = choose('birthdays').replace('{membre}', member.mention).replace('{age}', age_text)
        await send_as_nox(channel, content=content,
                          allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False))
        return True
    except (discord.HTTPException, OSError, ValueError, KeyError):
        log.exception('Accueil anniversaire NOX indisponible; annonce classique conservée')
        return False

async def quiz(channel: discord.TextChannel, session_id: str, winner: int | None) -> bool:
    if not enabled(channel.guild.id, 'quizzes'): return False
    key = 'quiz:' + session_id
    now = time.time()
    with engine.connect(DB) as con:
        ensure(con)
        # Réservation atomique pour empêcher deux publications simultanées.
        cur = con.execute('INSERT OR IGNORE INTO nox_event_posts VALUES (?,?,?)',
                          (channel.guild.id, key, now))
        con.commit()
        if not cur.rowcount: return False
    try:
        text = choose('quizzes').replace('{gagnant}', f'<@{winner}>' if winner else 'les participants')
        await send_as_nox(channel, content=text,
                          allowed_mentions=discord.AllowedMentions.none())
        return True
    except (discord.HTTPException, OSError, ValueError, KeyError):
        with engine.connect(DB) as con:
            con.execute('DELETE FROM nox_event_posts WHERE guild_id=? AND event_key=?', (channel.guild.id, key))
            con.commit()
        log.exception('Réaction NOX quiz impossible')
        return False

class NoxEvents(commands.Cog):
    def __init__(self, bot): self.bot = bot

    async def noxevenements(self, interaction: discord.Interaction, anniversaires: bool, quiz: bool):
        with engine.connect(DB) as con:
            ensure(con)
            con.execute('''INSERT INTO nox_event_config(guild_id,birthdays,quizzes) VALUES(?,?,?)
                ON CONFLICT(guild_id) DO UPDATE SET birthdays=excluded.birthdays, quizzes=excluded.quizzes''',
                (interaction.guild_id, int(anniversaires), int(quiz)))
            con.commit()
        await interaction.response.send_message(
            f'🐾 NOX : anniversaires {"activés" if anniversaires else "désactivés"} · '
            f'quiz {"activés" if quiz else "désactivés"}. Aucun doublon d’annonce anniversaire.', ephemeral=True)

async def setup(bot): await bot.add_cog(NoxEvents(bot))

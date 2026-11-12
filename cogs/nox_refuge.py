"""Refuge collectif NOX: panneau unique persistant et alertes modérées."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR
from . import nox_refuge_engine as engine
from .nox_memory import milestone_reply

log = logging.getLogger(__name__)
DB = Path(DATA_DIR) / 'nox_refuge.sqlite3'
ACTIONS = [('🍕 Nourrir', 'nourrir'), ('💧 Donner à boire', 'boire'),
           ('🎮 Jouer', 'jouer'), ('💛 Câlin', 'calin'),
           ('🛁 Bain', 'bain'), ('💤 Repos', 'repos')]
LABELS = {'faim':'Faim', 'soif':'Soif', 'bonheur':'Bonheur', 'energie':'Énergie', 'hygiene':'Hygiène'}
NEEDS = {
 'faim': ['Mon ventre fait un bruit de trou noir. À l’aide ! 🍕', 'Je viens de regarder une planète comme une pizza. C’est grave ?'],
 'soif': ['Un petit verre de comète fraîche, s’il vous plaît ! 💧', 'Je crois que mon dernier verre d’eau était une illusion cosmique.'],
 'bonheur': ['J’ai besoin d’un câlin intergalactique. C’est très officiel. 💛'],
 'energie': ['Mes paupières pèsent trois galaxies. Une sieste ? 💤'],
 'hygiene': ['J’ai des poussières d’étoiles jusque dans les oreilles. 🛁'],
}

REACTIONS_FILE = Path(DATA_DIR) / 'nox' / 'reactions_soins.json'
IMAGE_DIR = Path(DATA_DIR) / 'nox_tv'
# Images officielles du NOX bleu, par besoin et par niveau de jauge.
# Priorité à la jauge la plus basse, avec un seuil d'alerte à 45 %.
NEED_IMAGES = {
    'faim': 'nox_faim.png',
    'soif': 'nox_soif_cosmique_40.png',
    'bonheur': 'nox_tristesse_41.png',
    'energie': 'nox_fatigue_41.png',
    'hygiene': 'nox_refuge_coussins.png',
}
DECOR_IMAGE_NAMES = tuple(f'nox_refuge_evolutif_{level}.png' for level in range(5))

CARE_IMAGES = {
    'nourrir': 'nox_refuge_nourrir.png',
    'boire': 'nox_soif_cosmique_40.png',
    'jouer': 'nox_jeu_orbe_40.png',
    'calin': 'nox_reconfort_41.png',
    'bain': 'nox_refuge_bain.png',
    'repos': 'nox_bonne_nuit_couverture_40.png',
}

def choose_refuge_image(state, last_action=None, decorations=0):
    """Choisit une scène cohérente avec les besoins, sans état aléatoire."""
    stats = state['stats']
    weakest = min(engine.STATS, key=lambda key: stats[key])
    if stats[weakest] < 45:
        # Une image du besoin urgent prévaut sur le soin effectué.
        name = NEED_IMAGES[weakest]
    elif last_action in CARE_IMAGES:
        name = CARE_IMAGES[last_action]
    elif min(stats.values()) < 70:
        name = 'nox_refuge_coussins.png'
    else:
        name = DECOR_IMAGE_NAMES[max(0, min(4, int(decorations)))]
    file_path = IMAGE_DIR / name
    if file_path.is_file():
        return file_path
    fallback = IMAGE_DIR / 'nox_refuge_coussins.png'
    return fallback if fallback.is_file() else None

def refuge_embed_and_file(state, last_action=None):
    """Associe l'image au message Discord (attachment://) sans URL externe."""
    embed = make_embed(state)
    try:
        _, found = refuge_discoveries(state['guild_id'])
        decorations = len(found)
    except (sqlite3.Error, OSError):
        decorations = 0
    path = choose_refuge_image(state, last_action, decorations)
    if path is None:
        return embed, None
    embed.set_image(url=f'attachment://{path.name}')
    return embed, discord.File(str(path), filename=path.name)


def care_reply(action: str) -> str:
    """Choisit une réaction locale ; jamais de mention ni de publication supplémentaire."""
    try:
        bank = json.loads(REACTIONS_FILE.read_text(encoding='utf-8'))
        choices = bank.get(action, [])
        if choices:
            return random.choice(choices)
    except (OSError, ValueError, TypeError):
        log.warning('Réactions NOX indisponibles, réponse de secours utilisée')
    return '💛 NOX a apprécié ton attention ! Merci de prendre soin de lui.'

def refuge_cycle(hour):
    """Rythme parisien informatif : ne bloque jamais les soins."""
    if 23 <= hour or hour < 7:
        return '🌙 Nuit cosmique · NOX somnole, les soins restent possibles'
    if hour < 10:
        return '🌅 Réveil · NOX découvre la nouvelle journée'
    if hour < 18:
        return '☀️ Exploration · NOX est curieux et joueur'
    return '✨ Soirée · NOX ralentit et retrouve son Refuge'


def refuge_discoveries(guild_id):
    """Décorations déverrouillées à partir des soins existants, sans XP ni nouvelle table."""
    from .nox_memory import memory_summary
    with engine.connect(DB) as con:
        total = memory_summary(con, guild_id)['total_care']
    unlocks = [(5, '🛏️ Coussin d’étoiles'), (20, '🪔 Lanterne cosmique'),
               (50, '🧸 Peluche galactique'), (100, '🌌 Jardin de constellations')]
    found = [label for threshold, label in unlocks if total >= threshold]
    return total, found


def make_embed(s):
    v=s['stats']; low=s['needs']; mood=s['mood']
    lines=[]
    for key in engine.STATS:
        value=round(v[key]); filled=max(0,min(10,round(value/10)))
        lines.append(f'**{LABELS[key]}**  `{value:3d}%`  '+ '▰'*filled+'▱'*(10-filled))
    if low:
        speech=NEEDS[low[0]][0]
    else:
        speech='Je surveille ma galaxie… et surtout vos biscuits ! ✨' if mood=='heureux' else 'Tout va bien, mais un câlin ne se refuse jamais ! 💛'
    e=discord.Embed(title='🐾 Le Refuge de NOX',description='\n'.join(lines)+'\n\n💬 **NOX :** « '+speech+' »',color=0xD6AD55)
    e.add_field(name='Humeur',value={'heureux':'🌟 Heureux','calme':'🙂 Tranquille','besoin':'🥺 A besoin de vous','fatigue':'😴 Fatigué'}.get(mood,mood))
    hour = datetime.now(ZoneInfo('Europe/Paris')).hour
    e.add_field(name='🕰️ Cycle de vie', value=refuge_cycle(hour), inline=False)
    # Les découvertes sont calculées à partir des contributions déjà enregistrées.
    try:
        total, found = refuge_discoveries(s['guild_id'])
        e.add_field(name='🏡 Refuge évolutif',
                    value=f'{total} soins collectifs · '+(', '.join(found) if found else 'Première décoration à 5 soins'),
                    inline=False)
    except (sqlite3.Error, OSError):
        log.warning('Décorations NOX temporairement indisponibles', exc_info=True)
    e.set_footer(text='Un seul NOX · Soins avec délai de 30 min par action · Découvertes collectives')
    return e

class CareButton(discord.ui.Button):
    def __init__(self, label, action, row):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id='horizons:nox_refuge:'+action, row=row)
        self.action=action
    async def callback(self, interaction:discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog=interaction.client.get_cog('NoxRefuge')
        if not cog or not interaction.guild:
            await interaction.followup.send('Refuge indisponible.',ephemeral=True);return
        try:
            async with cog.lock:
                with engine.connect(DB) as con:
                    result=engine.perform(con,interaction.guild.id,interaction.user.id,self.action)
            if not result['ok']:
                mins=max(1,(result['remaining_seconds']+59)//60)
                await interaction.followup.send(f'🐾 NOX te remercie ! Tu pourras refaire ce soin dans {mins} min.',ephemeral=True)
                return
            await cog.refresh(interaction.guild.id, last_action=self.action)
            with engine.connect(DB) as con:
                row = con.execute('SELECT count FROM nox_refuge_contributions WHERE guild_id=? AND user_id=? AND action=?',
                                  (interaction.guild.id, interaction.user.id, self.action)).fetchone()
            # Synchronise les distinctions après un soin réussi ; l'échec ne bloque pas le Refuge.
            try:
                from .nox_honors_roles import sync_member
                if isinstance(interaction.user, discord.Member):
                    await sync_member(interaction.user)
            except Exception:
                log.exception("Synchronisation des rôles NOX impossible")
            special = milestone_reply(self.action, row['count']) if row else None
            await interaction.followup.send(special or care_reply(self.action), ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        except Exception:
            log.exception('Soin NOX impossible')
            await interaction.followup.send('Une erreur a empêché le soin. Réessaie plus tard.',ephemeral=True)

class RefugeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for index,(label,action) in enumerate(ACTIONS):
            self.add_item(CareButton(label,action,index//3))

class NoxRefuge(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        self.lock=asyncio.Lock()
        self.refresh_loop.start()
    async def cog_load(self):
        self.bot.add_view(RefugeView())
    def cog_unload(self):
        self.refresh_loop.cancel()
    async def refresh(self,guild_id, last_action=None):
        with engine.connect(DB) as con:
            s=engine.snapshot(con,guild_id)
        if not s['channel_id'] or not s['message_id']:return
        channel=self.bot.get_channel(s['channel_id'])
        if channel is None:
            try: channel=await self.bot.fetch_channel(s['channel_id'])
            except (discord.HTTPException,discord.Forbidden):return
        try:
            msg=await channel.fetch_message(s['message_id'])
            embed, image = refuge_embed_and_file(s, last_action)
            kwargs = dict(embed=embed, view=RefugeView(),
                          allowed_mentions=discord.AllowedMentions.none())
            if image is not None:
                kwargs['attachments'] = [image]
            await msg.edit(**kwargs)
        except (discord.HTTPException,discord.Forbidden):log.warning('Panneau Refuge introuvable ou non modifiable: %s',guild_id)
    @app_commands.command(name='noxrefuge',description='Installer ou retrouver le panneau du Refuge de NOX')
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(salon='Salon dédié au Refuge de NOX')
    async def noxrefuge(self,interaction:discord.Interaction,salon:discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or salon.guild.id!=interaction.guild.id:return
        me=interaction.guild.me
        perms=salon.permissions_for(me)
        if not (perms.send_messages and perms.embed_links and perms.read_message_history):
            await interaction.followup.send('Permissions insuffisantes dans ce salon (écrire, embeds, historique).',ephemeral=True);return
        async with self.lock:
            with engine.connect(DB) as con:
                previous=engine.snapshot(con,interaction.guild.id)
            if previous['message_id']:
                if previous['channel_id']==salon.id:
                    try:
                        msg=await salon.fetch_message(previous['message_id'])
                        embed, image = refuge_embed_and_file(previous)
                        kwargs = dict(embed=embed, view=RefugeView(),
                                      allowed_mentions=discord.AllowedMentions.none())
                        if image is not None:
                            kwargs['attachments'] = [image]
                        await msg.edit(**kwargs)
                        await interaction.followup.send(f'🐾 Panneau déjà installé : {msg.jump_url}',ephemeral=True);return
                    except discord.NotFound:pass
                else:
                    await interaction.followup.send('Un Refuge est déjà configuré dans un autre salon. Contacte le responsable avant de le déplacer.',ephemeral=True);return
            embed, image = refuge_embed_and_file(previous)
            kwargs = dict(embed=embed, view=RefugeView(),
                          allowed_mentions=discord.AllowedMentions.none())
            if image is not None:
                kwargs['file'] = image
            msg=await salon.send(**kwargs)
            with engine.connect(DB) as con:engine.set_panel(con,interaction.guild.id,salon.id,msg.id)
        await interaction.followup.send(f'🐾 Refuge installé : {msg.jump_url}\nÉpingle ce message pour le retrouver facilement.',ephemeral=True)
    @tasks.loop(minutes=15)
    async def refresh_loop(self):
        try:
            with engine.connect(DB) as con:
                rows=con.execute('SELECT guild_id FROM nox_refuge_state WHERE message_id IS NOT NULL').fetchall()
            for row in rows:
                async with self.lock:
                    await self.refresh(row['guild_id'])
        except Exception:log.exception('Actualisation du Refuge impossible')
    @refresh_loop.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(NoxRefuge(bot))

"""Missions coopératives de NOX, votes et progression persistants."""
from __future__ import annotations
import logging
import random
import time
import discord
from discord import app_commands
from discord.ext import commands
from .nox_refuge import DB
from . import nox_refuge_engine as engine
from .nox_identity import send_as_nox

LOG = logging.getLogger(__name__)
MISSIONS = (
    ('chaussettes', '🧦 ALERTE ! Mes chaussettes ont fondé une république indépendante. Aidez-moi à négocier avant qu’elles réclament la Lune !', 'Les chaussettes acceptent un traité de paix. Elles exigent seulement une lessive hebdomadaire.'),
    ('vaisseau', '🚀 Mon vaisseau refuse de démarrer. Il dit qu’il a besoin de compliments. Je crois que j’ai inventé le premier moteur susceptible.', 'Le vaisseau ronronne de bonheur et décolle. Il nous a demandé de ne plus le traiter de grille-pain.'),
    ('etoiles', '✨ J’ai renversé mon bocal d’étoiles. Il y en a partout ! Vite, une équipe de ramassage cosmique !', 'Toutes les étoiles sont récupérées. Sauf une. Elle s’est installée dans mon oreiller.'),
    ('biscuit', '🍪 Le grand biscuit orbital menace de s’écraser sur ma cuisine. Nous devons le sauver ! Enfin… surtout la cuisine.', 'Mission accomplie ! Le biscuit est sauf. La cuisine, elle, sent désormais la vanille intergalactique.'),
    ('doudou', '🧸 Mon doudou a été aspiré par un mini-trou noir. Je fais semblant d’être courageux, mais je renifle très fort.', 'Mon doudou est de retour ! Il a visité trois galaxies et refuse désormais de dormir sans passeport.'),
    ('mardi', '📅 Quelqu’un a volé le mardi. Je l’avais pourtant rangé entre lundi et mercredi !', 'Le mardi a été retrouvé derrière Saturne. Il prétend avoir pris des vacances.'),
)
TARGET = 12
DURATION = 3600


def init_db(con):
    con.execute('CREATE TABLE IF NOT EXISTS nox_cosmic_missions (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message_id INTEGER, mission_key TEXT NOT NULL, opened_at REAL NOT NULL, closed_at REAL, success INTEGER)')
    con.execute('CREATE TABLE IF NOT EXISTS nox_cosmic_helpers (mission_id INTEGER NOT NULL, user_id INTEGER NOT NULL, helped_at REAL NOT NULL, PRIMARY KEY(mission_id,user_id))')


def current(con, guild_id):
    return con.execute('SELECT id,channel_id,message_id,mission_key,opened_at FROM nox_cosmic_missions WHERE guild_id=? AND closed_at IS NULL ORDER BY id DESC LIMIT 1', (guild_id,)).fetchone()


class HelpView(discord.ui.View):
    def __init__(self, cog, mission_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.mission_id = mission_id

    @discord.ui.button(label='🤝 Aider NOX', style=discord.ButtonStyle.success, custom_id='nox:mission:placeholder')
    async def placeholder(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.help(interaction, self.mission_id)

    # custom_id doit être unique par mission pour restaurer plusieurs vues après redémarrage.
    def configure(self):
        self.children[0].custom_id = f'nox:mission:{self.mission_id}'
        return self


class NoxCosmicMissions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        with engine.connect(DB) as con:
            init_db(con)
            rows = con.execute('SELECT id FROM nox_cosmic_missions WHERE closed_at IS NULL').fetchall()
            con.commit()
        for row in rows:
            self.bot.add_view(HelpView(self, row[0]).configure())

    async def help(self, interaction: discord.Interaction, mission_id: int):
        if not interaction.guild or interaction.user.bot:
            await interaction.response.send_message('Participation réservée aux membres.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            init_db(con)
            row = con.execute('SELECT guild_id,opened_at,closed_at FROM nox_cosmic_missions WHERE id=?', (mission_id,)).fetchone()
            if not row or row[0] != interaction.guild.id or row[2] is not None or time.time() - row[1] > DURATION:
                await interaction.response.send_message('Cette mission est terminée. 🌙', ephemeral=True)
                return
            cursor = con.execute('INSERT OR IGNORE INTO nox_cosmic_helpers(mission_id,user_id,helped_at) VALUES(?,?,?)', (mission_id, interaction.user.id, time.time()))
            count = con.execute('SELECT COUNT(*) FROM nox_cosmic_helpers WHERE mission_id=?', (mission_id,)).fetchone()[0]
            con.commit()
        if not cursor.rowcount:
            await interaction.response.send_message(f'Ton aide est déjà comptée ! 💛 ({count}/{TARGET})', ephemeral=True)
        else:
            await interaction.response.send_message(f'Merci ! NOX a reçu ton aide. 🐾 ({count}/{TARGET})', ephemeral=True)

    async def noxmission(self, interaction: discord.Interaction, action: app_commands.Choice[str], salon: discord.TextChannel | None = None):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        with engine.connect(DB) as con:
            init_db(con)
            row = current(con, guild.id)
        if action.value == 'conclure':
            if not row:
                await interaction.followup.send('Aucune mission en cours.', ephemeral=True)
                return
            mission_id, channel_id, message_id, key, opened = row
            with engine.connect(DB) as con:
                count = con.execute('SELECT COUNT(*) FROM nox_cosmic_helpers WHERE mission_id=?', (mission_id,)).fetchone()[0]
                success = int(count >= TARGET)
                changed = con.execute('UPDATE nox_cosmic_missions SET closed_at=?,success=? WHERE id=? AND closed_at IS NULL', (time.time(), success, mission_id)).rowcount
                con.commit()
            if not changed:
                await interaction.followup.send('Mission déjà terminée.', ephemeral=True)
                return
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    hooks = await channel.webhooks()
                    hook = next((h for h in hooks if h.name == 'NOX' and h.user and h.user.id == guild.me.id), None)
                    if hook and message_id:
                        await hook.edit_message(message_id, view=None)
                except discord.HTTPException:
                    LOG.warning('Boutons de mission non retirés : %s', mission_id)
                result = next(m[2] for m in MISSIONS if m[0] == key) if success else 'Mission inachevée… Je vais mettre un panneau « revenez demain » sur la catastrophe. 🐾'
                try:
                    await send_as_nox(channel, content=f'🌌 **BILAN DE MISSION** — {count}/{TARGET} participants\n\n{result}', allowed_mentions=discord.AllowedMentions.none())
                except discord.HTTPException:
                    await interaction.followup.send('Mission clôturée, mais publication du bilan impossible.', ephemeral=True)
                    return
            await interaction.followup.send(f'Mission clôturée : {count}/{TARGET} participations.', ephemeral=True)
            return
        if row:
            await interaction.followup.send('Une mission est déjà active. Utilise `/noxmission conclure`.', ephemeral=True)
            return
        salon = salon or interaction.channel
        if not isinstance(salon, discord.TextChannel) or salon.guild.id != guild.id:
            await interaction.followup.send('Choisis un salon texte.', ephemeral=True)
            return
        perms = salon.permissions_for(guild.me)
        if not (perms.view_channel and perms.send_messages and perms.manage_webhooks):
            await interaction.followup.send('Permissions du salon insuffisantes (messages et webhooks).', ephemeral=True)
            return
        key, intro, _ = random.choice(MISSIONS)
        with engine.connect(DB) as con:
            # Une transaction empêche deux commandes concurrentes de créer deux missions.
            con.commit()
            con.execute('BEGIN IMMEDIATE')
            if current(con, guild.id):
                con.rollback()
                await interaction.followup.send('Une mission vient déjà de commencer.', ephemeral=True)
                return
            cur = con.execute('INSERT INTO nox_cosmic_missions(guild_id,channel_id,mission_key,opened_at) VALUES(?,?,?,?)', (guild.id, salon.id, key, time.time()))
            mission_id = cur.lastrowid
            con.commit()
        view = HelpView(self, mission_id).configure()
        try:
            message = await send_as_nox(salon, content=f'{intro}\n\n🤝 **Objectif : {TARGET} membres pour m’aider !**\n⏳ Durée : 1 heure. Une participation par membre.', view=view, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            with engine.connect(DB) as con:
                con.execute('UPDATE nox_cosmic_missions SET closed_at=? WHERE id=?', (time.time(), mission_id))
                con.commit()
            await interaction.followup.send('Publication impossible. Vérifie les permissions.', ephemeral=True)
            return
        with engine.connect(DB) as con:
            con.execute('UPDATE nox_cosmic_missions SET message_id=? WHERE id=?', (message.id, mission_id))
            con.commit()
        await interaction.followup.send(f'🚀 Mission lancée : {message.jump_url}', ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxCosmicMissions(bot))

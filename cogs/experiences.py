"""Expériences communautaires HORIZONS : propositions et rencontres entre membres."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

import json
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    GUILD_ID,
    FIND_PARTNER_CHANNEL_ID,
    LOCAL_TIMEZONE,
)
from .storage import db
import logging

log = logging.getLogger(__name__)


# Les missions tournent chaque semaine. Elles sont volontairement variées :
# découverte, participation et rencontre, plutôt que volume de messages.

ACTIVITY_CHOICES = [
    app_commands.Choice(name="🎮 Jouer à un jeu", value="Jouer à un jeu"),
    app_commands.Choice(name="🎬 Regarder un film ou une série", value="Film ou série"),
    app_commands.Choice(name="🎤 Discuter en vocal", value="Discussion en vocal"),
    app_commands.Choice(name="💬 Faire connaissance", value="Faire connaissance"),
    app_commands.Choice(name="🧠 Échanger sur un sujet", value="Discussion thématique"),
    app_commands.Choice(name="🎲 Faire un quiz ou une activité", value="Quiz ou activité"),
    app_commands.Choice(name="✨ Autre activité", value="Autre activité"),
]


def now_local() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def iso_now() -> str:
    return now_local().isoformat()






def get_text_channel(bot: commands.Bot, channel_id: int):
    return bot.get_channel(channel_id) if channel_id else None


class InterestView(discord.ui.View):
    """Bouton persistant permettant de signaler son intérêt pour une annonce."""

    def __init__(self, cog: "Experiences", request_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        self.cog = cog
        self.request_id = request_id
        button = discord.ui.Button(
            label="Je suis intéressé·e",
            emoji="🙋",
            style=discord.ButtonStyle.success,
            custom_id=f"horizons:interest:{request_id}",
            disabled=disabled,
        )
        button.callback = self.on_interest
        self.add_item(button)
        if not disabled:
            cancel = discord.ui.Button(
                label="Retirer mon intérêt", emoji="↩️",
                style=discord.ButtonStyle.secondary,
                custom_id=f"horizons:interest:withdraw:{request_id}",
            )
            cancel.callback = self.on_withdraw
            self.add_item(cancel)
            close = discord.ui.Button(
                label="Clore mon annonce", emoji="🔒",
                style=discord.ButtonStyle.danger,
                custom_id=f"horizons:interest:close:{request_id}",
            )
            close.callback = self.on_close
            self.add_item(close)

    async def on_withdraw(self, interaction: discord.Interaction):
        await self.cog.handle_withdraw_interest(interaction, self.request_id)

    async def on_close(self, interaction: discord.Interaction):
        await self.cog.handle_close_request(interaction, self.request_id)

    async def on_interest(self, interaction: discord.Interaction):
        await self.cog.handle_interest(interaction, self.request_id)


class Experiences(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.expire_activity_requests.start()

    def cog_unload(self):
        self.expire_activity_requests.cancel()

    async def cog_load(self):
        # Réenregistre les boutons des annonces encore actives après un redémarrage.
        with db() as conn:
            rows = conn.execute(
                "SELECT id,message_id FROM activity_requests "
                "WHERE status='open' AND expires_at>? AND message_id IS NOT NULL",
                (iso_now(),),
            ).fetchall()
        for row in rows:
            self.bot.add_view(InterestView(self, int(row["id"])), message_id=int(row["message_id"]))

    @tasks.loop(minutes=10)
    async def expire_activity_requests(self):
        with db() as conn:
            rows = conn.execute(
                "SELECT id,channel_id,message_id,thread_id FROM activity_requests "
                "WHERE status='open' AND message_id IS NOT NULL AND expires_at<=?",
                (iso_now(),),
            ).fetchall()
            if rows:
                conn.executemany(
                    "UPDATE activity_requests SET status='expired' WHERE id=?",
                    [(int(row["id"]),) for row in rows],
                )

        for row in rows:
            target_channel_id = int(row["thread_id"] or row["channel_id"])
            try:
                target = self.bot.get_channel(target_channel_id) or await self.bot.fetch_channel(target_channel_id)
                message = await target.fetch_message(int(row["message_id"]))
                await message.edit(view=InterestView(self, int(row["id"]), disabled=True))
                if isinstance(target, discord.Thread):
                    await target.edit(archived=True, locked=True)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, AttributeError):
                continue

    @expire_activity_requests.before_loop
    async def before_expire_activity_requests(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()



    # ------------------------------------------------------------------
    # 1. Passeport HORIZONS
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # 2. Je cherche quelqu'un pour…
    # ------------------------------------------------------------------
    @app_commands.command(
        name="chercher",
        description="Publier une annonce pour trouver quelqu'un avec qui faire une activité.",
    )
    @app_commands.describe(
        activite="Ce que tu aimerais faire",
        details="Jeu, film, sujet ou précision utile (facultatif)",
        duree_heures="Durée de visibilité de l'annonce, de 1 à 24 heures",
    )
    @app_commands.choices(activite=ACTIVITY_CHOICES)
    async def chercher(
        self,
        interaction: discord.Interaction,
        activite: app_commands.Choice[str],
        details: Optional[str] = None,
        duree_heures: app_commands.Range[int, 1, 24] = 6,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return
        if details and len(details) > 300:
            await interaction.response.send_message("Les précisions ne peuvent pas dépasser 300 caractères.", ephemeral=True)
            return
        if not FIND_PARTNER_CHANNEL_ID:
            await interaction.response.send_message("Le salon de recherche n'est pas configuré.", ephemeral=True)
            return

        channel = self.bot.get_channel(FIND_PARTNER_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(FIND_PARTNER_CHANNEL_ID)
            except discord.HTTPException:
                await interaction.response.send_message("Je ne parviens pas à accéder au salon de recherche.", ephemeral=True)
                return

        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.response.send_message(
                "Le salon des activités doit être un salon textuel ou un Forum.",
                ephemeral=True,
            )
            return

        created = now_local()
        expires = created + timedelta(hours=duree_heures)
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO activity_requests "
                "(guild_id,user_id,channel_id,activity,details,created_at,expires_at,status) "
                "VALUES(?,?,?,?,?,?,?,'open')",
                (
                    interaction.guild.id, interaction.user.id, channel.id,
                    activite.value, (details or "").strip(), created.isoformat(), expires.isoformat(),
                ),
            )
            request_id = int(cur.lastrowid)

        embed = horizons_embed(
            title=f"🤝 Recherche : {activite.value}",
            description=(details or "Pas de précision supplémentaire.").strip(),
            color=discord.Color.blurple(),
            timestamp=created,
        )
        embed.add_field(name="Proposé par", value=interaction.user.mention, inline=True)
        embed.add_field(name="Expire", value=f"Dans {duree_heures} h", inline=True)
        embed.set_footer(text=f"HORIZONS • Annonce n°{request_id} • Intérêt libre, révocable à tout moment.")

        view = InterestView(self, request_id)
        try:
            if isinstance(channel, discord.ForumChannel):
                title = f"{activite.value} — {interaction.user.display_name}"
                title = title[:100]
                thread, starter_message = await channel.create_thread(
                    name=title,
                    embed=embed,
                    content="Une nouvelle recherche de partenaire vient d'être publiée !",
                    view=view,
                )
                message_id = starter_message.id
                thread_id = thread.id
            else:
                message = await channel.send(embed=embed, view=view)
                message_id = message.id
                thread_id = None
        except discord.Forbidden:
            with db() as conn:
                conn.execute("UPDATE activity_requests SET status='failed' WHERE id=?", (request_id,))
            await interaction.response.send_message(
                "Je n'ai pas les permissions nécessaires pour publier dans le salon des activités.",
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            with db() as conn:
                conn.execute("UPDATE activity_requests SET status='failed' WHERE id=?", (request_id,))
            await interaction.response.send_message("Discord n'a pas accepté la publication. Réessaie dans un instant.", ephemeral=True)
            return

        with db() as conn:
            conn.execute(
                "UPDATE activity_requests SET message_id=?,thread_id=? WHERE id=?",
                (message_id, thread_id, request_id),
            )
        self.bot.add_view(view, message_id=message_id)
        await interaction.response.send_message(
            f"Ton annonce a été publiée dans <#{FIND_PARTNER_CHANNEL_ID}>. "
            f"Elle restera visible pendant {duree_heures} h. 💜",
            ephemeral=True,
        )

    async def handle_interest(self, interaction: discord.Interaction, request_id: int):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette annonce est réservée aux membres du serveur.", ephemeral=True)
            return
        with db() as conn:
            request = conn.execute(
                "SELECT * FROM activity_requests WHERE id=? AND guild_id=?",
                (request_id, interaction.guild_id),
            ).fetchone()
            if request is None or request["status"] != "open":
                await interaction.response.send_message("Cette annonce n'est plus disponible.", ephemeral=True)
                return
            if datetime.fromisoformat(request["expires_at"]) <= now_local():
                conn.execute("UPDATE activity_requests SET status='expired' WHERE id=?", (request_id,))
                await interaction.response.send_message("Cette annonce a expiré.", ephemeral=True)
                return
            if int(request["user_id"]) == interaction.user.id:
                await interaction.response.send_message("Tu ne peux pas répondre à ta propre annonce. 🙂", ephemeral=True)
                return
            cur = conn.execute(
                "INSERT OR IGNORE INTO activity_request_interests(request_id,user_id,created_at) VALUES(?,?,?)",
                (request_id, interaction.user.id, iso_now()),
            )
        if cur.rowcount == 0:
            await interaction.response.send_message("Tu as déjà manifesté ton intérêt pour cette annonce.", ephemeral=True)
            return

        requester_id = int(request["user_id"])
        requester = self.bot.get_user(requester_id)
        if requester is None:
            try:
                requester = await self.bot.fetch_user(requester_id)
            except discord.HTTPException:
                requester = None

        if requester:
            try:
                await requester.send(
                    f"💜 **{interaction.user.display_name}** est intéressé(e) par ton annonce "
                    f"« {request['activity']} » sur HORIZONS.\n"
                    "Tu peux lui répondre si tu souhaites organiser l'activité."
                )
                notice = "Ton intérêt a été transmis en message privé à la personne qui a publié l'annonce."
            except discord.Forbidden:
                notice = "Ton intérêt est enregistré, mais la personne ne peut pas recevoir de message privé. Tu peux lui répondre sur le serveur."
        else:
            notice = "Ton intérêt est enregistré."
        await interaction.response.send_message(notice, ephemeral=True)

    async def handle_withdraw_interest(self, interaction: discord.Interaction, request_id: int):
        """Révocation explicite, sans récompense ni participation présumée."""
        if interaction.guild_id is None:
            await interaction.response.send_message("Action réservée au serveur.", ephemeral=True)
            return
        with db() as conn:
            row = conn.execute(
                "SELECT status FROM activity_requests WHERE id=? AND guild_id=?",
                (request_id, interaction.guild_id),
            ).fetchone()
            if row is None or row["status"] != "open":
                await interaction.response.send_message("Cette annonce n'est plus active.", ephemeral=True)
                return
            removed = conn.execute(
                "DELETE FROM activity_request_interests WHERE request_id=? AND user_id=?",
                (request_id, interaction.user.id),
            ).rowcount
        await interaction.response.send_message(
            "Ton intérêt a été retiré. 💙" if removed else "Tu n'avais pas manifesté d'intérêt pour cette annonce.",
            ephemeral=True,
        )

    async def handle_close_request(self, interaction: discord.Interaction, request_id: int):
        """Seul l'auteur peut fermer son annonce; la clôture persiste en SQLite."""
        if interaction.guild_id is None:
            await interaction.response.send_message("Action réservée au serveur.", ephemeral=True)
            return
        with db() as conn:
            row = conn.execute(
                "SELECT user_id,status FROM activity_requests WHERE id=? AND guild_id=?",
                (request_id, interaction.guild_id),
            ).fetchone()
            if row is None:
                await interaction.response.send_message("Annonce introuvable.", ephemeral=True)
                return
            if int(row["user_id"]) != interaction.user.id:
                await interaction.response.send_message("Seul l'auteur peut clore cette annonce.", ephemeral=True)
                return
            if row["status"] != "open":
                await interaction.response.send_message("Cette annonce est déjà clôturée.", ephemeral=True)
                return
            conn.execute("UPDATE activity_requests SET status='closed' WHERE id=? AND status='open'", (request_id,))
        try:
            if interaction.message:
                await interaction.message.edit(view=InterestView(self, request_id, disabled=True))
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.response.send_message("Ton annonce est clôturée. Merci ! 🌌", ephemeral=True)

    # ------------------------------------------------------------------
    # 3. Défis collectifs
    # ------------------------------------------------------------------





async def setup(bot: commands.Bot):
    await bot.add_cog(Experiences(bot))


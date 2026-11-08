"""Expériences communautaires HORIZONS : passeport, entraide et défis collectifs."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

import json
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    MISSIONS_CHANNEL_ID,
    GUILD_ID,
    FIND_PARTNER_CHANNEL_ID,
    COLLECTIVE_CHALLENGES_CHANNEL_ID,
    LOCAL_TIMEZONE,
)
from .storage import db


# Les missions tournent chaque semaine. Elles sont volontairement variées :
# découverte, participation et rencontre, plutôt que volume de messages.
MISSION_SETS = [
    (
        "Découvrir un salon que tu ne connaissais pas",
        "Participer à une discussion ou à une animation",
        "Faire connaissance avec un autre membre, à ton rythme",
    ),
    (
        "Partager une passion ou une recommandation",
        "Participer à un quiz, un jeu ou un événement",
        "Accueillir ou aider un membre",
    ),
    (
        "Découvrir une activité proposée sur HORIZONS",
        "Lancer une conversation sur un sujet qui t'intéresse",
        "Participer à un défi ou à une activité collective",
    ),
]

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


def week_key() -> str:
    iso = now_local().isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def current_missions() -> tuple[str, str, str]:
    iso = now_local().isocalendar()
    return MISSION_SETS[(iso.week - 1) % len(MISSION_SETS)]


def get_text_channel(bot: commands.Bot, channel_id: int):
    return bot.get_channel(channel_id) if channel_id else None


class InterestView(discord.ui.View):
    """Bouton persistant permettant de signaler son intérêt pour une annonce."""

    def __init__(self, cog: "Experiences", request_id: int, disabled: bool = False):
        super().__init__(timeout=None)
        self.cog = cog
        self.request_id = request_id
        button = discord.ui.Button(
            label="Ça m'intéresse",
            emoji="🙋",
            style=discord.ButtonStyle.success,
            custom_id=f"horizons:interest:{request_id}",
            disabled=disabled,
        )
        button.callback = self.on_interest
        self.add_item(button)

    async def on_interest(self, interaction: discord.Interaction):
        await self.cog.handle_interest(interaction, self.request_id)


class Experiences(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.publish_weekly_missions.start()
        self.expire_activity_requests.start()

    def cog_unload(self):
        self.publish_weekly_missions.cancel()
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

    @tasks.loop(minutes=30)
    async def publish_weekly_missions(self):
        if not MISSIONS_CHANNEL_ID or not GUILD_ID:
            return
        key = week_key()
        with db() as conn:
            already_posted = conn.execute(
                "SELECT 1 FROM passport_week_announcements WHERE guild_id=? AND week_key=?",
                (GUILD_ID, key),
            ).fetchone()
        if already_posted:
            return

        channel = self.bot.get_channel(MISSIONS_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MISSIONS_CHANNEL_ID)
            except discord.HTTPException:
                return
        missions = current_missions()
        embed = horizons_embed(
            title="✦ Les missions de la semaine",
            description=(
                "Une nouvelle semaine commence sur HORIZONS ! Voici les trois petites missions "
                "à réaliser à ton rythme. Consulte `/mon_passeport` et valide tes étapes avec "
                "`/valider_mission`."
            ),
            color=discord.Color.blurple(),
        )
        for number, mission in enumerate(missions, start=1):
            embed.add_field(name=f"Mission {number}", value=mission, inline=False)
        embed.set_footer(text=f"Passeport HORIZONS • {key} • Chacun avance à son rythme.")
        try:
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(
                    name=f"Missions HORIZONS — {key}",
                    content="🧭 Les missions de la semaine sont disponibles !",
                    embed=embed,
                )
            elif isinstance(channel, (discord.TextChannel)):
                await channel.send(embed=embed)
            else:
                return
        except discord.HTTPException:
            return

        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO passport_week_announcements(guild_id,week_key,posted_at) VALUES(?,?,?)",
                (GUILD_ID, key, iso_now()),
            )

    @publish_weekly_missions.before_loop
    async def before_publish_weekly_missions(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

    # ------------------------------------------------------------------
    # 1. Passeport HORIZONS
    # ------------------------------------------------------------------
    @app_commands.command(
        name="mon_passeport",
        description="Consulter tes missions et ta progression du Passeport HORIZONS.",
    )
    async def mon_passeport(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return

        missions = current_missions()
        key = week_key()
        with db() as conn:
            rows = conn.execute(
                "SELECT mission_number FROM passport_completions "
                "WHERE guild_id=? AND user_id=? AND week_key=?",
                (interaction.guild_id, interaction.user.id, key),
            ).fetchall()
        completed = {int(row["mission_number"]) for row in rows}

        embed = horizons_embed(
            title="🧭 Ton Passeport HORIZONS",
            description=(
                "Trois petites missions pour découvrir le serveur, participer et créer des liens.\n"
                f"**Semaine : {key}**"
            ),
            color=discord.Color.blurple(),
        )
        for number, mission in enumerate(missions, start=1):
            mark = "✅" if number in completed else "⬜"
            embed.add_field(name=f"{mark} Mission {number}", value=mission, inline=False)
        embed.add_field(
            name="Progression de la semaine",
            value=f"**{len(completed)}/3 missions validées**",
            inline=False,
        )
        embed.set_footer(text="HORIZONS • Les validations reposent sur la confiance : pas de course aux messages ni de classement.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="valider_mission",
        description="Valider une mission accomplie dans ton Passeport HORIZONS.",
    )
    @app_commands.describe(numero="Le numéro de la mission affichée dans /mon_passeport")
    @app_commands.choices(numero=[
        app_commands.Choice(name="Mission 1", value=1),
        app_commands.Choice(name="Mission 2", value=2),
        app_commands.Choice(name="Mission 3", value=3),
    ])
    async def valider_mission(
        self,
        interaction: discord.Interaction,
        numero: app_commands.Choice[int],
    ):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO passport_completions "
                "(guild_id,user_id,week_key,mission_number,completed_at) VALUES(?,?,?,?,?)",
                (interaction.guild_id, interaction.user.id, week_key(), numero.value, iso_now()),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM passport_completions WHERE guild_id=? AND user_id=? AND week_key=?",
                (interaction.guild_id, interaction.user.id, week_key()),
            ).fetchone()[0]
        if cur.rowcount == 0:
            await interaction.response.send_message("Cette mission est déjà validée pour cette semaine. 🌟", ephemeral=True)
            return

        message = f"Mission {numero.value} validée ! Ta progression est maintenant de **{count}/3**. 🌱"
        if count == 3:
            message += "\n🎉 **Passeport complété pour cette semaine !** Bravo pour ta participation."
        await interaction.response.send_message(message, ephemeral=True)
        features = self.bot.get_cog("HorizonsFeatures")
        if features and isinstance(interaction.user, discord.Member) and interaction.guild:
            await features.check_achievements(interaction.guild, interaction.user)

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
                "Le salon #cherche-quelquun doit être un salon textuel ou un Forum.",
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
        embed.set_footer(text=f"HORIZONS • Annonce n°{request_id} • Clique sur « Ça m'intéresse » pour te manifester.")

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
                "Je n'ai pas les permissions nécessaires pour publier dans #cherche-quelquun.",
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

    # ------------------------------------------------------------------
    # 3. Défis collectifs
    # ------------------------------------------------------------------
    @app_commands.command(
        name="defi_collectif",
        description="Voir le défi collectif en cours et sa progression.",
    )
    async def defi_collectif(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            challenge = conn.execute(
                "SELECT * FROM collective_challenges WHERE guild_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (interaction.guild_id,),
            ).fetchone()
            if challenge:
                count = conn.execute(
                    "SELECT COUNT(*) FROM collective_challenge_members WHERE challenge_id=?",
                    (challenge["id"],),
                ).fetchone()[0]
                joined = conn.execute(
                    "SELECT 1 FROM collective_challenge_members WHERE challenge_id=? AND user_id=?",
                    (challenge["id"], interaction.user.id),
                ).fetchone() is not None
            else:
                count, joined = 0, False

        if challenge is None:
            await interaction.response.send_message("Aucun défi collectif n'est actuellement ouvert. Un nouveau défi arrivera bientôt ! 🌌", ephemeral=True)
            return

        ends_at = datetime.fromisoformat(challenge["ends_at"])
        embed = horizons_embed(
            title=f"🌟 Défi collectif : {challenge['title']}",
            description=challenge["description"],
            color=discord.Color.gold(),
        )
        embed.add_field(name="Progression", value=f"**{count}/{challenge['target']} membres**", inline=True)
        embed.add_field(name="Échéance", value=discord.utils.format_dt(ends_at, style="R"), inline=True)
        embed.add_field(name="Ta participation", value="✅ Tu as rejoint le défi." if joined else "Tu n'as pas encore rejoint le défi.", inline=False)
        embed.set_footer(text="HORIZONS • Chaque membre ne compte qu'une seule fois : c'est un objectif commun.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="rejoindre_defi",
        description="Participer au défi collectif HORIZONS en cours.",
    )
    async def rejoindre_defi(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            challenge = conn.execute(
                "SELECT * FROM collective_challenges WHERE guild_id=? AND status='active' ORDER BY id DESC LIMIT 1",
                (interaction.guild_id,),
            ).fetchone()
            if challenge is None:
                await interaction.response.send_message("Il n'y a pas de défi ouvert pour le moment.", ephemeral=True)
                return
            if datetime.fromisoformat(challenge["ends_at"]) <= now_local():
                conn.execute("UPDATE collective_challenges SET status='expired' WHERE id=?", (challenge["id"],))
                await interaction.response.send_message("Ce défi est arrivé à échéance.", ephemeral=True)
                return
            cur = conn.execute(
                "INSERT OR IGNORE INTO collective_challenge_members(challenge_id,user_id,joined_at) VALUES(?,?,?)",
                (challenge["id"], interaction.user.id, iso_now()),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM collective_challenge_members WHERE challenge_id=?",
                (challenge["id"],),
            ).fetchone()[0]
            completed_now = count >= int(challenge["target"]) and challenge["status"] == "active"
            if completed_now:
                conn.execute("UPDATE collective_challenges SET status='completed' WHERE id=?", (challenge["id"],))
        if cur.rowcount == 0:
            await interaction.response.send_message("Tu fais déjà partie de ce défi. Merci pour ta participation ! 💜", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Tu as rejoint le défi **{challenge['title']}** ! Nous sommes maintenant **{count}/{challenge['target']}**. 🌱",
            ephemeral=True,
        )
        features = self.bot.get_cog("HorizonsFeatures")
        if features and interaction.guild and isinstance(interaction.user, discord.Member):
            await features.check_achievements(interaction.guild, interaction.user)
        if completed_now:
            # Le succès collectif est attribué à tous les membres inscrits, sans publier
            # une avalanche d'annonces individuelles dans le salon des succès.
            if features and interaction.guild:
                with db() as conn:
                    participant_ids = [int(row[0]) for row in conn.execute(
                        "SELECT user_id FROM collective_challenge_members WHERE challenge_id=?",
                        (challenge["id"],),
                    ).fetchall()]
                for participant_id in participant_ids:
                    participant = interaction.guild.get_member(participant_id)
                    if participant is None:
                        try:
                            participant = await interaction.guild.fetch_member(participant_id)
                        except discord.HTTPException:
                            participant = None
                    if isinstance(participant, discord.Member):
                        await features.check_achievements(interaction.guild, participant)
            await self.announce_challenge(
                interaction.guild,
                f"🎉 **Défi réussi !** « {challenge['title']} » a atteint son objectif grâce à vous : "
                f"**{count}/{challenge['target']} membres** ont participé. Merci à toute la communauté !",
            )

    @app_commands.command(
        name="creer_defi",
        description="Créer un nouveau défi collectif (équipe HORIZONS).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        titre="Titre court du défi",
        description="Explication de l'objectif collectif",
        objectif="Nombre de membres à réunir",
        duree_jours="Durée du défi, de 1 à 30 jours",
    )
    async def creer_defi(
        self,
        interaction: discord.Interaction,
        titre: str,
        description: str,
        objectif: app_commands.Range[int, 2, 500],
        duree_jours: app_commands.Range[int, 1, 30] = 7,
    ):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur HORIZONS.", ephemeral=True)
            return
        if not 3 <= len(titre.strip()) <= 80 or not 5 <= len(description.strip()) <= 500:
            await interaction.response.send_message("Le titre doit contenir 3 à 80 caractères et la description 5 à 500 caractères.", ephemeral=True)
            return
        created = now_local()
        ends = created + timedelta(days=duree_jours)
        with db() as conn:
            conn.execute(
                "UPDATE collective_challenges SET status='expired' WHERE guild_id=? AND status='active' AND ends_at<=?",
                (interaction.guild_id, created.isoformat()),
            )
            active = conn.execute(
                "SELECT id FROM collective_challenges WHERE guild_id=? AND status='active'",
                (interaction.guild_id,),
            ).fetchone()
            if active:
                await interaction.response.send_message(
                    "Un défi est déjà en cours. Termine-le ou attends son échéance avant d'en créer un autre.",
                    ephemeral=True,
                )
                return
            cur = conn.execute(
                "INSERT INTO collective_challenges "
                "(guild_id,title,description,target,created_by,created_at,ends_at,status) "
                "VALUES(?,?,?,?,?,?,?,'active')",
                (interaction.guild_id, titre.strip(), description.strip(), objectif, interaction.user.id, created.isoformat(), ends.isoformat()),
            )
            challenge_id = int(cur.lastrowid)

        await interaction.response.send_message(
            f"Le défi **{titre}** est créé. Je le publie dans <#{COLLECTIVE_CHALLENGES_CHANNEL_ID}>.",
            ephemeral=True,
        )
        await self.announce_challenge(
            interaction.guild,
            f"🌟 **Nouveau défi collectif : {titre}**\n{description}\n\n"
            f"Objectif : **{objectif} membres**\n"
            f"Échéance : {discord.utils.format_dt(ends, style='R')}\n\n"
            "Pour participer, utilisez `/rejoindre_defi` et suivez la progression avec `/defi_collectif`.",
        )

    async def announce_challenge(self, guild: discord.Guild, message: str):
        channel = self.bot.get_channel(COLLECTIVE_CHALLENGES_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(COLLECTIVE_CHALLENGES_CHANNEL_ID)
            except discord.HTTPException:
                return
        try:
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(
                    name="Défi collectif HORIZONS",
                    content=message,
                )
            elif isinstance(channel, (discord.TextChannel)):
                await channel.send(message)
        except discord.HTTPException:
            # L'état du défi reste en base ; une publication manuelle reste possible.
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(Experiences(bot))

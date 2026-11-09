"""Carrefour communautaire permanent HORIZONS : salon et panneau interactif.

Le bot crée le salon seulement s'il n'existe pas. Les permissions explicites
sont appliquées uniquement à la création pour ne pas écraser les réglages
d'un administrateur sur un salon déjà en place.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands

from config import (
    GUILD_ID, EXPERIENCES_CATEGORY_ID, MEMBER_ROLE_ID, NEW_MEMBER_ROLE_ID,
    STAFF_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID, ANIMATOR_ROLE_ID,
    DAILY_QUESTION_CHANNEL_ID, AGENDA_CHANNEL_ID, FIND_PARTNER_CHANNEL_ID,
    MOOD_CHANNEL_ID, LOCAL_TIMEZONE,
)
from cogs.storage import db
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

log = logging.getLogger(__name__)
CHANNEL_NAME = "🌅・aujourd-hui-sur-horizons"
CHANNEL_KEY = "today_hub_channel_id"
MESSAGE_KEY = "today_hub_message_id"
MARKER = "HORIZONS-TODAY-HUB:v1"


def url(guild_id: int, channel_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


class TodayChoice(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="horizons:today:choice:v1",
            placeholder="Que souhaites-tu faire aujourd'hui ?",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Discuter", value="discussion", emoji="💬", description="Rejoindre une conversation"),
                discord.SelectOption(label="Jouer", value="games", emoji="🎮", description="Retrouver l'Arcade"),
                discord.SelectOption(label="Explorer", value="treasures", emoji="🌌", description="Découvrir les Trésors du Ciel"),
                discord.SelectOption(label="Rencontrer", value="meet", emoji="🤝", description="Voir les propositions existantes"),
                discord.SelectOption(label="Proposer une activité", value="propose", emoji="✨", description="Créer une invitation sans commande"),
                discord.SelectOption(label="Défi du jour", value="daily_challenge", emoji="🌱", description="Un petit geste collectif, sans compétition"),
                discord.SelectOption(label="Participer", value="events", emoji="📅", description="Voir les événements"),
                discord.SelectOption(label="Faire une pause", value="wellbeing", emoji="🌻", description="Prendre un moment pour soi"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Disponible uniquement sur HORIZONS.", ephemeral=True)
            return
        if MEMBER_ROLE_ID and not any(r.id == MEMBER_ROLE_ID for r in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Commence par accepter la charte pour accéder aux activités.", ephemeral=True)
            return
        choice = self.values[0]
        if choice == "daily_challenge":
            cog = interaction.client.get_cog("TodayHub")
            if cog is None:
                await interaction.response.send_message("Le défi du jour est temporairement indisponible.", ephemeral=True)
                return
            await cog.show_daily_challenge(interaction)
            return
        if choice == "propose":
            if not FIND_PARTNER_CHANNEL_ID or interaction.guild.get_channel(FIND_PARTNER_CHANNEL_ID) is None:
                await interaction.response.send_message("Le salon des rencontres n'est pas configuré.", ephemeral=True)
                return
            await interaction.response.send_message(
                "✨ Quel type de moment souhaites-tu proposer ? "
                "L'annonce sera visible pendant **6 heures**, sans notification générale.",
                view=ActivityProposalView(), ephemeral=True,
            )
            return
        destinations = {
            "discussion": (DAILY_QUESTION_CHANNEL_ID, "💬 Rejoins la question du jour et échange à ton rythme."),
            "meet": (FIND_PARTNER_CHANNEL_ID, "🤝 Propose une activité ou rejoins une proposition existante."),
            "events": (AGENDA_CHANNEL_ID, "📅 Découvre les rendez-vous et événements de la communauté."),
            "wellbeing": (MOOD_CHANNEL_ID, "🌻 Un espace pour prendre une pause et écouter ton humeur."),
        }
        if choice in destinations:
            cid, description = destinations[choice]
        elif choice in {"games", "treasures"}:
            # Recherche du salon par son nom : les IDs Arcade et Trésors ne sont
            # pas fixés dans config.py dans la version de référence.
            keywords = ("arcade-horizons", "arcade") if choice == "games" else ("tresors-du-ciel", "trésors-du-ciel", "tresors")
            channel = next((c for c in interaction.guild.text_channels if any(k in c.name.lower() for k in keywords)), None)
            cid = channel.id if channel else None
            description = "🎮 L'Arcade t'attend !" if choice == "games" else "🌌 Explore les étoiles et constellations !"
        else:
            cid, description = None, "Cette activité n'est pas encore disponible."
        if not cid or interaction.guild.get_channel(cid) is None:
            await interaction.response.send_message(
                "Cette destination n'est pas encore configurée. L'équipe pourra la compléter.", ephemeral=True,
            )
            return
        channel = interaction.guild.get_channel(cid)
        if not channel.permissions_for(interaction.user).view_channel:
            await interaction.response.send_message("Tu n'as pas encore accès à cet espace.", ephemeral=True)
            return
        view = discord.ui.View(timeout=180)
        view.add_item(discord.ui.Button(label="Accéder au salon", emoji="🔗", url=url(interaction.guild.id, cid)))
        await interaction.response.send_message(description, view=view, ephemeral=True)


class ActivityDetailsModal(discord.ui.Modal, title="Proposer un moment sur HORIZONS"):
    details = discord.ui.TextInput(
        label="Précision (facultative)", required=False, max_length=300,
        style=discord.TextStyle.paragraph,
        placeholder="Ex. : un petit jeu tranquille ce soir, sans obligation",
    )

    def __init__(self, activity_value: str):
        super().__init__()
        self.activity_value = activity_value

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Réservé aux membres HORIZONS.", ephemeral=True)
            return
        if MEMBER_ROLE_ID and not any(r.id == MEMBER_ROLE_ID for r in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Accepte d'abord la charte.", ephemeral=True)
            return
        cog = interaction.client.get_cog("Experiences")
        if cog is None:
            await interaction.response.send_message("Les propositions sont momentanément indisponibles.", ephemeral=True)
            return
        # Réutilise la logique d'annonces existante : expiration, persistance,
        # bouton « Ça m'intéresse » et notification privée à l'auteur.
        from cogs.experiences import ACTIVITY_CHOICES
        choice = next((c for c in ACTIVITY_CHOICES if c.value == self.activity_value), None)
        if choice is None:
            await interaction.response.send_message("Activité non reconnue.", ephemeral=True)
            return
        # Deux propositions réellement ouvertes et non expirées au maximum.
        # Le contrôle utilise la même table que le module Expériences.
        now = datetime.now(LOCAL_TIMEZONE)
        with db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM activity_requests WHERE guild_id=? AND user_id=? "
                "AND status='open' AND created_at >= ? AND expires_at > ?",
                (interaction.guild.id, interaction.user.id,
                 (now - timedelta(hours=6)).isoformat(), now.isoformat()),
            ).fetchone()[0]
        if count >= 2:
            await interaction.response.send_message(
                "Tu as déjà deux propositions récentes en cours. Reviens un peu plus tard 💙", ephemeral=True,
            )
            return
        await cog.chercher.callback(cog, interaction, choice, str(self.details.value or ""), 6)


class ActivityProposalSelect(discord.ui.Select):
    def __init__(self):
        from cogs.experiences import ACTIVITY_CHOICES
        super().__init__(
            placeholder="Choisir une activité à partager",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label=c.name[:100], value=c.value)
                for c in ACTIVITY_CHOICES
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ActivityDetailsModal(self.values[0]))


class ActivityProposalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ActivityProposalSelect())



CHALLENGES = (
    "Partager une découverte ou une recommandation dans une discussion",
    "Accueillir une personne ou lui souhaiter une bonne journée",
    "Proposer un petit jeu à partager, sans pression",
    "Échanger autour d'un souvenir positif",
    "Prendre un moment pour remercier quelqu'un",
    "Découvrir un salon que tu n'avais jamais visité",
    "Participer à une conversation à ton rythme",
)


class ChallengeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="J'ai participé", emoji="🌱", style=discord.ButtonStyle.success)
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("TodayHub")
        if cog is None:
            await interaction.response.send_message("Le défi n'est pas disponible pour le moment.", ephemeral=True)
            return
        await cog.join_daily_challenge(interaction)


class TodayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TodayChoice())


class TodayHub(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._initialized = False

    async def cog_load(self):
        with db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS today_challenge_participation (
                guild_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, day, user_id)
            )""")
        self.bot.add_view(TodayView())
        self.maintenance.start()

    def cog_unload(self):
        self.maintenance.cancel()

    def challenge_day(self):
        return datetime.now(LOCAL_TIMEZONE).date().isoformat()

    def challenge_description(self):
        return CHALLENGES[datetime.now(LOCAL_TIMEZONE).weekday()]

    def challenge_count(self, guild_id: int, day: str) -> int:
        with db() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM today_challenge_participation WHERE guild_id=? AND day=?",
                (guild_id, day),
            ).fetchone()[0]

    async def show_daily_challenge(self, interaction: discord.Interaction):
        day = self.challenge_day()
        count = self.challenge_count(interaction.guild.id, day)
        await interaction.response.send_message(
            f"🌱 **Défi du jour**\n{self.challenge_description()}\n\n"
            f"**{count} participation(s)** aujourd'hui. "
            "Participe à ton rythme, puis utilise le bouton si tu le souhaites. "
            "Aucune preuve ni publication n'est demandée.",
            view=ChallengeView(), ephemeral=True,
        )

    async def join_daily_challenge(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Réservé aux membres HORIZONS.", ephemeral=True)
            return
        if MEMBER_ROLE_ID and not any(r.id == MEMBER_ROLE_ID for r in interaction.user.roles) and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Accepte d'abord la charte pour participer.", ephemeral=True)
            return
        day = self.challenge_day()
        with db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO today_challenge_participation "
                "(guild_id,day,user_id,joined_at) VALUES(?,?,?,?)",
                (interaction.guild.id, day, interaction.user.id, datetime.now(LOCAL_TIMEZONE).isoformat()),
            )
            added = cur.rowcount > 0
        count = self.challenge_count(interaction.guild.id, day)
        msg = ("Merci d'avoir participé ! 💙" if added else "Ta participation est déjà enregistrée aujourd'hui 💙")
        await interaction.response.send_message(f"{msg} **{count} participation(s)** au total.", ephemeral=True)

    def setting(self, key: str) -> int | None:
        with db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
        try:
            return int(row["value"]) if row else None
        except (TypeError, ValueError):
            return None

    def save_setting(self, key: str, value: int):
        with db() as conn:
            conn.execute(
                "INSERT INTO bot_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    async def ensure_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        existing_id = self.setting(CHANNEL_KEY)
        channel = guild.get_channel(existing_id) if existing_id else None
        if not isinstance(channel, discord.TextChannel):
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
        if isinstance(channel, discord.TextChannel):
            self.save_setting(CHANNEL_KEY, channel.id)
            return channel

        category = guild.get_channel(EXPERIENCES_CATEGORY_ID) if EXPERIENCES_CATEGORY_ID else None
        if not isinstance(category, discord.CategoryChannel):
            category = None
            log.warning("Catégorie Expériences absente : création du salon à la racine.")

        everyone = guild.default_role
        me = guild.me
        member_role = guild.get_role(MEMBER_ROLE_ID) if MEMBER_ROLE_ID else None
        if not member_role or not me:
            log.error("Salon non créé : rôle membre ou compte bot introuvable.")
            return None
        if not me.guild_permissions.manage_channels:
            log.error("Salon non créé : permission Gérer les salons manquante.")
            return None

        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            member_role: discord.PermissionOverwrite(
                view_channel=True, read_message_history=True,
                send_messages=False, add_reactions=False,
                use_application_commands=True,
            ),
            me: discord.PermissionOverwrite(
                view_channel=True, read_message_history=True, send_messages=True,
                manage_messages=True, embed_links=True,
            ),
        }
        new_role = guild.get_role(NEW_MEMBER_ROLE_ID) if NEW_MEMBER_ROLE_ID else None
        if new_role and new_role != member_role:
            overwrites[new_role] = discord.PermissionOverwrite(view_channel=False)
        for rid in {STAFF_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID, ANIMATOR_ROLE_ID}:
            role = guild.get_role(rid) if rid else None
            if role and role != member_role and role != new_role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, read_message_history=True,
                    send_messages=False, use_application_commands=True,
                )
        try:
            channel = await guild.create_text_channel(
                CHANNEL_NAME, category=category, overwrites=overwrites,
                topic="Le carrefour interactif HORIZONS : trouve une activité sans commande.",
                reason="Création du panneau communautaire HORIZONS à la demande du fondateur.",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.error("Impossible de créer le salon du jour : %s", exc)
            return None
        self.save_setting(CHANNEL_KEY, channel.id)
        log.info("Salon du jour créé : %s", channel.id)
        return channel

    def make_embed(self):
        inspirations = (
            "💬 Une question simple : quelle découverte récente t'a fait sourire ?",
            "🎮 Envie d'un jeu rapide ? L'Arcade est accessible en quelques clics.",
            "🤝 Une activité à partager ? Propose-la sans obligation ni mention générale.",
            "🌌 Explore une étoile et découvre sa signification.",
            "🌻 Prends quelques minutes pour toi, à ton rythme.",
            "📅 Découvre les événements et les prochaines animations.",
            "✨ Et si tu invitais quelqu'un à découvrir un jeu ensemble ?",
        )
        idea = inspirations[datetime.now(LOCAL_TIMEZONE).weekday()]
        embed = horizons_embed(
            title="🌅 Que faire aujourd'hui sur HORIZONS ?",
            description=(
                "Bienvenue dans ton carrefour communautaire !\n\n"
                "Choisis une activité dans le menu ci-dessous : discuter, jouer, "
                "explorer les Trésors du Ciel, rencontrer des membres, participer "
                "à un événement, relever un défi collectif ou prendre une pause.\n\n"
                f"**Idée du jour :** {idea}\n\n"
                "💙 **Tu avances à ton rythme.** Aucun choix n'est obligatoire. "
                "Le menu t'indiquera où aller, sans encombrer le salon."
            ),
        )
        embed.set_footer(text=MARKER)
        return embed

    async def ensure_panel(self, channel: discord.TextChannel):
        embed = self.make_embed()
        mid = self.setting(MESSAGE_KEY)
        if mid:
            try:
                msg = await channel.fetch_message(mid)
                if msg.author.id == self.bot.user.id and any(
                    (e.footer.text or "") == MARKER for e in msg.embeds
                ):
                    if (not msg.embeds or msg.embeds[0].description != embed.description
                            or msg.embeds[0].title != embed.title or not msg.components):
                        await msg.edit(embed=embed, view=TodayView())
                    return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        # Si la DB a été restaurée, retrouver le panneau par sa signature.
        try:
            async for msg in channel.history(limit=75):
                if msg.author.id == self.bot.user.id and any(
                    (e.footer.text or "") == MARKER for e in msg.embeds
                ):
                    if (not msg.embeds or msg.embeds[0].description != embed.description
                            or msg.embeds[0].title != embed.title or not msg.components):
                        await msg.edit(embed=embed, view=TodayView())
                    self.save_setting(MESSAGE_KEY, msg.id)
                    return
        except (discord.Forbidden, discord.HTTPException):
            pass
        try:
            msg = await channel.send(embed=embed, view=TodayView(), allowed_mentions=discord.AllowedMentions.none())
            self.save_setting(MESSAGE_KEY, msg.id)
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.error("Impossible de publier le panneau du jour : %s", exc)

    @tasks.loop(hours=6)
    async def maintenance(self):
        guild = self.bot.get_guild(GUILD_ID) if GUILD_ID else None
        if guild is None:
            return
        await wait_for_logo_ready()
        channel = await self.ensure_channel(guild)
        if channel is not None:
            await self.ensure_panel(channel)

    @maintenance.before_loop
    async def before_maintenance(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(TodayHub(bot))

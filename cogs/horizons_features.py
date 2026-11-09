"""Fonctionnalités communautaires HORIZONS : humeur privée, succès et affinités."""
from __future__ import annotations
from cogs.embed_theme import get_logo_url, horizons_embed

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    DATA_DIR, MOOD_CHANNEL_ID, SUCCESS_CHANNEL_ID, AFFINITY_CHANNEL_ID,
    LOCAL_TIMEZONE, GUILD_ID,
)
from .storage import db

ROLE_CATALOG = DATA_DIR / "role_catalog.json"
AFFINITY_CATEGORIES = (
    "Langues", "Centres d'intérêt", "Styles musicaux", "Jeux",
    "Communication", "Disponibilités", "Ce que je recherche",
)
MOODS = [
    app_commands.Choice(name="😊 Je vais bien", value="Je vais bien"),
    app_commands.Choice(name="😁 Je suis heureux(se)", value="Heureux(se)"),
    app_commands.Choice(name="😐 Ça va, sans plus", value="Ça va, sans plus"),
    app_commands.Choice(name="😔 Je ne vais pas très bien", value="Pas très bien"),
    app_commands.Choice(name="😣 Je suis stressé(e)", value="Stressé(e)"),
    app_commands.Choice(name="💤 Je suis fatigué(e)", value="Fatigué(e)"),
    app_commands.Choice(name="🤝 J'aimerais parler à quelqu'un", value="Besoin de parler"),
]

ACHIEVEMENTS = {
    "first_day": ("🌱 Premier horizon", "Tu as participé à la vie de HORIZONS pour la première fois."),
    "seven_days": ("🌿 Présence régulière", "Tu as été actif(ve) pendant 7 jours différents."),
    "thirty_days": ("🌳 Horizon durable", "Tu as été actif(ve) pendant 30 jours différents."),
    "passport_week": ("🧭 Passeport accompli", "Tu as validé les trois missions de ton passeport hebdomadaire."),
}


def today_local() -> str:
    return datetime.now(LOCAL_TIMEZONE).date().isoformat()


def current_week_key() -> str:
    iso = datetime.now(LOCAL_TIMEZONE).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def load_affinity_roles() -> dict[str, set[int]]:
    data = json.loads(ROLE_CATALOG.read_text(encoding="utf-8"))
    return {
        category: {int(role_id) for _, role_id in data.get(category, [])}
        for category in AFFINITY_CATEGORIES
    }


class AffinityPanel(discord.ui.View):
    """Panneau permanent, actions privées, compatible avec les profils existants."""
    def __init__(self):
        super().__init__(timeout=None)

    async def _run(self, interaction: discord.Interaction, action: str):
        cog = interaction.client.get_cog("HorizonsFeatures")
        if cog is None:
            await interaction.response.send_message("Le service d'affinités est indisponible.", ephemeral=True)
            return
        if interaction.guild_id != GUILD_ID or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Cette fonction est réservée aux membres d'HORIZONS.", ephemeral=True)
            return
        if action == "enable":
            await cog.affinites_activer.callback(cog, interaction)
        elif action == "find":
            await cog.affinites_chercher.callback(cog, interaction)
        elif action == "disable":
            await cog.affinites_desactiver.callback(cog, interaction)
        else:
            await cog.affinity_interests(interaction)

    @discord.ui.button(label="Activer mon profil", emoji="💜", style=discord.ButtonStyle.success,
                       custom_id="horizons:affinity:enable:v1", row=0)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._run(interaction, "enable")

    @discord.ui.button(label="Trouver mes affinités", emoji="🧩", style=discord.ButtonStyle.primary,
                       custom_id="horizons:affinity:find:v1", row=0)
    async def find(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._run(interaction, "find")

    @discord.ui.button(label="Mes centres d'intérêt", emoji="🎭", style=discord.ButtonStyle.secondary,
                       custom_id="horizons:affinity:interests:v1", row=1)
    async def interests(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._run(interaction, "interests")

    @discord.ui.button(label="Désactiver mon profil", emoji="🔒", style=discord.ButtonStyle.danger,
                       custom_id="horizons:affinity:disable:v1", row=1)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._run(interaction, "disable")


class MoodChoice(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Choisir ma météo", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=c.name, value=c.value) for c in MOODS],
                         custom_id="horizons:mood:choose:v2")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("HorizonsFeatures")
        if cog is None:
            await interaction.response.send_message("Service indisponible.", ephemeral=True); return
        choice = next((c for c in MOODS if c.value == self.values[0]), None)
        if choice is None:
            await interaction.response.send_message("Choix invalide.", ephemeral=True); return
        await cog.humeur.callback(cog, interaction, choice)


class MoodSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(MoodChoice())


class MoodPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ma météo", emoji="💗", style=discord.ButtonStyle.primary, custom_id="horizons:mood:panel:choose:v2")
    async def mood(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Choisis ton humeur du jour, en privé :", view=MoodSelectView(), ephemeral=True)

    @discord.ui.button(label="Voir ma météo", emoji="🌤️", style=discord.ButtonStyle.secondary, custom_id="horizons:mood:panel:today:v2")
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("HorizonsFeatures")
        if cog: await cog.ma_meteo.callback(cog, interaction)
        else: await interaction.response.send_message("Service indisponible.", ephemeral=True)

    @discord.ui.button(label="Écrire au staff", emoji="✉️", style=discord.ButtonStyle.secondary, custom_id="horizons:mood:panel:staff:v2")
    async def staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog is None:
            await interaction.response.send_message("Messagerie staff indisponible.", ephemeral=True); return
        from .tickets import TicketOpenModal
        await interaction.response.send_modal(TicketOpenModal(cog))


class HorizonsFeatures(commands.Cog):
    affinites = app_commands.Group(name="affinites", description="Gérer tes affinités amicales HORIZONS")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._panels_checked = False

    async def cog_load(self):
        self.bot.add_view(AffinityPanel())
        self.bot.add_view(MoodPanel())

    @commands.Cog.listener()
    async def on_ready(self):
        if self._panels_checked:
            return
        self._panels_checked = True
        await self.ensure_explanation(MOOD_CHANNEL_ID, "mood_explanation_message", self.mood_embed(), view=MoodPanel())
        await self.ensure_explanation(AFFINITY_CHANNEL_ID, "affinity_explanation_message", self.affinity_embed(), view=AffinityPanel())

    @staticmethod
    def mood_embed() -> discord.Embed:
        embed = horizons_embed(
            title="❤️ La météo de l'humeur",
            description=(
                "**Comment te sens-tu aujourd'hui ?**\n\n"
                "Chaque journée est différente. Prends quelques secondes pour indiquer ton humeur "
                "du moment avec le bouton **Ma météo**.\n\n"
                "😊 Je vais bien • 😁 Heureux(se) • 😐 Ça va, sans plus\n"
                "😔 Pas très bien • 😣 Stressé(e) • 💤 Fatigué(e)\n"
                "🤝 J'aimerais parler à quelqu'un\n\n"
                "**Ta réponse est privée :** elle n'est pas publiée dans ce salon et les autres membres "
                "ne peuvent pas consulter ton historique. Tu peux consulter ton humeur du jour avec **Voir ma météo**. "
                "Cette réponse n'envoie pas d'alerte au staff. Pour contacter l'équipe en privé, utilise **Écrire au staff**.\n\n"
                "La participation est entièrement facultative. En cas de danger immédiat, contacte les services d'urgence."
            ),
            color=discord.Color.from_rgb(226, 91, 137),
        )
        embed.set_footer(text="HORIZONS • Un espace sans jugement")
        if not embed.thumbnail.url and (self_logo := get_logo_url()):
            embed.set_thumbnail(url=self_logo)
        return embed

    @staticmethod
    def affinity_embed() -> discord.Embed:
        embed = horizons_embed(
            title="🧩 Les Connexions du Ciel · Intérêts communs",
            description=(
                "**Envie de rencontrer des personnes qui partagent tes passions ?**\n\n"
                "💜 **Activer mon profil** : participer volontairement aux suggestions.\n"
                "🧩 **Trouver mes affinités** : découvrir en privé jusqu'à cinq membres "
                "volontaires ayant au moins deux rôles d'intérêt communs.\n"
                "🎭 **Mes centres d'intérêt** : consulter tes catégories et accéder au panneau "
                "des rôles pour les compléter.\n"
                "🔒 **Désactiver mon profil** : te retirer immédiatement des suggestions.\n\n"
                "**Compatibilité :** intérêts, jeux, musique, langues, disponibilité et "
                "préférences de communication. Les rôles d'âge, de genre, de pronoms, "
                "d'orientation, de culture et de localisation ne sont jamais utilisés.\n\n"
                "Tout est facultatif. Les résultats sont privés ; aucun MP ni contact "
                "automatique n'est envoyé. Une affinité n'est pas une obligation de discuter."
            ),
            color=discord.Color.from_rgb(105, 125, 220),
        )
        embed.set_footer(text="HORIZONS • Panneau permanent • Tes choix restent sous ton contrôle")
        return embed

    async def affinity_interests(self, interaction: discord.Interaction):
        try:
            categories = load_affinity_roles()
        except (OSError, ValueError, TypeError):
            await interaction.response.send_message("Le catalogue des rôles est indisponible.", ephemeral=True)
            return
        role_ids = {role.id for role in interaction.user.roles}
        summary = []
        for category, ids in categories.items():
            selected = [role.name for role in interaction.user.roles if role.id in ids]
            if selected:
                summary.append(f"**{category} :** " + ", ".join(discord.utils.escape_markdown(x) for x in selected[:12]))
        embed = horizons_embed(
            title="🎭 Mes centres d'intérêt",
            description=("\n".join(summary) if summary else "Tu n'as pas encore choisi de rôles d'intérêt.")
            + "\n\nPour modifier tes choix, utilise le panneau **🎭・choix-des-rôles** déjà présent sur le serveur.",
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def ensure_explanation(self, channel_id: int, setting_key: str, embed: discord.Embed, view: discord.ui.View | None = None):
        """Un seul panneau par salon, même après perte de son identifiant SQLite."""
        if not channel_id:
            return
        with db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (setting_key,)).fetchone()
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
        if not isinstance(channel, discord.TextChannel):
            return

        message = None
        if row:
            try:
                message = await channel.fetch_message(int(row["value"]))
                if message.author.id != self.bot.user.id:
                    message = None
            except (ValueError, TypeError, discord.NotFound):
                message = None
            except (discord.Forbidden, discord.HTTPException):
                return

        # Si la base a été restaurée, retrouver le panneau existant avant de publier.
        if message is None:
            try:
                async for candidate in channel.history(limit=100):
                    if candidate.author.id != self.bot.user.id:
                        continue
                    if any(e.title == embed.title for e in candidate.embeds):
                        message = candidate
                        break
            except (discord.Forbidden, discord.HTTPException):
                return

        if message is not None:
            needs_embed = not message.embeds or message.embeds[0].to_dict() != embed.to_dict()
            needs_buttons = view is not None and not message.components
            if needs_embed or needs_buttons:
                try:
                    await message.edit(embed=embed, view=view)
                except (discord.Forbidden, discord.HTTPException):
                    return
        else:
            try:
                message = await channel.send(embed=embed, view=view,
                                             allowed_mentions=discord.AllowedMentions.none())
            except (discord.Forbidden, discord.HTTPException):
                return
        with db() as conn:
            conn.execute(
                "INSERT INTO bot_settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (setting_key, str(message.id)),
            )

    @app_commands.command(name="humeur", description="Enregistrer ton humeur du jour en privé.")
    @app_commands.choices(mood=MOODS)
    async def humeur(self, interaction: discord.Interaction, mood: app_commands.Choice[str]):
        if interaction.guild_id != GUILD_ID:
            await interaction.response.send_message("Cette commande est réservée au serveur HORIZONS.", ephemeral=True)
            return
        now = datetime.now(timezone.utc).isoformat()
        with db() as conn:
            conn.execute(
                "INSERT INTO mood_entries(guild_id,user_id,mood_date,mood,created_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(guild_id,user_id,mood_date) DO UPDATE SET mood=excluded.mood,created_at=excluded.created_at",
                (interaction.guild_id, interaction.user.id, today_local(), mood.value, now),
            )
            cutoff = (datetime.now(LOCAL_TIMEZONE).date() - timedelta(days=90)).isoformat()
            conn.execute("DELETE FROM mood_entries WHERE mood_date < ?", (cutoff,))
        extra = (
            "\nSi tu souhaites parler à l'équipe en privé, tu peux utiliser `/ticket_ouvrir`."
            if mood.value == "Besoin de parler" else ""
        )
        await interaction.response.send_message(
            f"Ton humeur du jour a été enregistrée en privé : **{mood.value}**. 💜\n"
            "Tu peux la modifier en relançant `/humeur`." + extra,
            ephemeral=True,
        )

    @app_commands.command(name="ma_meteo", description="Consulter ton humeur du jour en privé.")
    async def ma_meteo(self, interaction: discord.Interaction):
        with db() as conn:
            row = conn.execute(
                "SELECT mood,created_at FROM mood_entries WHERE guild_id=? AND user_id=? AND mood_date=?",
                (interaction.guild_id or 0, interaction.user.id, today_local()),
            ).fetchone()
        if not row:
            await interaction.response.send_message("Tu n'as pas encore renseigné ton humeur aujourd'hui. Utilise `/humeur` si tu le souhaites.", ephemeral=True)
            return
        await interaction.response.send_message(f"Ta météo du jour : **{row['mood']}**. 💜", ephemeral=True)

    async def unlock(self, guild: discord.Guild, member: discord.Member, key: str):
        title, description = ACHIEVEMENTS[key]
        with db() as conn:
            inserted = conn.execute(
                "INSERT OR IGNORE INTO success_unlocks(guild_id,user_id,achievement_key,unlocked_at) VALUES(?,?,?,?)",
                (guild.id, member.id, key, datetime.now(timezone.utc).isoformat()),
            ).rowcount
        if not inserted:
            return
        channel = guild.get_channel(SUCCESS_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(SUCCESS_CHANNEL_ID)
            except discord.HTTPException:
                return
        if isinstance(channel, discord.TextChannel):
            embed = horizons_embed(
                title=f"🏆 Succès débloqué : {title}",
                description=f"Bravo {member.mention} !\n{description}",
                color=discord.Color.gold(),
            )
            embed.set_footer(text="HORIZONS • Chaque petit pas compte")
            try:
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
            except discord.HTTPException:
                pass

    async def check_achievements(self, guild: discord.Guild, member: discord.Member):
        with db() as conn:
            active_days = conn.execute(
                "SELECT COUNT(*) FROM success_activity_days WHERE guild_id=? AND user_id=?",
                (guild.id, member.id),
            ).fetchone()[0]
            missions = conn.execute(
                "SELECT COUNT(*) FROM passport_completions WHERE guild_id=? AND user_id=? AND week_key=?",
                (guild.id, member.id, current_week_key()),
            ).fetchone()[0]
        if active_days >= 1:
            await self.unlock(guild, member, "first_day")
        if active_days >= 7:
            await self.unlock(guild, member, "seven_days")
        if active_days >= 30:
            await self.unlock(guild, member, "thirty_days")
        if missions >= 3:
            await self.unlock(guild, member, "passport_week")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.id in getattr(self.bot, "automod_blocked_message_ids", set()):
            return
        if not message.guild or message.author.bot or not isinstance(message.author, discord.Member):
            return
        if len(message.content.strip()) < 25 or message.content.startswith(("/", "!")):
            return
        day = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO success_activity_days(guild_id,user_id,active_date) VALUES(?,?,?)",
                (message.guild.id, message.author.id, day),
            )
        await self.check_achievements(message.guild, message.author)

    @app_commands.command(name="mes_succes", description="Consulter tes succès HORIZONS débloqués.")
    async def mes_succes(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande disponible sur HORIZONS.", ephemeral=True)
            return
        await self.check_achievements(interaction.guild, interaction.user)
        with db() as conn:
            rows = conn.execute(
                "SELECT achievement_key,unlocked_at FROM success_unlocks WHERE guild_id=? AND user_id=? ORDER BY unlocked_at",
                (interaction.guild_id, interaction.user.id),
            ).fetchall()
        embed = horizons_embed(title="🏆 Tes succès HORIZONS", color=discord.Color.gold())
        if rows:
            embed.description = "\n".join(
                f"**{ACHIEVEMENTS[row['achievement_key']][0]}**\n{ACHIEVEMENTS[row['achievement_key']][1]}"
                for row in rows
            )
        else:
            embed.description = "Aucun succès débloqué pour le moment. Chaque participation peut être un premier pas !"
        embed.set_footer(text=f"{len(rows)}/{len(ACHIEVEMENTS)} succès débloqués")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @affinites.command(name="activer", description="Autoriser les suggestions d'affinités amicales.")
    async def affinites_activer(self, interaction: discord.Interaction):
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO affinity_optins(guild_id,user_id,enabled_at) VALUES(?,?,?)",
                (interaction.guild_id or 0, interaction.user.id, datetime.now(timezone.utc).isoformat()),
            )
        await interaction.response.send_message(
            "Ton profil est maintenant volontaire pour les suggestions d'affinités. "
            "Complète tes rôles de centres d'intérêt, langues et jeux, puis utilise `/affinites trouver`. 💜",
            ephemeral=True,
        )

    @affinites.command(name="desactiver", description="Retirer ton profil des suggestions d'affinités.")
    async def affinites_desactiver(self, interaction: discord.Interaction):
        with db() as conn:
            conn.execute(
                "DELETE FROM affinity_optins WHERE guild_id=? AND user_id=?",
                (interaction.guild_id or 0, interaction.user.id),
            )
        await interaction.response.send_message("Ton profil a été retiré des suggestions d'affinités. 💜", ephemeral=True)

    @affinites.command(name="trouver", description="Trouver des membres volontaires qui partagent tes centres d'intérêt.")
    async def affinites_chercher(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message("Commande disponible sur HORIZONS.", ephemeral=True)
            return
        with db() as conn:
            opted = conn.execute(
                "SELECT 1 FROM affinity_optins WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()
            candidates = conn.execute(
                "SELECT user_id FROM affinity_optins WHERE guild_id=? AND user_id<>?",
                (interaction.guild_id, interaction.user.id),
            ).fetchall()
        if not opted:
            await interaction.response.send_message("Active d'abord ton profil avec `/affinites activer`. Tu gardes le contrôle de ta participation.", ephemeral=True)
            return
        try:
            categories = load_affinity_roles()
        except (OSError, ValueError, TypeError):
            await interaction.response.send_message("Le catalogue des rôles est indisponible. Préviens l'équipe HORIZONS.", ephemeral=True)
            return
        allowed_ids = set().union(*categories.values()) if categories else set()
        own_ids = {role.id for role in interaction.user.roles} & allowed_ids
        if not own_ids:
            await interaction.response.send_message("Choisis d'abord quelques rôles de langues, centres d'intérêt, jeux ou musique dans 🎭・choix-des-rôles.", ephemeral=True)
            return
        matches = []
        for row in candidates:
            member = interaction.guild.get_member(int(row["user_id"]))
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(int(row["user_id"]))
                except discord.HTTPException:
                    continue
            if member.bot:
                continue
            shared = own_ids & {role.id for role in member.roles} & allowed_ids
            if len(shared) >= 2:
                matching_categories = [
                    name for name, role_ids in categories.items() if shared & role_ids
                ]
                matches.append((len(shared), member, matching_categories))
        matches.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
        if not matches:
            await interaction.response.send_message(
                "Je n'ai pas encore trouvé de membre volontaire avec au moins deux affinités communes. "
                "Tu peux compléter tes rôles et réessayer plus tard.",
                ephemeral=True,
            )
            return
        embed = horizons_embed(title="🌍 Tes affinités HORIZONS", color=discord.Color.blurple())
        for score, member, labels in matches[:5]:
            embed.add_field(
                name=member.display_name,
                value=f"**{score}** rôle(s) en commun\n" + ", ".join(labels),
                inline=False,
            )
        embed.set_footer(text="Résultats privés • Les deux membres doivent être volontaires • Aucun DM automatique")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HorizonsFeatures(bot))

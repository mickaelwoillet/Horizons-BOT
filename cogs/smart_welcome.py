"""Accueil intelligent HORIZONS : parcours guidé, suivi privé et rappel unique."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    WELCOME_CHANNEL_ID, CHARTER_CHANNEL_ID, INTRO_CHANNEL_ID,
    NEW_MEMBER_ROLE_ID, MEMBER_ROLE_ID, GUILD_ID,
)
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
from cogs.storage import db

logger = logging.getLogger("horizons.smart_welcome")
WELCOME_MARKER = "HORIZONS_SMART_WELCOME_V1"
REMINDER_AFTER = timedelta(hours=36)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_table() -> None:
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_progress (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                charter_accepted INTEGER NOT NULL DEFAULT 0,
                intro_posted INTEGER NOT NULL DEFAULT 0,
                participated INTEGER NOT NULL DEFAULT 0,
                reminder_sent INTEGER NOT NULL DEFAULT 0,
                completed_at TEXT,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_onboarding_followup
            ON onboarding_progress(guild_id, participated, reminder_sent, joined_at)
        """)


class WelcomeView(discord.ui.View):
    """Boutons de navigation vers les étapes essentielles."""

    def __init__(self):
        super().__init__(timeout=None)
        if CHARTER_CHANNEL_ID:
            self.add_item(discord.ui.Button(
                label="Lire la charte", emoji="📜", style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{CHARTER_CHANNEL_ID}"
            ))
        if INTRO_CHANNEL_ID:
            self.add_item(discord.ui.Button(
                label="Se présenter", emoji="👋", style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{INTRO_CHANNEL_ID}"
            ))


class SmartWelcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        ensure_table()
        self.followup_loop.start()

    async def cog_unload(self):
        self.followup_loop.cancel()

    def _upsert_join(self, member: discord.Member) -> None:
        with db() as conn:
            conn.execute("""
                INSERT INTO onboarding_progress(guild_id, user_id, joined_at, charter_accepted)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    joined_at=excluded.joined_at,
                    charter_accepted=excluded.charter_accepted,
                    intro_posted=0, participated=0, reminder_sent=0, completed_at=NULL
            """, (
                member.guild.id, member.id, utc_now().isoformat(),
                int(bool(MEMBER_ROLE_ID and discord.utils.get(member.roles, id=MEMBER_ROLE_ID)))
            ))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if GUILD_ID and member.guild.id != GUILD_ID:
            return
        self._upsert_join(member)
        await wait_for_logo_ready()
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID) if WELCOME_CHANNEL_ID else None
        if channel is None:
            logger.warning("Salon de bienvenue introuvable ou non configuré.")
            return

        embed = horizons_embed(
            title="🌅 Bienvenue dans HORIZONS !",
            description=(
                f"Bienvenue {member.mention} ! 💜\n\n"
                "Nous sommes heureux de t'accueillir. Tu peux prendre le temps de découvrir la communauté, "
                "sans obligation de te présenter immédiatement.\n\n"
                "**Pour commencer, voici trois petits pas :**\n"
                "📜 **1. Découvrir la charte** : lis-la puis utilise le bouton d'acceptation dans le salon dédié.\n"
                "👋 **2. Faire connaissance** : présente-toi si tu en as envie.\n"
                "🧭 **3. Explorer** : découvre les salons, les expériences et les animations à ton rythme.\n\n"
                "Tu peux simplement observer au début. Ici, chacun avance à son rythme : bienvenue chez toi ! ✨"
            ),
            color=discord.Color.gold(),
        )
        embed.set_author(name=f"Membre : {member.display_name}", icon_url=member.display_avatar.url)
        embed.set_footer(text=WELCOME_MARKER)
        try:
            await channel.send(embed=embed, view=WelcomeView(), allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            logger.exception("Impossible d'envoyer l'accueil guidé pour %s.", member.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not MEMBER_ROLE_ID:
            return
        had_role = any(role.id == MEMBER_ROLE_ID for role in before.roles)
        has_role = any(role.id == MEMBER_ROLE_ID for role in after.roles)
        if had_role or not has_role:
            return
        with db() as conn:
            conn.execute("""
                UPDATE onboarding_progress
                SET charter_accepted=1,
                    completed_at=CASE WHEN intro_posted=1 THEN ? ELSE completed_at END
                WHERE guild_id=? AND user_id=?
            """, (utc_now().isoformat(), after.guild.id, after.id))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.webhook_id:
            return
        if GUILD_ID and message.guild.id != GUILD_ID:
            return
        # Toute participation volontaire dans un salon textuel compte ; les messages système/bots sont exclus.
        with db() as conn:
            conn.execute("""
                UPDATE onboarding_progress SET participated=1
                WHERE guild_id=? AND user_id=?
            """, (message.guild.id, message.author.id))
            if INTRO_CHANNEL_ID and message.channel.id == INTRO_CHANNEL_ID:
                conn.execute("""
                    UPDATE onboarding_progress SET intro_posted=1
                    WHERE guild_id=? AND user_id=?
                """, (message.guild.id, message.author.id))

    @tasks.loop(hours=1)
    async def followup_loop(self):
        if not GUILD_ID:
            return
        cutoff = (utc_now() - REMINDER_AFTER).isoformat()
        with db() as conn:
            rows = conn.execute("""
                SELECT user_id FROM onboarding_progress
                WHERE guild_id=? AND participated=0 AND reminder_sent=0 AND joined_at<=?
            """, (GUILD_ID, cutoff)).fetchall()
            # Marquer avant l'envoi : un DM fermé ne doit pas provoquer des tentatives répétées.
            ids = [int(row["user_id"]) for row in rows]
            if ids:
                conn.executemany("""
                    UPDATE onboarding_progress SET reminder_sent=1
                    WHERE guild_id=? AND user_id=?
                """, [(GUILD_ID, uid) for uid in ids])

        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        for user_id in ids:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            try:
                await member.send(
                    "🌅 Petit coucou de HORIZONS !\n\n"
                    "Nous espérons que tu te sens bien parmi nous. Si tu le souhaites, "
                    "tu peux reprendre tranquillement ton parcours en découvrant la charte, "
                    "les présentations et les salons qui t'intéressent. Aucune obligation : "
                    "prends ton temps, nous sommes heureux de t'accueillir. 💜"
                )
            except discord.Forbidden:
                logger.info("Rappel d'accueil non envoyé (DM fermés) pour %s.", user_id)
            except discord.HTTPException:
                logger.warning("Échec Discord lors du rappel d'accueil pour %s.", user_id)

    @followup_loop.before_loop
    async def before_followup_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="accueil_bilan", description="Consulter le suivi privé des nouveaux membres HORIZONS.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def accueil_bilan(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("Cette commande est réservée au serveur HORIZONS.", ephemeral=True)
            return
        since = (utc_now() - timedelta(days=7)).isoformat()
        with db() as conn:
            total = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=?
            """, (interaction.guild.id, since)).fetchone()[0]
            charter = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND charter_accepted=1
            """, (interaction.guild.id, since)).fetchone()[0]
            intro = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND intro_posted=1
            """, (interaction.guild.id, since)).fetchone()[0]
            quiet = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND participated=0
            """, (interaction.guild.id, since)).fetchone()[0]
            reminded = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND reminder_sent=1
            """, (interaction.guild.id, since)).fetchone()[0]
        embed = horizons_embed(
            title="🧭 Accueil intelligent — bilan des 7 derniers jours",
            description=(
                f"**Nouveaux membres suivis :** {total}\n"
                f"**Charte acceptée :** {charter}\n"
                f"**Présentation publiée :** {intro}\n"
                f"**Aucune participation détectée :** {quiet}\n"
                f"**Rappels privés tentés :** {reminded}\n\n"
                "Ces indicateurs servent à améliorer l'accueil, pas à juger les membres. "
                "Une personne peut choisir de lire et d'observer sans écrire."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartWelcome(bot))

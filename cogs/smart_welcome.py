"""Accueil intelligent HORIZONS : parcours guidé, suivi privé et rappel unique."""
from __future__ import annotations

import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    DATA_DIR, WELCOME_CHANNEL_ID, CHARTER_CHANNEL_ID, INTRO_CHANNEL_ID,
    DAILY_QUESTION_CHANNEL_ID, NEW_MEMBER_ROLE_ID, MEMBER_ROLE_ID, GUILD_ID,
    STAFF_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID,
)
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
from cogs.storage import db

logger = logging.getLogger("horizons.smart_welcome")
WELCOME_MARKER = "HORIZONS_SMART_WELCOME_V1"
REMINDER_AFTER = timedelta(hours=36)

# Images livrées avec le bot, jamais hébergées sur un service externe.
WELCOME_IMAGE_PATHS = (
    DATA_DIR / "welcome_images" / "activites.webp",
    DATA_DIR / "welcome_images" / "commandes.webp",
    DATA_DIR / "welcome_images" / "parcours.webp",
)


def build_charter_welcome(member: discord.Member) -> discord.Embed:
    """Message privé envoyé uniquement lors de l'attribution du rôle Membre."""
    safe_name = discord.utils.escape_markdown(member.display_name)
    embed = horizons_embed(
        title="🌌 Bienvenue dans l'univers HORIZONS !",
        description=(
            f"Coucou **{safe_name}** ! 💙\n\n"
            "Une nouvelle étoile vient de rejoindre notre ciel… **et cette étoile, c'est toi !** ✨\n\n"
            "Ta charte est validée et ton aventure commence ! Tu trouveras ici des échanges, "
            "des jeux, des événements et des découvertes, toujours à ton rythme.\n\n"
            "🎮 **Les activités** : tout ce que tu peux vivre sur le serveur.\n"
            "🧭 **Les commandes** : les raccourcis essentiels.\n"
            "🌠 **Ton parcours** : trois étapes pour prendre tes repères.\n\n"
            "**Pour commencer, utilise `/centre` sur le serveur.** "
            "Et si tu as une question, `/aide` est là pour toi.\n\n"
            "Prends ton temps, découvre et surtout, sois toi-même. 💜"
        ),
        color=discord.Color.from_rgb(111, 69, 193),
    )
    embed.set_footer(text="HORIZONS • Avec toute la bienveillance de l'équipe")
    return embed


async def send_charter_welcome(member: discord.Member) -> None:
    """Envoi unique : un MP avec jusqu'à trois images, sans relance automatique."""
    from contextlib import ExitStack
    with ExitStack() as stack:
        files = []
        for path in WELCOME_IMAGE_PATHS:
            if not path.is_file():
                logger.warning("Affiche d'accueil absente : %s", path)
                continue
            files.append(discord.File(stack.enter_context(path.open("rb")), filename=path.name))
        await member.send(
            embed=build_charter_welcome(member),
            files=files,
            view=DiscoveryLinksView(member.guild),
            allowed_mentions=discord.AllowedMentions.none(),
        )



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
                charter_welcome_sent INTEGER NOT NULL DEFAULT 0,
                profile_customized INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_onboarding_followup
            ON onboarding_progress(guild_id, participated, reminder_sent, joined_at)
        """)
        # Migration non destructive : les anciennes bases conservent leur historique.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(onboarding_progress)").fetchall()}
        if "charter_welcome_sent" not in columns:
            conn.execute(
                "ALTER TABLE onboarding_progress ADD COLUMN charter_welcome_sent INTEGER NOT NULL DEFAULT 0"
            )
        if "profile_customized" not in columns:
            conn.execute(
                "ALTER TABLE onboarding_progress ADD COLUMN profile_customized INTEGER NOT NULL DEFAULT 0"
            )


class WelcomeView(discord.ui.View):
    """Boutons de navigation vers les étapes essentielles."""

    def __init__(self):
        super().__init__(timeout=None)
        if CHARTER_CHANNEL_ID:
            self.add_item(discord.ui.Button(
                label="Lire la charte", emoji="📜", style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{GUILD_ID}/{CHARTER_CHANNEL_ID}"
            ))
        self.add_item(ExploreButton())
        # La présentation n'est accessible qu'après validation de la charte.
        # On évite donc de proposer un lien prématuré depuis le premier accueil.


class ExploreButton(discord.ui.Button):
    """Bouton persistant, réponse privée et respect de la charte."""
    def __init__(self):
        super().__init__(
            label="Découvrir HORIZONS", emoji="🧭",
            style=discord.ButtonStyle.primary,
            custom_id="horizons:welcome:explore:v1",
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Ce parcours est disponible sur HORIZONS.", ephemeral=True)
            return
        if MEMBER_ROLE_ID and not any(role.id == MEMBER_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "📜 Pour découvrir les espaces, commence par accepter la charte. "
                "Tu pourras ensuite revenir à ce bouton.", ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=build_first_steps_embed(),
            view=DiscoveryLinksView(interaction.guild),
            ephemeral=True,
        )


class DiscoveryLinksView(discord.ui.View):
    """Liens directs proposés après validation de la charte."""

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        links = []
        if CHARTER_CHANNEL_ID:
            links.append(("Charte", "📜", CHARTER_CHANNEL_ID))
        if INTRO_CHANNEL_ID:
            links.append(("Présentation", "👋", INTRO_CHANNEL_ID))
        if DAILY_QUESTION_CHANNEL_ID:
            links.append(("Question du jour", "❓", DAILY_QUESTION_CHANNEL_ID))
        roles_channel = next(
            (channel for channel in guild.text_channels
             if "choix-des-rôles" in channel.name.casefold() or "choix-des-roles" in channel.name.casefold()),
            None,
        )
        if roles_channel:
            links.insert(1, ("Choisir mes rôles", "🎭", roles_channel.id))
        for label, emoji, channel_id in links[:5]:
            self.add_item(discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/{channel_id}",
            ))


def build_first_steps_embed() -> discord.Embed:
    embed = horizons_embed(
        title="🧭 Tes premiers pas sur HORIZONS",
        description=(
            "Tu as maintenant accès à la communauté ! 💜\n\n"
            "Il n'y a aucun parcours obligatoire à suivre et tu n'as pas besoin de tout faire aujourd'hui. "
            "Voici quelques portes que tu peux ouvrir, dans l'ordre qui te convient."
        ),
        color=discord.Color.teal(),
    )
    embed.add_field(
        name="🎭 1. Personnalise ton expérience",
        value="Dans **choix-des-rôles**, sélectionne les centres d'intérêt, langues, jeux ou préférences que tu souhaites afficher. Les choix personnels restent facultatifs.",
        inline=False,
    )
    embed.add_field(
        name="💬 2. Fais un premier petit pas",
        value="Tu peux répondre à la question du jour, réagir à une publication ou simplement parcourir les discussions. Aucune présentation n'est exigée.",
        inline=False,
    )
    embed.add_field(
        name="🌅 3. Explore à ton rythme",
        value="Commence par **`/centre`** : ton espace privé t’accueille par ton pseudo, affiche ta Carte du Ciel et te guide vers les activités. Le parcours HORIZONS reste facultatif. Pour les autres commandes, consulte **`/aide`**.",
        inline=False,
    )
    embed.add_field(
        name="🤝 4. Tu n'es pas seul",
        value="Si tu as une question, tu peux contacter l'équipe ou utiliser les espaces d'entraide. Tu peux aussi rester discret le temps de prendre tes repères.",
        inline=False,
    )
    embed.set_footer(text="HORIZONS • Tu es libre d'avancer à ton rythme")
    return embed


class SmartWelcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        ensure_table()
        self.bot.add_view(WelcomeView())
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
                    intro_posted=0, participated=0, reminder_sent=0, completed_at=NULL,
                    charter_welcome_sent=0, profile_customized=0
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

        from .nox_identity import send_as_nox
        choices = json.loads((DATA_DIR / "nox" / "accueils.json").read_text(encoding="utf-8"))
        index = int.from_bytes(hashlib.sha256(f"{member.guild.id}:{member.id}".encode()).digest()[:4], "big") % len(choices)
        content = choices[index]["texte"].replace("{mention}", member.mention)
        try:
            # Les boutons de charte et découverte restent sur le message de NOX.
            await send_as_nox(channel, content=content, view=WelcomeView(),
                              allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False))
        except discord.HTTPException:
            logger.exception("Webhook NOX indisponible : accueil via bot pour %s", member.id)
            try:
                await channel.send(content=content, view=WelcomeView(),
                                   allowed_mentions=discord.AllowedMentions(users=[member], roles=False, everyone=False))
            except discord.HTTPException:
                logger.exception("Impossible d'envoyer l'accueil pour %s", member.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not MEMBER_ROLE_ID:
            return
        had_role = any(role.id == MEMBER_ROLE_ID for role in before.roles)
        has_role = any(role.id == MEMBER_ROLE_ID for role in after.roles)
        if had_role or not has_role:
            return
        if GUILD_ID and after.guild.id != GUILD_ID:
            return
        now = utc_now().isoformat()
        with db() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO onboarding_progress(guild_id, user_id, joined_at, charter_accepted)
                VALUES (?, ?, ?, 1)
            """, (after.guild.id, after.id, now))
            row = conn.execute("""
                SELECT charter_welcome_sent FROM onboarding_progress
                WHERE guild_id=? AND user_id=?
            """, (after.guild.id, after.id)).fetchone()
            should_send_guide = bool(row and not row["charter_welcome_sent"])
            conn.execute("""
                UPDATE onboarding_progress
                SET charter_accepted=1,
                    completed_at=CASE WHEN intro_posted=1 THEN ? ELSE completed_at END
                WHERE guild_id=? AND user_id=?
            """, (now, after.guild.id, after.id))

        if not should_send_guide:
            logger.info("Guide déjà envoyé à %s : aucun doublon.", after.id)
            return
        try:
            await send_charter_welcome(after)
        except discord.Forbidden:
            logger.warning("MP de bienvenue refusé par Discord pour %s (MP fermés ou bloqués).", after.id)
        except discord.HTTPException:
            logger.exception("Échec Discord lors de l'envoi du MP illustré à %s.", after.id)
        except Exception:
            logger.exception("Erreur inattendue lors de l'envoi du MP illustré à %s.", after.id)
        else:
            with db() as conn:
                conn.execute("""
                    UPDATE onboarding_progress SET charter_welcome_sent=1
                    WHERE guild_id=? AND user_id=?
                """, (after.guild.id, after.id))
            logger.info("Bienvenue illustrée envoyée avec succès après validation de la charte (%s).", after.id)

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

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Les commandes slash, boutons et menus comptent comme une première interaction.
        if not interaction.guild_id or interaction.user.bot:
            return
        if GUILD_ID and interaction.guild_id != GUILD_ID:
            return
        if interaction.type not in {
            discord.InteractionType.application_command,
            discord.InteractionType.component,
            discord.InteractionType.modal_submit,
        }:
            return
        with db() as conn:
            conn.execute(
                "UPDATE onboarding_progress SET participated=1 WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, interaction.user.id),
            )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id or (self.bot.user and payload.user_id == self.bot.user.id):
            return
        if GUILD_ID and payload.guild_id != GUILD_ID:
            return
        with db() as conn:
            conn.execute(
                "UPDATE onboarding_progress SET participated=1 WHERE guild_id=? AND user_id=?",
                (payload.guild_id, payload.user_id),
            )

    @tasks.loop(hours=1)
    async def followup_loop(self):
        if not GUILD_ID:
            return
        cutoff = (utc_now() - REMINDER_AFTER).isoformat()
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        with db() as conn:
            rows = conn.execute("""
                SELECT user_id, charter_accepted FROM onboarding_progress
                WHERE guild_id=? AND participated=0 AND reminder_sent=0 AND joined_at<=?
            """, (GUILD_ID, cutoff)).fetchall()
            # Marquer avant l'envoi : un DM fermé ne doit pas provoquer des tentatives répétées.
            pending = [(int(row["user_id"]), bool(row["charter_accepted"])) for row in rows]
            if pending:
                conn.executemany("""
                    UPDATE onboarding_progress SET reminder_sent=1
                    WHERE guild_id=? AND user_id=?
                """, [(GUILD_ID, uid) for uid, _ in pending])

        for user_id, charter_accepted in pending:
            member = guild.get_member(user_id)
            if member is None:
                try:
                    member = await guild.fetch_member(user_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
            try:
                if not charter_accepted:
                    await member.send(
                        "🌅 Petit coucou de HORIZONS !\n\n"
                        "Si tu souhaites poursuivre ton arrivée, tu peux retrouver la charte dans le salon "
                        "📏・la-charte. Sa validation te donnera accès aux autres espaces.\n\n"
                        "Aucune urgence : prends le temps qu'il te faut. 💜"
                    )
                else:
                    await member.send(
                        "🌅 Petit coucou de HORIZONS !\n\n"
                        "Si tu souhaites découvrir quelques espaces, utilise le bouton "
                        "**Découvrir HORIZONS** dans le salon de bienvenue.\n\n"
                        "Tu peux aussi simplement observer et avancer à ton rythme. 💜"
                    )
            except discord.Forbidden:
                logger.info("Rappel d'accueil non envoyé (DM fermés) pour %s.", user_id)
            except discord.HTTPException:
                logger.warning("Échec Discord lors du rappel d'accueil pour %s.", user_id)

    @followup_loop.before_loop
    async def before_followup_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="premiers_pas", description="Retrouver ton guide de découverte et les liens utiles HORIZONS.")
    async def premiers_pas(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild is None:
            await interaction.response.send_message("Cette commande est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        if MEMBER_ROLE_ID and not any(role.id == MEMBER_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "🌱 Pour accéder au guide, commence par lire et accepter la charte dans **📏・la-charte**. Tu pourras ensuite revenir ici.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=build_first_steps_embed(),
            view=DiscoveryLinksView(interaction.guild),
            ephemeral=True,
        )

    @staticmethod
    def _authorized_staff(interaction: discord.Interaction) -> bool:
        """Contrôle réel côté bot (les permissions Discord seules sont modifiables)."""
        member = interaction.user
        if not isinstance(member, discord.Member) or interaction.guild is None:
            return False
        if GUILD_ID and interaction.guild.id != GUILD_ID:
            return False
        return bool(
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
            or any(role.id in {STAFF_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID} for role in member.roles)
        )

    @staticmethod
    async def _manual_welcome(interaction: discord.Interaction, target: discord.Member, *, test: bool) -> None:
        """Envoie le vrai guide sans modifier l'historique d'accueil ni les rôles."""
        if not SmartWelcome._authorized_staff(interaction):
            await interaction.response.send_message("⛔ Cette commande est réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("⛔ Le guide ne peut pas être envoyé à un bot.", ephemeral=True)
            return
        if not test and MEMBER_ROLE_ID and not any(role.id == MEMBER_ROLE_ID for role in target.roles):
            await interaction.response.send_message(
                "📜 Ce membre n'a pas encore le rôle Membre. Attends sa validation de la charte.",
                ephemeral=True,
            )
            return
        # Accusé de réception avant l'envoi : une interaction Discord expire rapidement.
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await send_charter_welcome(target)
        except discord.Forbidden:
            logger.warning("Guide manuel refusé par Discord : membre=%s, staff=%s", target.id, interaction.user.id)
            await interaction.followup.send(
                "❌ Discord a refusé le MP (messages privés fermés ou bot bloqué). Aucun statut modifié.",
                ephemeral=True,
            )
        except discord.HTTPException as exc:
            logger.warning("Erreur Discord du guide manuel : membre=%s, erreur=%s", target.id, exc)
            await interaction.followup.send(
                f"❌ Discord n'a pas pu envoyer le guide (code {getattr(exc, 'status', 'inconnu')}). Aucun statut modifié.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("Erreur inattendue lors du guide manuel : membre=%s", target.id)
            await interaction.followup.send("❌ Une erreur est survenue. Consulte la console ; aucun statut modifié.", ephemeral=True)
        else:
            logger.info("Guide %s envoyé manuellement : membre=%s, staff=%s", "test" if test else "renvoi", target.id, interaction.user.id)
            await interaction.followup.send(
                ("✅ MP de test envoyé avec les affiches. " if test else f"✅ Guide renvoyé à {target.mention}. ")
                + "Aucun rôle ni historique d'accueil n'a été modifié.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def test_bienvenue_mp(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande disponible uniquement sur le serveur.", ephemeral=True)
            return
        await self._manual_welcome(interaction, interaction.user, test=True)

    async def renvoyer_bienvenue(self, interaction: discord.Interaction, membre: discord.Member):
        await self._manual_welcome(interaction, membre, test=False)

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
            guides = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND charter_welcome_sent=1
            """, (interaction.guild.id, since)).fetchone()[0]
            customized = conn.execute("""
                SELECT COUNT(*) FROM onboarding_progress WHERE guild_id=? AND joined_at>=? AND profile_customized=1
            """, (interaction.guild.id, since)).fetchone()[0]
        embed = horizons_embed(
            title="🧭 Accueil intelligent — bilan des 7 derniers jours",
            description=(
                f"**Nouveaux membres suivis :** {total}\n"
                f"**Charte acceptée :** {charter}\n"
                f"**Présentation publiée :** {intro}\n"
                f"**Aucune participation détectée :** {quiet}\n"
                f"**Guides après charte proposés :** {guides}\n"
                f"**Profils personnalisés (centres d'intérêt et préférences non sensibles) :** {customized}\n"
                f"**Rappels privés tentés :** {reminded}\n\n"
                "Ces indicateurs servent à améliorer l'accueil, pas à juger les membres. "
                "Une personne peut choisir de lire et d'observer sans écrire."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SmartWelcome(bot))

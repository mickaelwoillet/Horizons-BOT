"""Point d'entrée du bot Discord HORIZONS.

Les fonctionnalités sont isolées dans des extensions du dossier cogs/.
Les secrets et identifiants sont fournis par le fichier .env (jamais codés ici).
"""
from __future__ import annotations

import asyncio
import logging
import json
import os
import sys
from typing import Final

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    BASE_DIR, DISCORD_TOKEN, GUILD_ID, STAFF_ROLE_ID, ALERT_LOG_CHANNEL_ID,
    JOKE_DAILY_CHANNEL_ID, RIDDLE_DAILY_CHANNEL_ID, LOG_CHANNEL_ID,
    MOD_LOG_CHANNEL_ID, WELCOME_CHANNEL_ID, LEAVE_CHANNEL_ID, STAFF_COMMANDS_CHANNEL_ID,
    BIRTHDAY_CHANNEL_ID, SUGGESTION_CHANNEL_ID, INTRO_CHANNEL_ID,
    ANONYMOUS_CHANNEL_ID, DAILY_QUESTION_CHANNEL_ID, QUIZ_CHANNEL_ID, TEMP_VOICE_TRIGGER_ID,
    TEMP_VOICE_CATEGORY_ID, TICKET_CATEGORY_ID, AUTO_MOD_ENABLED,
    BLOCK_DISCORD_INVITES, TRANSLATE_API_URL, TRANSLATE_API_KEY, RANK_ROLE_IDS, DEFAULT_ANNOUNCEMENT_IMAGE_URL,
    TIMEZONE_NAME, LOCAL_TIMEZONE, COGS_DIR, DATA_DIR, LOG_DIR,
)

# Identité visuelle : le logo est publié une seule fois comme pièce jointe Discord.
from cogs.embed_theme import LOGO_PATH, LOGO_STATE_PATH, set_logo_url

_LOGO_SETUP_LOCK = asyncio.Lock()
_LOGO_SETUP_ATTEMPTED = False
# Référence du dépôt déjà présent sur Discord et consignée dans le ZIP fourni.
LOGO_FALLBACK_CHANNEL_ID = 1566562235793416242
LOGO_FALLBACK_MESSAGE_ID = 1567595402247667802


async def ensure_horizons_logo_asset(bot: commands.Bot) -> None:
    """Réutilise un dépôt existant ; ne republie pas si Discord est indisponible.

    Les identifiants du ZIP peuvent être périmés sur l'hébergement : rechercher
    dans l'historique avant de publier, puis enregistrer le message retrouvé.
    """
    global _LOGO_SETUP_ATTEMPTED
    async with _LOGO_SETUP_LOCK:
        if _LOGO_SETUP_ATTEMPTED:
            return
        _LOGO_SETUP_ATTEMPTED = True
        if not LOGO_PATH.is_file():
            logger.warning("Logo HORIZONS introuvable : %s", LOGO_PATH)
            set_logo_url(bot.user.display_avatar.url if bot.user else None)
            return

        try:
            state = json.loads(LOGO_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (OSError, json.JSONDecodeError):
            state = {}

        def remember(message: discord.Message) -> bool:
            attachments = [a for a in message.attachments if a.filename.lower() == "horizons_logo.png"]
            if not attachments:
                return False
            set_logo_url(attachments[0].url)
            try:
                LOGO_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                temporary = LOGO_STATE_PATH.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps({"channel_id": message.channel.id, "message_id": message.id},
                               ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(LOGO_STATE_PATH)
            except OSError:
                logger.warning("Impossible d'enregistrer la référence du logo ; recherche Discord au prochain démarrage.")
            return True

        # L'historique du salon constitue la référence de secours si le fichier
        # local est réinitialisé à chaque déploiement.
        candidates = []
        for cid in (state.get("channel_id"), LOGO_FALLBACK_CHANNEL_ID,
                    STAFF_COMMANDS_CHANNEL_ID, LOG_CHANNEL_ID):
            if cid and cid not in candidates:
                candidates.append(cid)

        destination = None
        for cid in candidates:
            try:
                channel = bot.get_channel(int(cid)) or await bot.fetch_channel(int(cid))
                if not isinstance(channel, discord.TextChannel):
                    continue
                if destination is None and cid in (STAFF_COMMANDS_CHANNEL_ID, LOG_CHANNEL_ID):
                    destination = channel
                if cid == state.get("channel_id") and state.get("message_id"):
                    try:
                        if remember(await channel.fetch_message(int(state["message_id"]))):
                            return
                    except discord.NotFound:
                        pass
                if cid == LOGO_FALLBACK_CHANNEL_ID:
                    try:
                        if remember(await channel.fetch_message(LOGO_FALLBACK_MESSAGE_ID)):
                            return
                    except discord.NotFound:
                        pass
                async for message in channel.history(limit=200):
                    if message.author.id == bot.user.id and remember(message):
                        logger.info("Dépôt du logo HORIZONS retrouvé dans l'historique Discord.")
                        return
            except (discord.Forbidden, discord.HTTPException, ValueError, AttributeError) as exc:
                # Une erreur réseau/permission ne signifie pas que le message a
                # disparu. Ne jamais republier dans ce cas.
                logger.warning("Recherche du logo impossible (%s) : aucune republication automatique.", exc)
                set_logo_url(bot.user.display_avatar.url if bot.user else None)
                return

        # Ne jamais publier une image technique automatiquement au démarrage.
        # Le logo Discord existant ou l'avatar de l'application servent de secours.
        fallback_avatar = bot.user.display_avatar.url if bot.user else None
        logger.warning("Dépôt du logo introuvable : avatar du bot utilisé sans publication.")
        set_logo_url(fallback_avatar)
        return

# Charger uniquement les extensions présentes. Les extensions pourront être
# ajoutées progressivement sans empêcher le démarrage du bot.
EXTENSIONS: Final[tuple[str, ...]] = (
    "cogs.general",
    "cogs.onboarding",
    "cogs.smart_welcome",
    "cogs.today_hub",
    "cogs.salon_harmony",
    "cogs.visual_identity",
    "cogs.continuity",
    "cogs.moderation",
    "cogs.logging_tools",
    "cogs.birthdays",
    "cogs.announcements",
    "cogs.jokes",
    "cogs.riddles",
    "cogs.community_ranks",
    "cogs.events",
    "cogs.staff_tools",
    "cogs.automod",
    "cogs.voice_rooms",
    "cogs.giveaways",
    "cogs.role_panels",
    "cogs.horizons_features",
    "cogs.community_hub",
    "cogs.staff_dashboard",
    "cogs.horizons_dashboard",
    "cogs.quizzes",
    "cogs.community",
    "cogs.experiences",
    "cogs.seasons",
    "cogs.circle_guides",
    "cogs.server_audit_export",
    "cogs.horizons_daily",
    "cogs.publication_calendar",
    "cogs.weekly_animations",
    "cogs.horizons_path",
    "cogs.server_guides",
    "cogs.tickets",
    "cogs.translation",
    "cogs.horizons_arcade",
    "cogs.celestial_treasures",
)

# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "horizons.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("horizons")


class HorizonsBot(commands.Bot):
    """Bot HORIZONS avec commandes slash synchronisées sur le serveur cible."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        # L'intent de présence n'est volontairement pas activé : inutile
        # pour les fonctions prévues et demande une permission privilégiée.
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.guild_object = discord.Object(id=GUILD_ID) if GUILD_ID else None

    async def setup_hook(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        COGS_DIR.mkdir(parents=True, exist_ok=True)
        from cogs.storage import init_db
        init_db()

        # Extensions optionnelles : les modules seront ajoutés au fil de la
        # reconstruction. Une extension absente est signalée sans bloquer le bot.
        for extension in EXTENSIONS:
            module_path = BASE_DIR.joinpath(*extension.split(".")).with_suffix(".py")
            if not module_path.is_file():
                logger.info("Extension en attente : %s", extension)
                continue
            try:
                await self.load_extension(extension)
                logger.info("Extension chargée : %s", extension)
            except Exception:
                logger.exception("Échec du chargement de l'extension %s", extension)

        if self.guild_object:
            # Les commandes définies dans les cogs sont globales par défaut.
            # On les copie dans le serveur cible avant la synchronisation locale.
            self.tree.copy_global_to(guild=self.guild_object)
            synced = await self.tree.sync(guild=self.guild_object)
            logger.info("%d commande(s) slash synchronisée(s) sur HORIZONS.", len(synced))
        else:
            logger.warning("GUILD_ID absent : aucune synchronisation slash effectuée.")

    async def on_ready(self) -> None:
        await ensure_horizons_logo_asset(self)
        if self.user:
            logger.info("Connecté en tant que %s (ID : %s)", self.user, self.user.id)
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les horizons se rencontrer"))
        guild = self.get_guild(GUILD_ID) if GUILD_ID else None
        if GUILD_ID and guild is None:
            logger.warning("Le bot n'a pas accès au serveur configuré (GUILD_ID=%s).", GUILD_ID)
        elif guild:
            logger.info("Serveur actif : %s (%s membres connus)", guild.name, guild.member_count)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        if GUILD_ID and guild.id != GUILD_ID:
            logger.warning("Le bot a rejoint un serveur non configuré : %s (%s).", guild.name, guild.id)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(error, app_commands.MissingPermissions):
            message = "Tu ne disposes pas des permissions Discord nécessaires pour cette commande."
        elif isinstance(error, app_commands.CheckFailure):
            message = "Tu n'es pas autorisé à utiliser cette commande."
        else:
            message = "Une erreur est survenue pendant l'exécution de cette commande. L'équipe HORIZONS en a été informée."
        logger.error(
            "Erreur commande slash %s : %s",
            getattr(interaction.command, "qualified_name", "inconnue"),
            original,
            exc_info=(type(original), original, original.__traceback__),
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Impossible d'envoyer le message d'erreur à l'utilisateur.")


async def main() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN est absent. Ajoute le nouveau token dans le fichier .env local, "
            "sans le partager dans une conversation ou dans Git."
        )

    async with HorizonsBot() as bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt demandé : fermeture de HORIZONS.")

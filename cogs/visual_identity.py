"""HORIZONS Ciel Royal: changements idempotents, limités à une liste d'IDs.

Ne publie aucun message et ne crée aucun salon ou rôle. Les éléments graphiques
sont optionnels et désactivés par défaut pour protéger les personnalisations.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
import discord
from discord.ext import commands
from config import BASE_DIR, GUILD_ID

log = logging.getLogger(__name__)
CONFIG_PATH = BASE_DIR / "visual_identity.json"


def load_config():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("La configuration visuelle doit être un objet JSON")
    for key in ("category_names", "channel_names", "role_colors", "emoji_files", "role_icon_files"):
        if not isinstance(cfg.get(key, {}), dict):
            raise ValueError(f"{key} doit être un objet")
    for section in ("category_names", "channel_names"):
        for key, name in cfg.get(section, {}).items():
            if not str(key).isdigit() or not isinstance(name, str) or not (1 <= len(name) <= 100):
                raise ValueError(f"Nom invalide dans {section}: {key}")
    for key, value in cfg.get("role_colors", {}).items():
        if not str(key).isdigit() or not isinstance(value, str) or len(value) != 7 or value[0] != "#":
            raise ValueError(f"Couleur invalide pour {key}")
        int(value[1:], 16)
    return cfg


def safe_file(filename: str) -> bytes:
    """N'accepte que des fichiers graphiques locaux dans assets/ciel_royal."""
    if not filename or Path(filename).name != filename:
        raise ValueError("Nom de fichier non autorisé")
    path = BASE_DIR / "assets" / "ciel_royal" / filename
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        raise ValueError("Extension d'image non autorisée")
    data = path.read_bytes()
    if len(data) > 256000:
        raise ValueError("Image trop volumineuse (maximum 250 Ko)")
    return data


class VisualIdentity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.applied = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.applied:
            return
        guild = self.bot.get_guild(GUILD_ID)
        if guild is None:
            return
        try:
            cfg = load_config()
        except (OSError, ValueError, json.JSONDecodeError):
            log.exception("Configuration Ciel Royal invalide : aucune modification")
            return
        if not cfg.get("enabled", False):
            self.applied = True
            return
        me = guild.me
        if me is None:
            return
        dry = bool(cfg.get("dry_run", False))
        changes = 0
        for section, enabled, expected_type in (
            ("category_names", "manage_category_names", discord.CategoryChannel),
            ("channel_names", "manage_channel_names", (discord.TextChannel, discord.ForumChannel, discord.VoiceChannel, discord.StageChannel)),
        ):
            if not cfg.get(enabled, False):
                continue
            for raw_id, desired in cfg.get(section, {}).items():
                channel = guild.get_channel(int(raw_id))
                if not isinstance(channel, expected_type):
                    log.warning("Ciel Royal : élément %s introuvable ou type incorrect", raw_id)
                    continue
                if channel.name == desired:
                    continue
                changes += 1
                log.info("Ciel Royal %s : %s -> %s%s", section, channel.name, desired, " (aperçu)" if dry else "")
                if dry:
                    continue
                if not me.guild_permissions.manage_channels:
                    log.warning("Permission Gérer les salons absente")
                    continue
                try:
                    await channel.edit(name=desired, reason="HORIZONS Ciel Royal : harmonie visuelle")
                except (discord.Forbidden, discord.HTTPException):
                    log.exception("Impossible de renommer %s", raw_id)
        if cfg.get("manage_role_colors", False):
            for raw_id, color in cfg.get("role_colors", {}).items():
                role = guild.get_role(int(raw_id))
                if role is None or role.is_default() or role.managed or role >= me.top_role:
                    log.warning("Ciel Royal : rôle absent ou non modifiable : %s", raw_id)
                    continue
                desired = discord.Colour(int(color[1:], 16))
                if role.colour == desired:
                    continue
                changes += 1
                log.info("Ciel Royal rôle %s : %s -> %s%s", role.name, role.colour, color, " (aperçu)" if dry else "")
                if dry:
                    continue
                if not me.guild_permissions.manage_roles:
                    log.warning("Permission Gérer les rôles absente")
                    continue
                try:
                    await role.edit(colour=desired, reason="HORIZONS Ciel Royal : palette")
                except (discord.Forbidden, discord.HTTPException):
                    log.exception("Impossible de recolorer %s", raw_id)
        # La personnalisation de marque est volontairement optionnelle.
        # Elle n'est jamais activée sans fichiers validés et configuration explicite.
        if cfg.get("manage_guild_branding", False):
            log.warning("Personnalisation icône/bannière : activation différée, aucune modification automatique")
        if cfg.get("manage_emojis", False) or cfg.get("manage_role_icons", False):
            log.warning("Émojis/icônes de rôles : activation différée, aucune modification automatique")
        self.applied = True
        log.info("Ciel Royal : %s changement(s) détecté(s), aperçu=%s", changes, dry)


async def setup(bot: commands.Bot):
    await bot.add_cog(VisualIdentity(bot))

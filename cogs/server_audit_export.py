"""Export privé de la structure et des permissions du serveur HORIZONS."""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


def permission_names(permissions: discord.Permissions) -> list[str]:
    """Retourne les permissions activées sous forme de noms lisibles."""
    return [name for name, enabled in permissions if enabled]


def overwrite_data(overwrite: discord.PermissionOverwrite) -> dict:
    allow, deny = overwrite.pair()
    return {
        "allow": permission_names(allow),
        "deny": permission_names(deny),
        "allow_value": allow.value,
        "deny_value": deny.value,
    }


def target_type(target: object) -> str:
    return "role" if isinstance(target, discord.Role) else "member"


class ServerAuditExport(commands.Cog):
    """Génère un inventaire JSON sans lire les messages ni la base de données."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="export_structure",
        description="Exporter en privé les salons, rôles et permissions du serveur.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def export_structure(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée depuis le serveur HORIZONS.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        inaccessible: list[dict] = []

        # Le cache peut ne pas être complet immédiatement après un démarrage.
        try:
            channels = await guild.fetch_channels()
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.exception("Impossible de récupérer la liste complète des salons pour %s", guild.id)
            channels = list(guild.channels)
            inaccessible.append({
                "scope": "guild_channels",
                "reason": f"fetch_channels indisponible : {type(exc).__name__}",
            })

        roles = sorted(guild.roles, key=lambda role: role.position, reverse=True)
        role_rows = []
        for role in roles:
            role_rows.append({
                "id": role.id,
                "name": role.name,
                "position": role.position,
                "color": str(role.color),
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "managed": role.managed,
                "permissions_value": role.permissions.value,
                "permissions": permission_names(role.permissions),
            })

        channel_rows = []
        for channel in sorted(channels, key=lambda item: (item.position, item.id)):
            overwrites = []
            try:
                for target, overwrite in channel.overwrites.items():
                    overwrites.append({
                        "target_type": target_type(target),
                        "target_id": target.id,
                        # Le nom facilite la lecture ; l'identifiant reste la référence fiable.
                        "target_name": getattr(target, "name", None),
                        **overwrite_data(overwrite),
                    })
            except (AttributeError, discord.HTTPException) as exc:
                inaccessible.append({
                    "scope": "channel_overwrites",
                    "channel_id": channel.id,
                    "reason": type(exc).__name__,
                })

            row = {
                "id": channel.id,
                "name": channel.name,
                "type": str(channel.type),
                "position": getattr(channel, "position", None),
                "category_id": getattr(channel, "category_id", None),
                "category_name": getattr(getattr(channel, "category", None), "name", None),
                "permissions_synced": getattr(channel, "permissions_synced", None),
                "topic": getattr(channel, "topic", None),
                "nsfw": getattr(channel, "nsfw", None),
                "slowmode_delay": getattr(channel, "slowmode_delay", None),
                "overwrites": overwrites,
            }
            # Informations complémentaires pour les salons de forum et médias.
            if isinstance(channel, discord.ForumChannel):
                row["forum"] = {
                    "default_auto_archive_duration": channel.default_auto_archive_duration,
                    "default_thread_slowmode_delay": channel.default_thread_slowmode_delay,
                    "default_sort_order": str(channel.default_sort_order),
                    "default_layout": str(channel.default_layout),
                    "available_tags": [
                        {"id": tag.id, "name": tag.name, "moderated": tag.moderated}
                        for tag in channel.available_tags
                    ],
                }
            channel_rows.append(row)

        payload = {
            "export": {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "server_id": guild.id,
                "server_name": guild.name,
                "owner_id": guild.owner_id,
                "requested_by_id": interaction.user.id,
                "scope": "structure_roles_and_channel_permission_overwrites",
                "privacy": "Aucun message, historique, contenu de membre ou donnée de base SQLite n'est exporté.",
                "limitations": [
                    "L'export décrit les permissions des rôles et les exceptions par salon ; il ne calcule pas un accès effectif pour chaque membre.",
                    "Les permissions effectives dépendent aussi de la combinaison des rôles d'un membre et des exceptions qui lui sont propres.",
                    "Les salons ou détails que le bot ne peut pas consulter peuvent être absents ou signalés dans inaccessible.",
                ],
            },
            "roles": role_rows,
            "channels": channel_rows,
            "inaccessible_or_incomplete": inaccessible,
            "summary": {
                "role_count": len(role_rows),
                "channel_count": len(channel_rows),
                "category_count": sum(isinstance(c, discord.CategoryChannel) for c in channels),
                "channels_with_overwrites": sum(bool(c.overwrites) for c in channels),
                "channels_with_unsynced_permissions": sum(
                    getattr(c, "permissions_synced", None) is False for c in channels
                ),
            },
        }

        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = f"horizons_structure_{guild.id}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}Z.json"
        file = discord.File(io.BytesIO(raw), filename=filename)
        try:
            await interaction.followup.send(
                content=(
                    f"Export terminé : **{len(channel_rows)} salons**, **{len(role_rows)} rôles**. "
                    "Le fichier est visible uniquement par toi."
                ),
                file=file,
                ephemeral=True,
            )
        except discord.HTTPException:
            log.exception("Échec de l'envoi de l'export privé pour le serveur %s", guild.id)
            await interaction.followup.send(
                "L'export a été préparé, mais Discord n'a pas accepté la pièce jointe. "
                "Vérifie la limite de taille des fichiers et réessaie.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerAuditExport(bot))

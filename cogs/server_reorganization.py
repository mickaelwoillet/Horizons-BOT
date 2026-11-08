"""Réorganisation HORIZONS pilotée par le bot, avec prévisualisation et sauvegarde."""
from __future__ import annotations

import json
import logging
import unicodedata
from copy import copy
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import DATA_DIR, GUILD_ID, STAFF_ROLE_ID

log = logging.getLogger(__name__)
BACKUP_DIR = DATA_DIR / "server_reorganization_backups"
STATE_FILE = DATA_DIR / "server_reorganization_state.json"

# Catégories existantes réutilisées : aucun nouvel ID n'est nécessaire pour les espaces principaux.
CATEGORY_NAMES = {
    1566562020273168506: "👋・𝐀𝐂𝐂𝐔𝐄𝐈𝐋 & 𝐈𝐍𝐅𝐎𝐑𝐌𝐀𝐓𝐈𝐎𝐍𝐒",
    1566567464530088026: "☀️・𝐑𝐎𝐔𝐓𝐈𝐍𝐄 𝐇𝐎𝐑𝐈𝐙𝐎𝐍𝐒",
    1566566035463864542: "💬・𝐋𝐄 𝐋𝐈𝐄𝐍 & 𝐋𝐄𝐒 𝐄́𝐂𝐇𝐀𝐍𝐆𝐄𝐒",
    1566566858205700217: "🌍・𝐂𝐔𝐋𝐓𝐔𝐑𝐄𝐒 & 𝐃𝐄́𝐂𝐎𝐔𝐕𝐄𝐑𝐓𝐄𝐒",
    1566567964419825805: "❤️・𝐄𝐍𝐓𝐑𝐀𝐈𝐃𝐄 & 𝐒𝐎𝐋𝐈𝐃𝐀𝐑𝐈𝐓𝐄́",
    1567247035688554596: "🧭・𝐄𝐗𝐏𝐄́𝐑𝐈𝐄𝐍𝐂𝐄𝐒 & 𝐂𝐄𝐑𝐂𝐋𝐄𝐒",
    1566568994851524608: "🎉・𝐀𝐆𝐄𝐍𝐃𝐀 & 𝐄́𝐕𝐄́𝐍𝐄𝐌𝐄𝐍𝐓𝐒",
    1566569978495508610: "🔊・𝐄𝐒𝐏𝐀𝐂𝐄𝐒 𝐕𝐎𝐂𝐀𝐔𝐗",
    1566562044604317848: "🛡️・𝐄𝐒𝐏𝐀𝐂𝐄 𝐒𝐓𝐀𝐅𝐅",
    1567218409656156250: "🎟️・𝐒𝐔𝐏𝐏𝐎𝐑𝐓 & 𝐓𝐈𝐂𝐊𝐄𝐓𝐒",
    1566562045623799909: "⚙️・𝐉𝐎𝐔𝐑𝐍𝐀𝐔𝐗 𝐓𝐄𝐂𝐇𝐍𝐈𝐐𝐔𝐄𝐒",
    1566562033711710318: "📦・𝐀𝐑𝐂𝐇𝐈𝐕𝐄𝐒 & 𝐀𝐍𝐂𝐈𝐄𝐍𝐒 𝐒𝐀𝐋𝐎𝐍𝐒",
}

# Chaque destination conserve son ID de catégorie ; les salons déplacés gardent leurs permissions explicites.
CHANNEL_DESTINATIONS = {
    # Accueil
    1566562049222250647: 1566562020273168506,
    1566562055811633353: 1566562020273168506,
    1566562054591086702: 1566562020273168506,
    1566565826293661696: 1566562020273168506,
    1566565766634151956: 1566562020273168506,
    1566562156839837907: 1566562020273168506,
    # Le lien et les échanges
    1566566402540699678: 1566566035463864542,
    1566566452960432349: 1566566035463864542,
    1566566574641512529: 1566566035463864542,
    1567218950180311210: 1566566035463864542,
    1566566621596876810: 1566566035463864542,
    1566953048071344158: 1566566035463864542,
    1566562128461037618: 1566566035463864542,
    1567300011165880451: 1566567964419825805,
    1567300152945942659: 1566567964419825805,
    1567291911176323173: 1566566035463864542,
    1566620913254932633: 1566566035463864542,
    # Routine quotidienne
    1566849962153611354: 1566567464530088026,
    1566850089761382553: 1566567464530088026,
    1566850190017699940: 1566566858205700217,
    1566850366145036328: 1566566858205700217,
    1567290709583593503: 1566567464530088026,
    1567844795307532308: 1566567464530088026,
    1568958163875528754: 1566567464530088026,
    1566957238625632399: 1566567464530088026,
    1567195919710027796: 1566567464530088026,
    1567198113318568158: 1566567464530088026,
    # Culture : les forums existants restent en place
    1566848209555554456: 1566566858205700217,
    1566870874597101608: 1566566858205700217,
    1566848609956270262: 1566566858205700217,
    1566848728478781510: 1566566858205700217,
    # Expériences et cercles
    1567247269970059345: 1567247035688554596,
    1567247627181883483: 1567247035688554596,
    1567247726985355424: 1567247035688554596,
    1568998134162522234: 1567247035688554596,
    1568998630831169666: 1567247035688554596,
    # Agenda
    1566569087184797786: 1566568994851524608,
    1566569118159609886: 1566568994851524608,
    1566569216411177152: 1566568994851524608,
    1566562183490441326: 1566568994851524608,
    # Support / demande de ticket
    1567217890967425135: 1567218409656156250,
    # Espace staff
    1566562218487586999: 1566562044604317848,
    1566562220375146578: 1566562044604317848,
    1566562233960505356: 1566562044604317848,
    1566562221884973207: 1566562044604317848,
    1566562223298453625: 1566562044604317848,
    1566562224892285118: 1566562044604317848,
    1566562226087788699: 1566562044604317848,
    1566562228101062818: 1566562044604317848,
    1566562235793416242: 1566562044604317848,
}

# Les anciens salons thématiques gardent leurs messages, mais deviennent des archives consultables.
ARCHIVE_CHANNEL_IDS = {
    1566562118466019498,
    1566562120005459978,
    1566562121544761374,
    1566562122710786181,
    1566562124245770341,
    1566562125399457933,
    1566562126838104154,
    1566568794527240283,
}

FORUM_NAME = "🎨・𝗽𝗮𝘀𝘀𝗶𝗼𝗻𝘀-𝗲𝘁-𝗱𝗲𝗰𝗼𝘂𝘃𝗲𝗿𝘁𝗲𝘀"
FORUM_TAGS = (
    "Créations", "Style", "Cuisine", "Technologie", "Cinéma & séries",
    "Musique", "Écriture", "Jeux vidéo", "Découvertes",
)

BOLD_LOWER = str.maketrans({chr(i): chr(0x1D5EE + i - 97) for i in range(97, 123)})
BOLD_UPPER = str.maketrans({chr(i): chr(0x1D5D4 + i - 65) for i in range(65, 91)})


def style_channel_name(name: str) -> str:
    """Applique une graisse Unicode discrète aux mots des salons sans toucher aux emojis."""
    if "・" in name:
        prefix, suffix = name.split("・", 1)
        suffix = unicodedata.normalize("NFKC", suffix).lower()
        suffix = suffix.translate(BOLD_LOWER)
        return f"{prefix}・{suffix}"[:100]
    normalized = unicodedata.normalize("NFKC", name).lower()
    return normalized.translate(BOLD_LOWER)[:100]


def _serialize_overwrites(overwrites: dict) -> list[dict]:
    result = []
    for target, overwrite in overwrites.items():
        allow, deny = overwrite.pair()
        result.append({
            "target_type": "role" if isinstance(target, discord.Role) else "member",
            "target_id": target.id,
            "allow": allow.value,
            "deny": deny.value,
        })
    return result


def _backup_payload(guild: discord.Guild) -> dict:
    channels = []
    for channel in guild.channels:
        channels.append({
            "id": channel.id,
            "name": channel.name,
            "type": type(channel).__name__,
            "category_id": getattr(channel, "category_id", None),
            "position": channel.position,
            "overwrites": _serialize_overwrites(channel.overwrites),
        })
    roles = [{
        "id": role.id,
        "name": role.name,
        "position": role.position,
        "permissions": role.permissions.value,
        "managed": role.managed,
    } for role in guild.roles]
    return {
        "guild_id": guild.id,
        "created_at": datetime.now().astimezone().isoformat(),
        "channels": channels,
        "roles": roles,
        "note": "Sauvegarde avant réorganisation HORIZONS ; aucun rôle n'est modifié par cette opération.",
    }


def _write_backup(guild: discord.Guild) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / f"structure_{guild.id}_{stamp}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(_backup_payload(guild), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def _staff_role_ids(guild: discord.Guild, bot_user_id: int | None) -> set[int]:
    protected = {STAFF_ROLE_ID} if STAFF_ROLE_ID else set()
    for role in guild.roles:
        perms = role.permissions
        if perms.administrator or perms.manage_guild or perms.manage_channels or perms.manage_roles or perms.manage_messages or perms.moderate_members:
            protected.add(role.id)
    if bot_user_id:
        member = guild.get_member(bot_user_id)
        if member:
            protected.update(role.id for role in member.roles)
    return protected


def _archive_overwrites(channel: discord.abc.GuildChannel, staff_ids: set[int], bot_user_id: int | None) -> dict:
    overwrites = {target: copy(overwrite) for target, overwrite in channel.overwrites.items()}
    for target, overwrite in overwrites.items():
        if isinstance(target, discord.Role) and target.id in staff_ids:
            continue
        if isinstance(target, discord.Member) and bot_user_id and target.id == bot_user_id:
            continue
        overwrite.send_messages = False
        if hasattr(overwrite, "send_messages_in_threads"):
            overwrite.send_messages_in_threads = False
        if hasattr(overwrite, "create_public_threads"):
            overwrite.create_public_threads = False
        if hasattr(overwrite, "create_private_threads"):
            overwrite.create_private_threads = False
    return overwrites



def _deserialize_overwrites(guild: discord.Guild, entries: list[dict], bot_user_id: int | None) -> dict:
    result = {}
    for entry in entries:
        target_id = int(entry.get("target_id", 0))
        target = guild.get_role(target_id) if entry.get("target_type") == "role" else guild.get_member(target_id)
        if target is None and bot_user_id == target_id:
            target = guild.me
        if target is None:
            continue
        allow = discord.Permissions(int(entry.get("allow", 0)))
        deny = discord.Permissions(int(entry.get("deny", 0)))
        result[target] = discord.PermissionOverwrite.from_pair(allow, deny)
    return result


class ServerReorganization(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _authorized(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.guild_permissions.manage_guild or any(
            role.id == STAFF_ROLE_ID for role in interaction.user.roles
        )

    async def _guild(self, interaction: discord.Interaction) -> discord.Guild | None:
        guild = interaction.guild
        if guild is None or (GUILD_ID and guild.id != GUILD_ID):
            await interaction.response.send_message("Cette commande doit être utilisée sur le serveur HORIZONS configuré.", ephemeral=True)
            return None
        if not self._authorized(interaction):
            await interaction.response.send_message("Cette commande est réservée à l'équipe autorisée.", ephemeral=True)
            return None
        return guild

    @app_commands.command(name="audit_structure", description="Audite les salons, catégories et rôles HORIZONS sans rien modifier.")
    async def audit_structure(self, interaction: discord.Interaction) -> None:
        guild = await self._guild(interaction)
        if guild is None:
            return
        categories = sum(isinstance(c, discord.CategoryChannel) for c in guild.channels)
        channels = sum(not isinstance(c, discord.CategoryChannel) for c in guild.channels)
        privileged = [r for r in guild.roles if r.permissions.administrator or r.permissions.manage_guild or r.permissions.manage_channels or r.permissions.manage_roles or r.permissions.manage_messages or r.permissions.kick_members or r.permissions.ban_members]
        unsynced = [c for c in guild.channels if getattr(c, "category", None) and not isinstance(c, discord.CategoryChannel) and not c.permissions_synced]
        moderator = discord.utils.get(guild.roles, name="⚒️ Modérateur")
        animator = discord.utils.get(guild.roles, name="🥳 Animateur")
        managed_count = sum(role.managed for role in guild.roles)
        lines = [
            f"**Structure actuelle :** {categories} catégories, {channels} salons et {len(guild.roles)} rôles.",
            f"**Permissions particulières :** {len(unsynced)} salons avec des permissions non synchronisées.",
            f"**Rôles gérés par des intégrations :** {managed_count} (ils ne seront pas modifiés).",
            "**Rôles à examiner (aucune modification automatique) :**",
        ]
        if moderator:
            lines.append(f"• ⚒️ Modérateur — Kick : {'oui' if moderator.permissions.kick_members else 'non'} ; Ban : {'oui' if moderator.permissions.ban_members else 'non'}.")
        if animator:
            lines.append(f"• 🥳 Animateur — Gestion des événements : {'oui' if animator.permissions.manage_events or animator.permissions.create_events else 'non'} ; modération des messages : {'oui' if animator.permissions.manage_messages else 'non'}.")
        lines.extend(f"• {role.name} — position {role.position}" for role in privileged[:18])
        if len(privileged) > 18:
            lines.append(f"• … et {len(privileged) - 18} autre(s) rôle(s).")
        lines.append("Les rôles, leurs permissions et leur hiérarchie ne seront pas modifiés par la réorganisation des salons.")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="previsualiser_reorganisation", description="Prévisualise les déplacements et archives prévus pour HORIZONS.")
    async def preview_reorganization(self, interaction: discord.Interaction) -> None:
        guild = await self._guild(interaction)
        if guild is None:
            return
        channel_ids = {c.id for c in guild.channels}
        category_ids = {c.id for c in guild.categories}
        missing_categories = sorted(set(CATEGORY_NAMES) - category_ids)
        missing_channels = sorted((set(CHANNEL_DESTINATIONS) | ARCHIVE_CHANNEL_IDS) - channel_ids)
        move_count = sum(1 for cid, dest in CHANNEL_DESTINATIONS.items() if cid in channel_ids and cid not in ARCHIVE_CHANNEL_IDS and dest in category_ids)
        archive_count = sum(cid in channel_ids for cid in ARCHIVE_CHANNEL_IDS)
        forum_exists = any(isinstance(c, discord.ForumChannel) and c.name == FORUM_NAME for c in guild.channels)
        grouped_counts: dict[int, int] = {}
        for channel_id, category_id in CHANNEL_DESTINATIONS.items():
            if channel_id in channel_ids and category_id in category_ids:
                grouped_counts[category_id] = grouped_counts.get(category_id, 0) + 1
        category_labels = {1566562020273168506: "Accueil", 1566566035463864542: "Lien & échanges", 1566567464530088026: "Routine", 1566566858205700217: "Cultures", 1567247035688554596: "Expériences", 1566568994851524608: "Agenda", 1567218409656156250: "Tickets", 1566562044604317848: "Staff"}
        lines = [
            "**Prévisualisation — aucune modification effectuée**",
            f"• {len(CATEGORY_NAMES)} catégories existantes seront renommées avec une typographie dédiée.",
            f"• {move_count} salons seront déplacés en conservant leurs permissions explicites.",
            "• Répartition : " + " ; ".join(f"{category_labels.get(cid, str(cid))} : {count}" for cid, count in grouped_counts.items()) + ".",
            f"• {archive_count} anciens salons thématiques passeront en lecture seule, historique conservé.",
            f"• Forum de remplacement des passions : {'déjà présent' if forum_exists else 'à créer'}.",
            "• Les rôles, permissions de rôles, identifiants des salons existants et publications automatiques seront préservés.",
        ]
        if missing_categories:
            lines.append(f"⚠️ Catégories absentes : {', '.join(map(str, missing_categories))}")
        if missing_channels:
            lines.append(f"⚠️ Salons absents/non accessibles : {', '.join(map(str, missing_channels))}")
        lines.append("Pour appliquer après vérification : `/appliquer_reorganisation confirmation:HORIZONS`.")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="appliquer_reorganisation", description="Applique la réorganisation HORIZONS après sauvegarde et confirmation.")
    @app_commands.describe(confirmation="Saisis exactement HORIZONS pour confirmer l'opération.")
    async def apply_reorganization(self, interaction: discord.Interaction, confirmation: str) -> None:
        guild = await self._guild(interaction)
        if guild is None:
            return
        if confirmation.strip() != "HORIZONS":
            await interaction.response.send_message("Confirmation incorrecte. Rien n'a été modifié.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            backup_path = _write_backup(guild)
        except OSError:
            log.exception("Impossible de sauvegarder la structure avant réorganisation.")
            await interaction.followup.send("⚠️ Échec de la sauvegarde. Rien n'a été modifié : la sauvegarde préalable n'a pas pu être créée.", ephemeral=True)
            return

        category_map = {c.id: c for c in guild.categories}
        missing = [cid for cid in CATEGORY_NAMES if cid not in category_map]
        if missing:
            await interaction.followup.send(f"Sauvegarde créée (`{backup_path.name}`), mais opération annulée : catégories manquantes {missing}.", ephemeral=True)
            return

        done_moves = 0
        archived = 0
        renamed = 0
        try:
            # Renommer les catégories existantes sans toucher à leurs permissions.
            for category_id, new_name in CATEGORY_NAMES.items():
                category = category_map[category_id]
                if category.name != new_name:
                    await category.edit(name=new_name, reason="Réorganisation HORIZONS validée par l'équipe")
                    renamed += 1

            culture_category = category_map[1566566858205700217]
            forum = next((c for c in guild.channels if isinstance(c, discord.ForumChannel) and c.name == FORUM_NAME), None)
            if forum is None:
                forum = await guild.create_forum(
                    name=FORUM_NAME,
                    topic="Un espace commun pour partager vos créations, passions et découvertes. Choisissez le tag qui correspond à votre publication.",
                    category=culture_category,
                    overwrites=culture_category.overwrites,
                    available_tags=[discord.ForumTag(name=tag) for tag in FORUM_TAGS],
                    reason="Création du nouvel espace commun des passions HORIZONS",
                )

            # Déplacer les salons en conservant leurs overwrites existants, y compris les non synchronisés.
            for channel_id, category_id in CHANNEL_DESTINATIONS.items():
                channel = guild.get_channel(channel_id)
                destination = category_map.get(category_id)
                if channel is None or destination is None or channel_id in ARCHIVE_CHANNEL_IDS:
                    continue
                if getattr(channel, "category_id", None) != destination.id:
                    await channel.edit(
                        category=destination,
                        overwrites=dict(channel.overwrites),
                        reason="Réorganisation HORIZONS — permissions explicites conservées",
                    )
                    done_moves += 1

            # Les anciens salons de passions deviennent des archives en lecture seule.
            archive_category = category_map[1566562033711710318]
            staff_ids = _staff_role_ids(guild, self.bot.user.id if self.bot.user else None)
            for channel_id in ARCHIVE_CHANNEL_IDS:
                channel = guild.get_channel(channel_id)
                if channel is None:
                    continue
                await channel.edit(
                    category=archive_category,
                    overwrites=_archive_overwrites(channel, staff_ids, self.bot.user.id if self.bot.user else None),
                    reason="Archivage HORIZONS — historique conservé, lecture seule",
                )
                archived += 1

            # Typographie différenciée : catégories en capitales grasses, salons en minuscules grasses.
            for channel in list(guild.channels):
                if isinstance(channel, discord.CategoryChannel):
                    continue
                styled = style_channel_name(channel.name)
                if styled != channel.name:
                    await channel.edit(name=styled, reason="Harmonisation typographique HORIZONS")

            state = {
                "last_backup": str(backup_path.name),
                "forum_id": forum.id,
                "applied_at": datetime.now().astimezone().isoformat(),
                "moved_channels": done_moves,
                "archived_channels": archived,
                "renamed_categories": renamed,
            }
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temp = STATE_FILE.with_suffix(".tmp")
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(STATE_FILE)
            await interaction.followup.send(
                "**Réorganisation appliquée.**\n"
                f"• Catégories renommées : {renamed}\n"
                f"• Salons déplacés : {done_moves}\n"
                f"• Salons archivés en lecture seule : {archived}\n"
                f"• Forum passions : {forum.mention}\n"
                f"• Sauvegarde préalable : `{backup_path.name}`\n\n"
                "Les rôles et leurs permissions n'ont pas été modifiés. Les catégories devenues vides ne sont pas supprimées : elles restent à vérifier manuellement.",
                ephemeral=True,
            )
        except Exception:
            log.exception("Réorganisation HORIZONS interrompue. Sauvegarde disponible : %s", backup_path)
            await interaction.followup.send(
                f"⚠️ L'opération a été interrompue après une erreur. Une sauvegarde complète existe : `{backup_path.name}`. "
                "Une partie des déplacements peut déjà avoir été effectuée ; vérifie le serveur avant de relancer la commande.",
                ephemeral=True,
            )


    @app_commands.command(name="restaurer_structure", description="Restaure noms, catégories et permissions depuis une sauvegarde HORIZONS.")
    @app_commands.describe(nom_sauvegarde="Nom exact du fichier JSON de sauvegarde, sans chemin.", confirmation="Saisis exactement RESTAURER pour confirmer.")
    async def restore_structure(self, interaction: discord.Interaction, nom_sauvegarde: str, confirmation: str) -> None:
        guild = await self._guild(interaction)
        if guild is None:
            return
        if confirmation.strip() != "RESTAURER":
            await interaction.response.send_message("Confirmation incorrecte. Rien n'a été modifié.", ephemeral=True)
            return
        safe_name = Path(nom_sauvegarde).name
        if safe_name != nom_sauvegarde or not safe_name.endswith(".json"):
            await interaction.response.send_message("Indique uniquement le nom d'un fichier JSON de sauvegarde.", ephemeral=True)
            return
        backup_path = BACKUP_DIR / safe_name
        if not backup_path.is_file():
            await interaction.response.send_message("Sauvegarde introuvable dans le dossier des sauvegardes HORIZONS.", ephemeral=True)
            return
        try:
            payload = json.loads(backup_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            await interaction.response.send_message("La sauvegarde est illisible. Aucune modification effectuée.", ephemeral=True)
            return
        if payload.get("guild_id") != guild.id:
            await interaction.response.send_message("Cette sauvegarde ne correspond pas à ce serveur.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        restored = 0
        skipped = 0
        # Restaurer d'abord les catégories, puis les salons et leurs permissions.
        for item in payload.get("channels", []):
            if item.get("type") != "CategoryChannel":
                continue
            category = guild.get_channel(int(item["id"]))
            if not isinstance(category, discord.CategoryChannel):
                skipped += 1
                continue
            try:
                overwrites = _deserialize_overwrites(guild, item.get("overwrites", []), self.bot.user.id if self.bot.user else None)
                await category.edit(name=item["name"], overwrites=overwrites, position=item.get("position"), reason="Restauration d'une sauvegarde HORIZONS")
                restored += 1
            except (discord.Forbidden, discord.HTTPException, KeyError, ValueError):
                log.exception("Échec de restauration de la catégorie %s", item.get("id"))
                skipped += 1
        for item in payload.get("channels", []):
            if item.get("type") == "CategoryChannel":
                continue
            channel = guild.get_channel(int(item["id"]))
            if channel is None:
                skipped += 1
                continue
            category = guild.get_channel(item.get("category_id")) if item.get("category_id") else None
            try:
                overwrites = _deserialize_overwrites(guild, item.get("overwrites", []), self.bot.user.id if self.bot.user else None)
                await channel.edit(
                    name=item["name"],
                    category=category if isinstance(category, discord.CategoryChannel) else None,
                    overwrites=overwrites,
                    position=item.get("position"),
                    reason="Restauration d'une sauvegarde HORIZONS",
                )
                restored += 1
            except (discord.Forbidden, discord.HTTPException, KeyError, ValueError):
                log.exception("Échec de restauration du salon %s", item.get("id"))
                skipped += 1
        await interaction.followup.send(
            f"Restauration terminée : {restored} élément(s) restauré(s), {skipped} ignoré(s). "
            "Les nouveaux salons créés depuis la sauvegarde ne sont pas supprimés automatiquement, afin de ne pas effacer d'éventuelles nouvelles publications.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ServerReorganization(bot))

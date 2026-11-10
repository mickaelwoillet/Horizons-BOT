"""Identité NOX via webhook Discord. Ne stocke aucun jeton de webhook."""
from __future__ import annotations
import logging
import discord

log = logging.getLogger(__name__)
WEBHOOK_NAME = "NOX"

async def send_as_nox(channel: discord.TextChannel, *, content: str | None = None,
                      embed: discord.Embed | None = None, avatar_url: str | None = None,
                      view: discord.ui.View | None = None,
                      file: discord.File | None = None,
                      allowed_mentions: discord.AllowedMentions | None = None):
    """Publie avec le nom et l'avatar NOX. Permissions Manage Webhooks requises."""
    guild = channel.guild
    me = guild.me
    if me is None or not channel.permissions_for(me).manage_webhooks:
        raise discord.Forbidden(discord.Object(id=channel.id), "Permission Gérer les webhooks manquante")
    hooks = await channel.webhooks()
    hook = next((h for h in hooks if h.name == WEBHOOK_NAME and h.user and h.user.id == guild.me.id), None)
    if hook is None:
        hook = await channel.create_webhook(name=WEBHOOK_NAME, reason="Identité de la mascotte HORIZONS")
    from config import DATA_DIR
    from pathlib import Path
    # Avatar public configurable, sans second bot et sans stockage de jeton webhook.
    avatar_file = DATA_DIR / "nox" / "avatar_url.txt"
    configured = avatar_file.read_text(encoding="utf-8").strip() if avatar_file.is_file() else ""
    avatar = avatar_url or (configured if configured.startswith("https://") else None) or (guild.me.display_avatar.url if guild.me else None)
    return await hook.send(content=content, embed=embed, username=WEBHOOK_NAME,
                           avatar_url=avatar, wait=True, view=view, file=file,
                           allowed_mentions=allowed_mentions or discord.AllowedMentions.none())

"""Identité NOX via webhook Discord. Ne stocke aucun jeton de webhook."""
from __future__ import annotations
import logging
from pathlib import Path
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
    # The avatar is stored ON the NOX webhook, not on the Horizons bot.
    # No public image URL or extra bot account is required.
    portrait = Path(DATA_DIR) / 'nox_tv' / 'nox_avatar.webp'
    if portrait.is_file() and not getattr(hook, 'avatar', None):
        try:
            await hook.edit(avatar=portrait.read_bytes(), reason='Avatar officiel de NOX')
        except discord.HTTPException:
            log.warning('Avatar du webhook NOX non actualisé dans %s', channel.id)
    avatar = avatar_url  # None keeps the webhook's own uploaded avatar.
    # discord.py 2.5+ refuse explicitement view=None / file=None.
    kwargs = dict(content=content, embed=embed, username=WEBHOOK_NAME, wait=True,
                  allowed_mentions=allowed_mentions or discord.AllowedMentions.none())
    if avatar is not None:
        kwargs['avatar_url'] = avatar
    if view is not None:
        kwargs['view'] = view
    if file is not None:
        kwargs['file'] = file
    return await hook.send(**kwargs)

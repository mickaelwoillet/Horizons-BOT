"""Journalisation non bloquante des étapes de l'Escape Game HORIZONS."""
import logging
import os
import unicodedata
import discord

log = logging.getLogger(__name__)


def _normalise(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.lower()) if not unicodedata.combining(c)).replace('-', '').replace('_', '').replace(' ', '').replace('・', '')


def _channel(guild):
    raw = os.getenv('ESCAPE_EVENTS_LOG_CHANNEL_ID', '').strip()
    if raw.isdecimal():
        channel = guild.get_channel(int(raw))
        if isinstance(channel, discord.TextChannel):
            return channel
    for channel in guild.text_channels:
        if _normalise(channel.name) in ('logsevenements', 'logsevenement'):
            return channel
    return None


async def log_escape_event(interaction, kind, *, room_number=None, room_name=None, mode='solo'):
    """Send a staff log. A missing channel/permission never interrupts a game."""
    guild = interaction.guild
    if guild is None:
        return
    channel = _channel(guild)
    if channel is None:
        log.warning('Escape Game: salon Logs événements introuvable sur %s', guild.id)
        return
    who = interaction.user.mention
    title = '**🌌 Les Fractures du Cosmos**'
    suffix = ' (en équipe)' if mode == 'team' else ' (en solo)'
    if kind == 'start':
        message = f'🚀 {who} a commencé l’Escape Game {title}{suffix}.'
    elif kind == 'room':
        message = f'🧩 {who} a atteint la **salle {room_number}** — **{room_name}** dans {title}{suffix}.'
    elif kind == 'finish':
        message = f'🏆 {who} a terminé avec succès l’Escape Game {title}{suffix} ! 🎉'
    else:
        return
    try:
        await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning('Escape Game: impossible d’envoyer le log dans %s : %s', channel.id, exc)

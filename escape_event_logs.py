"""Journaux des événements de l'Escape Game HORIZONS, sans interrompre le jeu."""
import logging
import os
import unicodedata

import discord
from config import LOG_CHANNEL_ID

log = logging.getLogger(__name__)


def _normalise(name):
    return ''.join(c for c in unicodedata.normalize('NFKD', name.lower())
                   if not unicodedata.combining(c)).replace('-', '').replace('_', '').replace(' ', '').replace('・', '')


def _channel(guild):
    """Salon dédié configuré > salon dédié nommé > journal général configuré."""
    raw = os.getenv('ESCAPE_EVENTS_LOG_CHANNEL_ID', '').strip()
    if raw:
        if not raw.isdecimal():
            log.warning('ESCAPE_EVENTS_LOG_CHANNEL_ID invalide : %r', raw)
        else:
            channel = guild.get_channel(int(raw))
            if isinstance(channel, discord.TextChannel):
                return channel
            log.warning('Salon Escape configuré (%s) introuvable ou non textuel sur %s', raw, guild.id)
    for channel in guild.text_channels:
        if _normalise(channel.name) in ('logsevenements', 'logsevenement', 'logsescapegame', 'logescapegame'):
            return channel
    channel = guild.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
    if isinstance(channel, discord.TextChannel):
        return channel
    return None


async def log_escape_event(interaction, kind, *, room_number=None, room_name=None, mode='solo'):
    """Journaliser démarrage, changement de salle et victoire sans ping ni blocage."""
    guild = interaction.guild
    if guild is None:
        return
    try:
        channel = _channel(guild)
        if channel is None:
            log.warning('Escape Game : aucun salon de logs utilisable sur %s. '
                        'Configurer ESCAPE_EVENTS_LOG_CHANNEL_ID ou LOG_CHANNEL_ID.', guild.id)
            return
        member = interaction.user
        who = f'{discord.utils.escape_markdown(str(member))} (`{member.id}`)'
        title = '**🌌 Les Fractures du Cosmos**'
        suffix = ' (en équipe)' if mode == 'team' else ' (en solo)'
        if kind == 'start':
            message = f'🚀 {who} a commencé l’Escape Game {title}{suffix}.'
        elif kind == 'room':
            safe_name = discord.utils.escape_markdown(str(room_name or 'Salle inconnue'))
            message = f'🧩 {who} a atteint la **salle {room_number}** — **{safe_name}** dans {title}{suffix}.'
        elif kind == 'finish':
            message = f'🏆 {who} a terminé avec succès l’Escape Game {title}{suffix} ! 🎉'
        else:
            return
        await channel.send(message, allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning('Escape Game : envoi du journal impossible : %s', exc)
    except Exception:
        log.exception('Escape Game : erreur inattendue de journalisation')

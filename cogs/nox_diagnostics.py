"""Read-only, administrator-only NOX preflight for staging deployments.

No Discord messages are posted, no webhook is created and no reservations are altered.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from .nox_refuge import DB
from . import nox_refuge_engine as engine
from .nox_daily_12 import initialize, SLOTS, ILLUSTRATED_SLOTS, IMAGE_CATALOG, IMAGE_DIR
from .nox_daily_polls import initialize as init_polls
from .nox_daily_challenges import init_db as init_challenges
import json

PARIS = ZoneInfo('Europe/Paris')


def inspect_database(con, guild_id, day):
    """Inspect scheduled delivery state without changing any existing reservations."""
    initialize(con)
    init_polls(con)
    init_challenges(con)
    config = con.execute('SELECT channel_id,enabled FROM nox_daily_config WHERE guild_id=?', (guild_id,)).fetchone()
    rows = con.execute('SELECT slot,state FROM nox_daily_posts WHERE guild_id=? AND local_day=? ORDER BY slot', (guild_id, day)).fetchall()
    sent = sum(row['state'] == 'sent' for row in rows)
    pending = [row['slot'] for row in rows if row['state'] != 'sent']
    polls = con.execute('SELECT slot,message_id FROM nox_daily_polls WHERE guild_id=? AND local_day=?', (guild_id, day)).fetchall()
    challenges = con.execute('SELECT slot,message_id FROM nox_daily_challenges WHERE guild_id=? AND local_day=?', (guild_id, day)).fetchall()
    return {'channel_id': config['channel_id'] if config else None,
            'enabled': bool(config['enabled']) if config else False,
            'sent': sent, 'pending': pending,
            'polls_unlinked': [r['slot'] for r in polls if not r['message_id']],
            'challenges_unlinked': [r['slot'] for r in challenges if not r['message_id']]}


def inspect_images():
    try:
        catalog = json.loads(IMAGE_CATALOG.read_text(encoding='utf-8'))
        valid = {entry['id'] for entry in catalog if isinstance(entry, dict)
                 and isinstance(entry.get('id'), str)
                 and isinstance(entry.get('image'), str)
                 and (IMAGE_DIR / Path(entry['image']).name).is_file()}
        return len(valid), len(catalog)
    except (OSError, ValueError, KeyError, TypeError):
        return 0, 0


class NoxDiagnostics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def noxdiagnostic(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message('Commande réservée à un serveur.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        day = datetime.now(PARIS).date().isoformat()
        try:
            with engine.connect(DB) as con:
                report = inspect_database(con, interaction.guild.id, day)
        except Exception:
            await interaction.followup.send('❌ Impossible de lire la base NOX. Consulter les journaux du bot.', ephemeral=True)
            return
        image_count, image_total = inspect_images()
        channel = self.bot.get_channel(report['channel_id']) if report['channel_id'] else None
        if channel is None and report['channel_id']:
            try:
                channel = await self.bot.fetch_channel(report['channel_id'])
            except (discord.HTTPException, discord.Forbidden):
                pass
        checks = []
        checks.append('🟢 Programmateur activé' if report['enabled'] else '⚪ Programmateur désactivé')
        if isinstance(channel, discord.TextChannel) and interaction.guild.me:
            perms = channel.permissions_for(interaction.guild.me)
            for name, ok in [('Voir le salon', perms.view_channel), ('Écrire', perms.send_messages),
                             ('Gérer les webhooks', perms.manage_webhooks), ('Joindre des fichiers', perms.attach_files)]:
                checks.append(('🟢 ' if ok else '🔴 ') + name)
        else:
            checks.append('🔴 Salon de publication introuvable ou non configuré')
        checks.append(f'🖼️ Illustrations disponibles : {image_count}/{image_total} (6 créneaux illustrés)')
        checks.append(f'📬 Publications du jour : {report["sent"]}/{len(SLOTS)} envoyées')
        if report['pending']:
            checks.append('🟠 Réservations non confirmées : ' + ', '.join(str(x + 1) for x in report['pending']))
        if report['polls_unlinked'] or report['challenges_unlinked']:
            checks.append('🟠 Interactions sans identifiant de message : vérifier les envois')
        checks.append('🔁 Boutons persistants : vérifier le démarrage des extensions dans les logs')
        checks.append('ℹ️ Test en lecture seule : aucun webhook créé, aucun message envoyé')
        await interaction.followup.send('**🐾 Diagnostic NOX — ' + day + '**\n' + '\n'.join(checks), ephemeral=True)


async def setup(bot):
    await bot.add_cog(NoxDiagnostics(bot))

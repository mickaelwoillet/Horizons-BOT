"""Récompense honorifique et célébration des victoires de l'Escape Game HORIZONS."""
import logging
import sqlite3
from pathlib import Path
import discord

log = logging.getLogger(__name__)
ROLE_NAME = '🌟 Sauveur du Cosmos'
ROLE_COLOR = discord.Color(0xD4AF37)
IMAGE = Path(__file__).resolve().parent / 'escape_content' / 'images' / 'victoire_cosmos.png'


def eligible_members(interaction, database, key):
    guild_id, adventure, mode, owner_id = key
    if mode == 'solo':
        return [owner_id]
    if mode != 'team':
        return []
    try:
        with sqlite3.connect(database) as con:
            return [row[0] for row in con.execute(
                'SELECT m.user_id FROM team_members m JOIN teams t ON t.id=m.team_id '
                'WHERE t.guild_id=? AND t.adventure=? AND t.id=?',
                (guild_id, adventure, owner_id))]
    except sqlite3.Error as exc:
        log.error('Escape Game: participants de l’équipe introuvables : %s', exc)
        return []


async def award_role(interaction, database, key):
    guild = interaction.guild
    if guild is None:
        return [], []
    participants = list(dict.fromkeys(eligible_members(interaction, database, key)))
    role = discord.utils.get(guild.roles, name=ROLE_NAME)
    if role is None:
        try:
            role = await guild.create_role(name=ROLE_NAME, color=ROLE_COLOR,
                                           permissions=discord.Permissions.none(),
                                           reason='Récompense Escape Game HORIZONS')
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning('Escape Game: création du rôle impossible : %s', exc)
            return [], participants
    awarded, failed = [], []
    for user_id in participants:
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
            if role not in member.roles:
                await member.add_roles(role, reason='Victoire aux Fractures du Cosmos')
            awarded.append(user_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
            failed.append(user_id)
            log.warning('Escape Game: rôle non attribué à %s : %s', user_id, exc)
    return awarded, failed


async def celebrate(interaction, database, key, secret=False):
    awarded, failed = await award_role(interaction, database, key)
    heading = '🎉 FÉLICITATIONS ! 🎉'
    description = ('🌌 **Tu as découvert l’Origine cachée et restauré l’équilibre du Cosmos !**\n'
                   'Les fractures se referment et les étoiles retrouvent leur éclat.' if secret else
                   '🌌 **Tu as triomphé du Tribunal des Éternités !**\n'
                   'Les fractures sont contenues et l’équilibre du Cosmos est préservé.')
    description += '\n\n🏅 **Distinction : 🌟 Sauveur du Cosmos**'
    if key[2] == 'team':
        description += '\n👥 **Victoire collective :** les membres de l’équipe reçoivent la distinction.'
    if failed:
        description += '\n⚠️ Attribution du rôle impossible pour certains participants : le staff doit vérifier les permissions et la hiérarchie du bot.'
    embed = discord.Embed(title=heading, description=description, color=ROLE_COLOR)
    embed.set_footer(text='HORIZONS • Les Fractures du Cosmos')
    file = None
    if IMAGE.is_file():
        file = discord.File(IMAGE, filename='victoire_cosmos.png')
        embed.set_image(url='attachment://victoire_cosmos.png')
    try:
        await interaction.followup.send(embed=embed, file=file, ephemeral=True,
                                        allowed_mentions=discord.AllowedMentions.none())
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning('Escape Game: écran de victoire impossible : %s', exc)

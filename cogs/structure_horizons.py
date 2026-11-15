"""Renommage contrôlé des salons HORIZONS et nettoyage optionnel.

Aucune suppression ni modification n'est effectuée au démarrage.
Les IDs proviennent de l'export serveur du 15 novembre 2026.
"""
from __future__ import annotations

import logging
import os
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)
FOUNDER_ROLE_ID = int(os.getenv('FOUNDER_ROLE_ID', '1566561887305339001'))

# Les noms sont explicites et validés ; ne pas toucher aux autres salons.
RENAMES = {
    1566566402540699678: '🌌・𝓛𝓐 𝓟𝓛𝓐𝓒𝓔・💬',
    1569434256311193721: '🌟・𝓭𝓲𝓼𝓽𝓲𝓷𝓬𝓽𝓲𝓸𝓷𝓼-𝓭𝓮-𝓷𝓸𝔁',
    1566562044604317848: '🛡️ ┃ 𝐄𝐒𝐏𝐀𝐂𝐄 𝐒𝐓𝐀𝐅𝐅',
    1566562045623799909: '⚙️ ┃ 𝐉𝐎𝐔𝐑𝐍𝐀𝐔𝐗 & 𝐋𝐎𝐆𝐒',
    1569434248652521605: '🌌 ┃ 𝐂𝐇𝐀𝐎𝐒 𝐂𝐎𝐒𝐌𝐈𝐐𝐔𝐄',
    1571534451144392744: '📜・𝘳è𝘨𝘭𝘦𝘮𝘦𝘯𝘵-𝘴𝘵𝘢𝘧𝘧',
    1566562220375146578: '💬・𝘥𝘪𝘴𝘤𝘶𝘴𝘴𝘪𝘰𝘯-𝘴𝘵𝘢𝘧𝘧',
    1566562226087788699: '📋・𝘰𝘳𝘨𝘢𝘯𝘪𝘴𝘢𝘵𝘪𝘰𝘯',
    1566562245574656140: '📋・𝗹𝗼𝗴𝘀-𝗴𝗲𝗻𝗲𝗿𝗮𝗹',
    1568965253817962506: '🎟️・𝗹𝗼𝗴𝘀-𝘁𝗶𝗰𝗸𝗲𝘁𝘀',
    1571537581596876941: '👑・𝗹𝗼𝗴𝘀-𝗳𝗼𝗻𝗱𝗮𝘁𝗲𝘂𝗿',
}
CLEANUP = {
    1569393198126731434: 'Le Regard du Jour',
    1569393200463085598: 'Archives du Regard',
    1567290709583593503: 'Météo des émotions',
}
PLACE_ID = 1566566402540699678
PLACE_TOPIC = '🌟 Le cœur de HORIZONS — discussion générale : viens échanger, partager et faire connaissance avec la communauté.'


def is_founder(interaction: discord.Interaction) -> bool:
    member = interaction.user
    return bool(interaction.guild and isinstance(member, discord.Member) and (
        interaction.guild.owner_id == member.id or any(r.id == FOUNDER_ROLE_ID for r in member.roles)
    ))


class ConfirmStructure(discord.ui.View):
    def __init__(self, cog: 'StructureHorizons', actor_id: int, operation: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.actor_id = actor_id
        self.operation = operation

    @discord.ui.button(label='Confirmer', emoji='✅', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.actor_id or not is_founder(interaction):
            return await interaction.response.send_message('Seul le Fondateur ayant demandé cette action peut la confirmer.', ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)
        successes, failures = [], []
        if self.operation == 'apply':
            for cid, name in RENAMES.items():
                channel = interaction.guild.get_channel(cid)
                if channel is None:
                    failures.append(f'{cid} : introuvable')
                    continue
                try:
                    changes = {}
                    if channel.name != name:
                        changes['name'] = name
                    if cid == PLACE_ID and isinstance(channel, discord.TextChannel):
                        if channel.topic != PLACE_TOPIC:
                            changes['topic'] = PLACE_TOPIC
                    if changes:
                        await channel.edit(reason=f'Harmonisation HORIZONS demandée par {interaction.user}', **changes)
                        successes.append(str(cid))
                except (discord.Forbidden, discord.HTTPException) as exc:
                    failures.append(f'{cid} : {type(exc).__name__}')
            place = interaction.guild.get_channel(PLACE_ID)
            if isinstance(place, discord.TextChannel) and place.category:
                try:
                    if place.position != 0:
                        await place.edit(position=0, reason='Mise en avant du salon général HORIZONS')
                except (discord.Forbidden, discord.HTTPException) as exc:
                    failures.append(f'Position La Place : {type(exc).__name__}')
        else:
            for cid, label in CLEANUP.items():
                channel = interaction.guild.get_channel(cid)
                if channel is None:
                    continue
                try:
                    await channel.delete(reason=f'Nettoyage HORIZONS confirmé par {interaction.user} : {label}')
                    successes.append(label)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    failures.append(f'{label} : {type(exc).__name__}')
        log.warning('Structure HORIZONS %s par %s : réussites=%s échecs=%s', self.operation, interaction.user.id, successes, failures)
        result = f'Action terminée. Modifications : {len(successes)}. Erreurs : {len(failures)}.'
        if failures:
            result += '\n' + '\n'.join(f'• {x}' for x in failures)[:1200]
        await interaction.followup.send(result, ephemeral=True)

    @discord.ui.button(label='Annuler', emoji='✖️', style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.actor_id:
            return await interaction.response.send_message('Ce panneau ne vous appartient pas.', ephemeral=True)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content='Action annulée. Aucun changement effectué.', view=self)


class StructureHorizons(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='structure', description='Prévisualiser ou harmoniser les salons HORIZONS (Fondateur).')
    @app_commands.describe(action='Aperçu, appliquer les noms, ou supprimer les trois anciens salons')
    @app_commands.choices(action=[
        app_commands.Choice(name='Aperçu des changements', value='preview'),
        app_commands.Choice(name='Appliquer les renommages', value='apply'),
        app_commands.Choice(name='Nettoyer les anciens salons', value='cleanup'),
    ])
    @app_commands.guild_only()
    async def structure(self, interaction: discord.Interaction, action: app_commands.Choice[str]):
        if not is_founder(interaction):
            return await interaction.response.send_message('Commande réservée au Fondateur.', ephemeral=True)
        if action.value == 'preview':
            lines = []
            for cid, name in RENAMES.items():
                channel = interaction.guild.get_channel(cid)
                if channel and channel.name != name:
                    lines.append(f'• {channel.name} → {name}')
            removed = [f'• {label} (`{cid}`)' for cid, label in CLEANUP.items() if interaction.guild.get_channel(cid)]
            message = '**Renommages proposés**\n' + ('\n'.join(lines) or 'Aucun renommage nécessaire.')
            message += '\n\n**Salons supprimables séparément**\n' + ('\n'.join(removed) or 'Aucun salon à supprimer.')
            message += '\n\nAucune permission ni catégorie ne sera modifiée. La Place sera remontée en tête de sa catégorie.'
            return await interaction.response.send_message(message[:1900], ephemeral=True)
        if action.value == 'cleanup':
            names = [f'• {name}' for cid, name in CLEANUP.items() if interaction.guild.get_channel(cid)]
            if not names:
                return await interaction.response.send_message('Aucun des trois anciens salons n’existe encore.', ephemeral=True)
            msg = '**ATTENTION : suppression définitive des salons et de leurs messages.**\n' + '\n'.join(names)
        else:
            msg = f'Confirmer les renommages de {len(RENAMES)} salons/catégories et la mise en avant de La Place ? Aucun salon ne sera supprimé.'
        await interaction.response.send_message(msg, view=ConfirmStructure(self, interaction.user.id, action.value), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(StructureHorizons(bot))

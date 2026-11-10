"""Panneau permanent et interactif des Missions et Saisons HORIZONS.

Réutilise les commandes et les tables existantes ; ne touche pas aux permissions.
"""
from __future__ import annotations
import logging
import discord
from discord import app_commands
from discord.ext import commands
from config import MISSIONS_CHANNEL_ID
from .embed_theme import horizons_embed, wait_for_logo_ready

log = logging.getLogger(__name__)
TITLE = '✦ Missions & Saisons HORIZONS'


def build_embed(bot):
    embed = horizons_embed(
        title=TITLE,
        description=(
            '**🧭 Missions HORIZONS**\n'
            'Trois petits défis renouvelés chaque semaine. Consulte ton passeport et valide '
            'une mission accomplie, à ton rythme.\n\n'
            '**🌅 Saisons HORIZONS**\n'
            'Une aventure collective de six semaines, avec trois étapes facultatives '
            'par semaine et des distinctions à découvrir.\n\n'
            '**Aucune obligation, aucun classement, aucune course aux messages.** '
            'Les validations reposent sur la confiance.'
        ),
    )
    if not embed.thumbnail.url and bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text='HORIZONS • Panneau permanent • Missions et Saisons')
    return embed


class MissionSteps(discord.ui.View):
    def __init__(self, cog_name: str, command: str, parameter: str):
        super().__init__(timeout=180)
        for n in (1, 2, 3):
            button = discord.ui.Button(label=f'Valider l’étape {n}', style=discord.ButtonStyle.secondary, emoji='🌟')
            async def callback(interaction: discord.Interaction, number=n):
                cog = interaction.client.get_cog(cog_name)
                if cog is None:
                    await interaction.response.send_message('Fonction temporairement indisponible.', ephemeral=True)
                    return
                choice = app_commands.Choice(name=f'Étape {number}', value=number)
                method = getattr(cog, command)
                if isinstance(method, app_commands.Command):
                    await method.callback(cog, interaction, **{parameter: choice})
                else:
                    await method(interaction, **{parameter: choice})
            button.callback = callback
            self.add_item(button)


class MissionHubView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Mon passeport', emoji='🧭', style=discord.ButtonStyle.primary, custom_id='horizons:missionhub:passport')
    async def passport(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog('Experiences')
        if cog:
            await cog.mon_passeport.callback(cog, interaction)
        else:
            await interaction.response.send_message('Passeport indisponible.', ephemeral=True)

    @discord.ui.button(label='Valider une mission', emoji='✅', style=discord.ButtonStyle.secondary, custom_id='horizons:missionhub:validate')
    async def validate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Choisis une mission que tu as accomplie :', view=MissionSteps('Experiences', 'valider_mission', 'numero'), ephemeral=True)

    @discord.ui.button(label='Saison en cours', emoji='🌅', style=discord.ButtonStyle.primary, custom_id='horizons:missionhub:season')
    async def season(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog('Seasons')
        if cog:
            await cog.saison.callback(cog, interaction)
        else:
            await interaction.response.send_message('Saison indisponible.', ephemeral=True)

    @discord.ui.button(label='Rejoindre la saison', emoji='🤝', style=discord.ButtonStyle.success, custom_id='horizons:missionhub:join')
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog('Seasons')
        if cog:
            await cog.rejoindre_saison(interaction)
        else:
            await interaction.response.send_message('Saison indisponible.', ephemeral=True)

    @discord.ui.button(label='Mes étapes de saison', emoji='✨', style=discord.ButtonStyle.secondary, custom_id='horizons:missionhub:steps')
    async def steps(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog('Seasons')
        if not cog:
            await interaction.response.send_message('Saison indisponible.', ephemeral=True)
            return
        # Affiche les étapes et permet de les valider sans commande slash.
        await interaction.response.send_message('Consulte tes étapes et choisis celles déjà réalisées :', view=MissionSteps('Seasons', 'valider_etape_saison', 'etape'), ephemeral=True)


class MissionHub(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ready_once = False

    async def cog_load(self):
        self.bot.add_view(MissionHubView())

    @commands.Cog.listener()
    async def on_ready(self):
        if self.ready_once or not MISSIONS_CHANNEL_ID:
            return
        await wait_for_logo_ready()
        channel = self.bot.get_channel(MISSIONS_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(MISSIONS_CHANNEL_ID)
            except discord.HTTPException:
                return
        if not isinstance(channel, discord.TextChannel):
            return
        embed = build_embed(self.bot)
        try:
            async for message in channel.history(limit=150):
                if message.author.id != self.bot.user.id:
                    continue
                if any(e.title == TITLE for e in message.embeds):
                    await message.edit(embed=embed, view=MissionHubView())
                    self.ready_once = True
                    return
            await channel.send(embed=embed, view=MissionHubView())
            self.ready_once = True
        except (discord.Forbidden, discord.HTTPException):
            # Pas de nouvelle publication si l'historique est inaccessible.
            log.exception('Panneau Missions : lecture ou mise à jour impossible')


async def setup(bot):
    await bot.add_cog(MissionHub(bot))

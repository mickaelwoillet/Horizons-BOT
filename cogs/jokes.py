"""Commandes et publication quotidienne des blagues HORIZONS."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
import logging
from datetime import time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import JOKE_DAILY_CHANNEL_ID, LOCAL_TIMEZONE
from .content_utils import categories, pick_joke

log = logging.getLogger(__name__)


def nice_category(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").capitalize()


class JokeView(discord.ui.View):
    def __init__(self, owner_id: int, category: str | None = None):
        super().__init__(timeout=180)
        self.owner_id = owner_id
        self.category = category

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette blague a été lancée par une autre personne 🙂", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Une autre !", style=discord.ButtonStyle.primary, emoji="😄")
    async def another(self, interaction: discord.Interaction, button: discord.ui.Button):
        cat, joke = pick_joke(self.category)
        embed = horizons_embed(title="😄 Une nouvelle blague !", description=joke, color=discord.Color.blurple())
        embed.set_footer(text=f"HORIZONS • {nice_category(cat)}")
        await interaction.response.edit_message(embed=embed, view=self)


class Jokes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_joke.start()

    def cog_unload(self):
        self.daily_joke.cancel()

    @app_commands.command(name="blague", description="Découvrir une blague HORIZONS.")
    @app_commands.describe(categorie="Choisir une catégorie de blagues")
    async def blague(self, interaction: discord.Interaction, categorie: str | None = None):
        cats = categories()
        if categorie and categorie not in cats:
            await interaction.response.send_message("Cette catégorie n'existe pas. Utilise `/blague` sans catégorie pour une surprise.", ephemeral=True)
            return
        cat, joke = pick_joke(categorie)
        embed = horizons_embed(title="😄 La blague du moment", description=joke, color=discord.Color.blurple())
        embed.set_footer(text=f"HORIZONS • {nice_category(cat)}")
        await interaction.response.send_message(embed=embed, view=JokeView(interaction.user.id, categorie))

    @blague.autocomplete("categorie")
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=nice_category(c), value=c) for c in categories() if current.lower() in c.lower()][:25]

    @tasks.loop(time=time(hour=12, minute=0, tzinfo=LOCAL_TIMEZONE))
    async def daily_joke(self):
        channel = self.bot.get_channel(JOKE_DAILY_CHANNEL_ID) if JOKE_DAILY_CHANNEL_ID else None
        if channel is None and JOKE_DAILY_CHANNEL_ID:
            try:
                channel = await self.bot.fetch_channel(JOKE_DAILY_CHANNEL_ID)
            except discord.HTTPException:
                log.exception("Canal quotidien des blagues introuvable.")
                return
        if channel is None:
            log.warning("JOKE_DAILY_CHANNEL_ID non configuré : publication ignorée.")
            return
        cat, joke = pick_joke()
        embed = horizons_embed(title="☀️ La blague du jour", description=joke, color=discord.Color.gold())
        embed.set_footer(text=f"HORIZONS • {nice_category(cat)}")
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            log.exception("Impossible de publier la blague quotidienne.")

    @daily_joke.before_loop
    async def before_daily_joke(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Jokes(bot))

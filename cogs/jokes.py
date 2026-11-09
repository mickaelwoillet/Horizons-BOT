"""Commandes et publication quotidienne des blagues HORIZONS."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
import logging
from datetime import time, datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import JOKE_DAILY_CHANNEL_ID, LOCAL_TIMEZONE
from .storage import db
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
        self._catchup_done = False

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

    @commands.Cog.listener()
    async def on_ready(self):
        if self._catchup_done:
            return
        self._catchup_done = True
        if datetime.now(LOCAL_TIMEZONE).time() >= time(hour=15, minute=30):
            await self.publish_daily_joke()

    @tasks.loop(time=time(hour=15, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def daily_joke(self):
        await self.publish_daily_joke()

    async def publish_daily_joke(self):
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        try:
            with db() as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS joke_daily_publications (day TEXT PRIMARY KEY, message_id TEXT, status TEXT NOT NULL)")
                existing = conn.execute("SELECT status FROM joke_daily_publications WHERE day=?", (today,)).fetchone()
                if existing:
                    return
                conn.execute("INSERT INTO joke_daily_publications(day,message_id,status) VALUES(?,NULL,'pending')", (today,))
        except Exception:
            log.exception("Impossible de réserver la blague quotidienne dans SQLite")
            return
        # Le salon officiel est vérifié dans l'export structure HORIZONS du 09/11/2026.
        # Une ancienne variable .env ne doit jamais rediriger la blague quotidienne
        # vers le salon de discussion « sourires ».
        official_joke_channel_id = 1567195919710027796
        if JOKE_DAILY_CHANNEL_ID != official_joke_channel_id:
            log.warning(
                "JOKE_DAILY_CHANNEL_ID=%s ne correspond pas au salon officiel %s ; "
                "utilisation du salon la-blague-du-jour.",
                JOKE_DAILY_CHANNEL_ID, official_joke_channel_id,
            )
        channel = self.bot.get_channel(official_joke_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(official_joke_channel_id)
            except discord.HTTPException:
                log.exception("Salon de la blague du jour inaccessible")
        if channel is None:
            log.error("Blague quotidienne non publiée : salon absent")
            with db() as conn:
                conn.execute("DELETE FROM joke_daily_publications WHERE day=? AND status='pending'", (today,))
            return
        cat, joke = pick_joke()
        embed = horizons_embed(title="☀️ La blague du jour", description=joke)
        embed.set_footer(text=f"HORIZONS • {nice_category(cat)}")
        try:
            msg = await channel.send(embed=embed)
            with db() as conn:
                conn.execute("UPDATE joke_daily_publications SET message_id=?, status='sent' WHERE day=?", (str(msg.id), today))
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Impossible de publier la blague quotidienne")
            with db() as conn:
                conn.execute("DELETE FROM joke_daily_publications WHERE day=? AND status='pending'", (today,))

    @daily_joke.before_loop
    async def before_daily_joke(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Jokes(bot))

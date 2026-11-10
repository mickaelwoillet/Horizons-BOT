"""Commandes et publication quotidienne des devinettes HORIZONS."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
import logging
from datetime import time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import RIDDLE_DAILY_CHANNEL_ID, LOCAL_TIMEZONE
from .content_utils import pick_riddle

log = logging.getLogger(__name__)


class RiddleView(discord.ui.View):
    def __init__(self, owner_id: int | None, answer: str):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.answer = answer

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette devinette appartient à une autre personne. Ouvre `/centre` → Activités pour jouer à ton tour !", ephemeral=True)
            return False
        return True

    async def reveal(self, interaction: discord.Interaction, abandoned: bool = False):
        self.clear_items()
        title = "🏳️ La solution !" if abandoned else "💡 Bien joué, voici la réponse !"
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else horizons_embed()
        embed.color = discord.Color.green()
        embed.add_field(name=title, value=self.answer, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Voir la réponse", style=discord.ButtonStyle.success, emoji="💡")
    async def show_answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction)

    @discord.ui.button(label="Abandonner", style=discord.ButtonStyle.secondary, emoji="🏳️")
    async def give_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reveal(interaction, abandoned=True)


class Riddles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_riddle.start()

    def cog_unload(self):
        self.daily_riddle.cancel()

    async def devinette(self, interaction: discord.Interaction):
        item = pick_riddle()
        if not item:
            await interaction.response.send_message("Aucune devinette n'est encore disponible.", ephemeral=True)
            return
        embed = horizons_embed(title="🧩 La devinette HORIZONS", description=item["question"], color=discord.Color.teal())
        embed.set_footer(text="HORIZONS • À toi de jouer !")
        await interaction.response.send_message(embed=embed, view=RiddleView(interaction.user.id, item["reponse"]), ephemeral=True)

    @tasks.loop(time=time(hour=17, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def daily_riddle(self):
        channel = self.bot.get_channel(RIDDLE_DAILY_CHANNEL_ID) if RIDDLE_DAILY_CHANNEL_ID else None
        if channel is None and RIDDLE_DAILY_CHANNEL_ID:
            try:
                channel = await self.bot.fetch_channel(RIDDLE_DAILY_CHANNEL_ID)
            except discord.HTTPException:
                log.exception("Canal quotidien des devinettes introuvable.")
                return
        if channel is None:
            log.warning("RIDDLE_DAILY_CHANNEL_ID non configuré : publication ignorée.")
            return
        item = pick_riddle()
        if not item:
            log.warning("Aucune devinette disponible dans data/devinettes.json.")
            return
        embed = horizons_embed(title="🧩 La devinette du jour", description=item["question"], color=discord.Color.teal())
        embed.set_footer(text="HORIZONS • Qui trouvera la réponse ?")
        # Publication quotidienne consultable par tous ; la solution est révélée par les boutons.
        view = RiddleView(None, item["reponse"])
        try:
            if isinstance(channel, discord.ForumChannel):
                title = item["question"].strip()
                if len(title) > 100:
                    title = title[:97].rstrip() + "..."
                await channel.create_thread(
                    name=title or "🧩 La devinette du jour",
                    content="🧩 Une nouvelle devinette HORIZONS ! Réfléchissez ensemble, puis utilisez les boutons pour découvrir la solution.",
                    embed=embed,
                    view=view,
                )
            elif isinstance(channel, (discord.TextChannel)):
                await channel.send(embed=embed, view=view)
            else:
                log.error("Le salon des devinettes n'est ni un Forum ni un salon textuel (type : %s).", type(channel).__name__)
        except discord.Forbidden:
            log.exception("Permissions insuffisantes pour publier la devinette quotidienne.")
        except discord.HTTPException:
            log.exception("Impossible de publier la devinette quotidienne.")

    @daily_riddle.before_loop
    async def before_daily_riddle(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Riddles(bot))

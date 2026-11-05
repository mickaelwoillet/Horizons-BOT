"""Salons vocaux temporaires facultatifs, activés par configuration."""
from __future__ import annotations
import discord
from discord.ext import commands
from config import TEMP_VOICE_TRIGGER_ID, TEMP_VOICE_CATEGORY_ID

class TemporaryVoiceRooms(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.temporary: set[int] = set()

    async def cog_load(self):
        if TEMP_VOICE_CATEGORY_ID:
            for guild in self.bot.guilds:
                category = guild.get_channel(TEMP_VOICE_CATEGORY_ID)
                if isinstance(category, discord.CategoryChannel):
                    self.temporary.update(c.id for c in category.voice_channels if c.name.startswith("horizons-temp-"))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not TEMP_VOICE_TRIGGER_ID or not TEMP_VOICE_CATEGORY_ID: return
        if after.channel and after.channel.id == TEMP_VOICE_TRIGGER_ID and before.channel != after.channel:
            category = member.guild.get_channel(TEMP_VOICE_CATEGORY_ID)
            if not isinstance(category, discord.CategoryChannel): return
            safe = discord.utils.escape_markdown(member.display_name)[:24]
            channel = await member.guild.create_voice_channel(f"horizons-temp-{safe}", category=category, reason="Création d'un salon vocal temporaire")
            self.temporary.add(channel.id)
            try: await member.move_to(channel, reason="Création du salon vocal personnel")
            except discord.HTTPException:
                await channel.delete(reason="Impossible de déplacer le membre")
                self.temporary.discard(channel.id)
        # Le nom permet aussi de reconnaître les salons créés avant un redémarrage
        # du bot, lorsque l'ensemble en mémoire self.temporary est vide.
        if (
            before.channel
            and (before.channel.id in self.temporary or before.channel.name.startswith("horizons-temp-"))
            and len(before.channel.members) == 0
        ):
            cid = before.channel.id
            try: await before.channel.delete(reason="Salon vocal temporaire vide")
            except discord.HTTPException: pass
            self.temporary.discard(cid)

async def setup(bot: commands.Bot): await bot.add_cog(TemporaryVoiceRooms(bot))

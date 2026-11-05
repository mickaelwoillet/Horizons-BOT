"""Automodération prudente : répétitions et vagues de mentions."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
from collections import defaultdict, deque
from datetime import datetime, timezone
import discord
from discord.ext import commands
from config import MOD_LOG_CHANNEL_ID, AUTO_MOD_ENABLED, BLOCK_DISCORD_INVITES, STAFF_ROLE_ID

class AutoModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recent: dict[tuple[int,int], deque] = defaultdict(lambda: deque(maxlen=8))

    async def report(self, guild: discord.Guild, message: discord.Message, reason: str):
        channel = guild.get_channel(MOD_LOG_CHANNEL_ID) if MOD_LOG_CHANNEL_ID else None
        if channel:
            embed = horizons_embed(title="🛡️ Automodération", description=f"Message retiré dans {message.channel.mention}\nMembre : {message.author.mention}\nMotif : {reason}", color=discord.Color.orange(), timestamp=datetime.now(timezone.utc))
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not AUTO_MOD_ENABLED or not message.guild or message.author.bot: return
        if isinstance(message.author, discord.Member):
            if message.author.guild_permissions.manage_messages or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in message.author.roles)):
                return
        content = message.content.strip()
        reason = None
        if message.mention_everyone:
            reason = "Mention collective @everyone ou @here non autorisée."
        elif len(message.mentions) >= 8:
            reason = "Vague de mentions (8 membres ou plus)."
        elif BLOCK_DISCORD_INVITES and ("discord.gg/" in content.lower() or "discord.com/invite/" in content.lower()):
            reason = "Lien d'invitation Discord non autorisé."
        else:
            key = (message.guild.id, message.author.id)
            now = message.created_at.timestamp()
            queue = self.recent[key]
            while queue and now - queue[0][0] > 12: queue.popleft()
            normalized = " ".join(content.lower().split())
            if normalized and len(normalized) >= 12 and sum(1 for ts, text in queue if text == normalized) >= 3:
                reason = "Répétition excessive du même message."
            queue.append((now, normalized))
        if reason:
            try:
                await message.delete()
                await self.report(message.guild, message, reason)
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

async def setup(bot: commands.Bot): await bot.add_cog(AutoModeration(bot))

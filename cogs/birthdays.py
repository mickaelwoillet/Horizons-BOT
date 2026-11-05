"""Anniversaires facultatifs, conservés localement dans SQLite."""
from __future__ import annotations
from cogs.embed_theme import wait_for_logo_ready
from datetime import time, datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import BIRTHDAY_CHANNEL_ID, LOCAL_TIMEZONE
from .storage import db

class Birthdays(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_birthdays.start()
    def cog_unload(self): self.daily_birthdays.cancel()

    @app_commands.command(name="anniversaire_definir", description="Enregistrer ton anniversaire (jour et mois uniquement).")
    async def anniversaire_definir(self, interaction: discord.Interaction, jour: app_commands.Range[int,1,31], mois: app_commands.Range[int,1,12]):
        import calendar
        if jour > calendar.monthrange(2024, mois)[1]:
            await interaction.response.send_message("Cette date n'existe pas dans le calendrier.", ephemeral=True); return
        with db() as conn:
            conn.execute("INSERT INTO birthdays(guild_id,user_id,month,day,created_at) VALUES(?,?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET month=excluded.month,day=excluded.day,created_at=excluded.created_at", (interaction.guild_id,interaction.user.id,mois,jour,datetime.now(LOCAL_TIMEZONE).isoformat()))
        await interaction.response.send_message("🎂 Ton anniversaire est enregistré. Seuls le jour et le mois sont conservés, pas ton année de naissance.", ephemeral=True)

    @app_commands.command(name="anniversaire_supprimer", description="Supprimer ton anniversaire enregistré.")
    async def anniversaire_supprimer(self, interaction: discord.Interaction):
        with db() as conn:
            cur = conn.execute("DELETE FROM birthdays WHERE guild_id=? AND user_id=?", (interaction.guild_id,interaction.user.id))
        await interaction.response.send_message("Ton anniversaire a été supprimé." if cur.rowcount else "Aucun anniversaire n'était enregistré.", ephemeral=True)

    @tasks.loop(time=time(hour=9, minute=0, tzinfo=LOCAL_TIMEZONE))
    async def daily_birthdays(self):
        today = datetime.now(LOCAL_TIMEZONE)
        channel = self.bot.get_channel(BIRTHDAY_CHANNEL_ID) if BIRTHDAY_CHANNEL_ID else None
        if channel is None and BIRTHDAY_CHANNEL_ID:
            try: channel = await self.bot.fetch_channel(BIRTHDAY_CHANNEL_ID)
            except discord.HTTPException: return
        if channel is None: return
        with db() as conn:
            rows = conn.execute("SELECT user_id FROM birthdays WHERE guild_id=? AND month=? AND day=?", (channel.guild.id,today.month,today.day)).fetchall()
        for row in rows:
            uid = row["user_id"]
            with db() as conn:
                exists = conn.execute("SELECT 1 FROM birthday_posts WHERE guild_id=? AND year=? AND user_id=?", (channel.guild.id,today.year,uid)).fetchone()
            if exists: continue
            member = channel.guild.get_member(uid)
            if not member: continue
            try:
                await channel.send(f"🎉 Aujourd'hui, nous souhaitons un très joyeux anniversaire à {member.mention} ! Que cette journée soit belle ! 🎂")
            except discord.HTTPException: continue
            with db() as conn:
                conn.execute("INSERT OR IGNORE INTO birthday_posts(guild_id,year,user_id) VALUES(?,?,?)", (channel.guild.id,today.year,uid))
    @daily_birthdays.before_loop
    async def before_daily_birthdays(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot): await bot.add_cog(Birthdays(bot))

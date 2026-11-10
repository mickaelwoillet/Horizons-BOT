"""Anniversaires facultatifs, conservés localement dans SQLite."""
from __future__ import annotations
from cogs.embed_theme import wait_for_logo_ready
from datetime import time, datetime, date
import calendar
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import BIRTHDAY_CHANNEL_ID, LOCAL_TIMEZONE
from .storage import db

class BirthdayModal(discord.ui.Modal, title="Mon anniversaire HORIZONS"):
    date_anniversaire = discord.ui.TextInput(label="Jour et mois (JJ/MM)", placeholder="Exemple : 25/09", min_length=4, max_length=5)
    annee = discord.ui.TextInput(label="Année de naissance (facultatif)", placeholder="Exemple : 1998", required=False, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            day, month = map(int, str(self.date_anniversaire.value).strip().split("/"))
            if not 1 <= month <= 12 or day > calendar.monthrange(2024, month)[1] or day < 1:
                raise ValueError
        except (ValueError, TypeError):
            await interaction.response.send_message("Date invalide. Utilise le format JJ/MM (par exemple 25/09).", ephemeral=True); return
        year_text = str(self.annee.value or "").strip()
        year = None
        if year_text:
            try:
                year = int(year_text)
                today = datetime.now(LOCAL_TIMEZONE).date()
                if len(year_text) != 4 or year < 1900 or year > today.year or (month, day) > (today.month, today.day) and year == today.year:
                    raise ValueError
                date(year, month, day)
            except ValueError:
                await interaction.response.send_message("Année invalide. Indique une année de naissance réelle (4 chiffres), ou laisse le champ vide.", ephemeral=True); return
        with db() as conn:
            conn.execute("INSERT INTO birthdays(guild_id,user_id,month,day,birth_year,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET month=excluded.month,day=excluded.day,birth_year=excluded.birth_year,created_at=excluded.created_at", (interaction.guild_id,interaction.user.id,month,day,year,datetime.now(LOCAL_TIMEZONE).isoformat()))
        text = "🎂 Ton anniversaire a été enregistré ! " + ("Ton âge sera affiché le jour venu." if year else "Ton âge ne sera pas affiché.")
        await interaction.response.send_message(text, ephemeral=True)


class BirthdayPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Enregistrer / modifier mon anniversaire", emoji="🎂", style=discord.ButtonStyle.primary, custom_id="horizons:birthday:register")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BirthdayModal())


class Birthdays(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(BirthdayPanel())
        self.daily_birthdays.start()
    def cog_unload(self): self.daily_birthdays.cancel()

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
            rows = conn.execute("SELECT user_id, birth_year FROM birthdays WHERE guild_id=? AND month=? AND day=?", (channel.guild.id,today.month,today.day)).fetchall()
        for row in rows:
            uid = row["user_id"]
            with db() as conn:
                exists = conn.execute("SELECT 1 FROM birthday_posts WHERE guild_id=? AND year=? AND user_id=?", (channel.guild.id,today.year,uid)).fetchone()
            if exists: continue
            member = channel.guild.get_member(uid)
            if not member: continue
            try:
                age = today.year - int(row["birth_year"]) if row["birth_year"] is not None else None
                age_text = f" qui fête ses **{age} ans**" if age is not None and age >= 0 else ""
                from .nox_events import birthday as nox_birthday
                if not await nox_birthday(channel, member, age_text):
                    await channel.send(f"🎉 Aujourd'hui, nous souhaitons un très joyeux anniversaire à {member.mention}{age_text} ! Que cette journée soit belle ! 🎂")
            except discord.HTTPException: continue
            with db() as conn:
                conn.execute("INSERT OR IGNORE INTO birthday_posts(guild_id,year,user_id) VALUES(?,?,?)", (channel.guild.id,today.year,uid))
    @daily_birthdays.before_loop
    async def before_daily_birthdays(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot): await bot.add_cog(Birthdays(bot))

"""Rangs honorifiques fondés sur l'ancienneté et la régularité, sans XP ni classement."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import json
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from config import RANK_ROLE_IDS, STAFF_ROLE_ID, LOCAL_TIMEZONE
from .storage import db
from .horizons_features import ACHIEVEMENTS

RANKS = [
    ("Nouveau regard", 0, 0),
    ("Premier pas", 7, 3),
    ("Voix familière", 30, 10),
    ("Esprit ouvert", 60, 20),
    ("Lien vivant", 120, 40),
    ("Éclaireur", 180, 70),
    ("Bâtisseur d'horizons", 365, 120),
]

class CommunityRanks(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    def rank_index(self, member: discord.Member, active_days: int) -> int:
        tenure = max(0, (datetime.now(timezone.utc) - member.joined_at).days) if member.joined_at else 0
        result = 0
        for index, (_, days, activity) in enumerate(RANKS):
            if tenure >= days and active_days >= activity: result = index
        return result

    async def apply_rank(self, member: discord.Member, active_days: int):
        if not RANK_ROLE_IDS: return
        index = self.rank_index(member, active_days)
        role_id = RANK_ROLE_IDS.get(RANKS[index][0])
        if not role_id: return
        try: role_id = int(role_id)
        except (TypeError, ValueError): return
        target = member.guild.get_role(role_id)
        if not target: return
        rank_ids = {int(v) for v in RANK_ROLE_IDS.values() if str(v).isdigit()}
        to_remove = [r for r in member.roles if r.id in rank_ids and r.id != target.id]
        try:
            if to_remove: await member.remove_roles(*to_remove, reason="Mise à jour du rang honorifique HORIZONS")
            if target not in member.roles: await member.add_roles(target, reason="Progression communautaire HORIZONS")
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or len(message.content.strip()) < 25: return
        if message.content.startswith(("/", "!")): return
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        with db() as conn:
            cur = conn.execute("INSERT OR IGNORE INTO activity_days(guild_id,user_id,active_date) VALUES(?,?,?)", (message.guild.id,message.author.id,today))
            if not cur.rowcount: return
            count = conn.execute("SELECT COUNT(*) FROM activity_days WHERE guild_id=? AND user_id=?", (message.guild.id,message.author.id)).fetchone()[0]
        if isinstance(message.author, discord.Member): await self.apply_rank(message.author, count)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.apply_rank(member, 0)

    @app_commands.command(name="mon_parcours", description="Consulter ton rang honorifique HORIZONS.")
    async def mon_parcours(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member): return
        with db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM activity_days WHERE guild_id=? AND user_id=?", (interaction.guild_id,interaction.user.id)).fetchone()[0]
        idx = self.rank_index(interaction.user, count)
        name, tenure, activity = RANKS[idx]
        days = max(0, (datetime.now(timezone.utc)-interaction.user.joined_at).days) if interaction.user.joined_at else 0
        embed = horizons_embed(title="🌱 Ton parcours HORIZONS", description=f"**Rang actuel : {name}**", color=discord.Color.teal())
        embed.add_field(name="Ancienneté", value=f"{days} jour(s)")
        embed.add_field(name="Jours actifs enregistrés", value=str(count))
        if idx < len(RANKS)-1:
            next_name, next_tenure, next_activity = RANKS[idx+1]
            embed.add_field(name="Prochaine étape", value=f"{next_name}\nAncienneté requise : {next_tenure} jours\nJours actifs requis : {next_activity}", inline=False)
        embed.set_footer(text="HORIZONS • Aucun classement, aucun compteur de messages : la régularité compte davantage que le volume.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="progression", description="Voir l'ensemble de ta progression communautaire HORIZONS.")
    async def progression(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        member = interaction.user
        features = self.bot.get_cog("HorizonsFeatures")
        if features:
            await features.check_achievements(interaction.guild, member)
        today = datetime.now(LOCAL_TIMEZONE)
        week = today.isocalendar()
        week_key = f"{week.year}-W{week.week:02d}"
        with db() as conn:
            active_days = conn.execute(
                "SELECT COUNT(*) FROM activity_days WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            missions = conn.execute(
                "SELECT COUNT(*) FROM passport_completions WHERE guild_id=? AND user_id=? AND week_key=?",
                (interaction.guild_id, member.id, week_key),
            ).fetchone()[0]
            ideas = conn.execute(
                "SELECT COUNT(*) FROM community_ideas WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            accepted_ideas = conn.execute(
                "SELECT COUNT(*) FROM community_ideas WHERE guild_id=? AND user_id=? AND status IN ('accepted','done')",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            thanks_given = conn.execute(
                "SELECT COUNT(*) FROM solidarity_thanks WHERE guild_id=? AND author_id=?",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            thanks_received = conn.execute(
                "SELECT COUNT(*) FROM solidarity_thanks WHERE guild_id=? AND target_id=?",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            challenges = conn.execute(
                "SELECT COUNT(*) FROM collective_challenge_members m JOIN collective_challenges c ON c.id=m.challenge_id WHERE c.guild_id=? AND m.user_id=?",
                (interaction.guild_id, member.id),
            ).fetchone()[0]
            successes = conn.execute(
                "SELECT achievement_key FROM success_unlocks WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, member.id),
            ).fetchall()
        idx = self.rank_index(member, active_days)
        rank_name = RANKS[idx][0]
        embed = horizons_embed(title="🧭 Ta progression HORIZONS", description=(
            f"**Rang honorifique : {rank_name}**\n"
            "Ta progression valorise la régularité, les contributions et les liens créés. "
            "Il n'existe ni classement général ni course aux messages."
        ), color=discord.Color.teal())
        embed.add_field(name="🌱 Présence", value=f"{active_days} jour(s) actif(s) enregistré(s)", inline=True)
        embed.add_field(name="🧭 Missions", value=f"{missions}/3 cette semaine", inline=True)
        embed.add_field(name="💡 Contributions", value=f"{ideas} idée(s) proposée(s)\n{accepted_ideas} retenue(s)", inline=True)
        embed.add_field(name="💜 Entraide", value=f"{thanks_given} merci partagé(s)\n{thanks_received} merci reçu(s)", inline=True)
        embed.add_field(name="🌟 Défis collectifs", value=f"{challenges} participation(s)", inline=True)
        embed.add_field(name="🏆 Succès", value=f"{len(successes)}/{len(ACHIEVEMENTS)} débloqué(s)", inline=True)
        if idx < len(RANKS) - 1:
            next_name, tenure, activity = RANKS[idx + 1]
            joined_days = max(0, (datetime.now(timezone.utc) - member.joined_at).days) if member.joined_at else 0
            embed.add_field(name="Prochaine étape", value=(
                f"**{next_name}**\nAncienneté : {joined_days}/{tenure} jours\nJours actifs : {active_days}/{activity}"
            ), inline=False)
        embed.set_footer(text="HORIZONS • Chaque contribution compte, à ton rythme.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="actualiser_rangs", description="Recalculer les rangs honorifiques des membres (équipe).")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def actualiser_rangs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        members = interaction.guild.members
        updated = 0
        for member in members:
            if member.bot: continue
            with db() as conn:
                count = conn.execute("SELECT COUNT(*) FROM activity_days WHERE guild_id=? AND user_id=?", (interaction.guild_id,member.id)).fetchone()[0]
            await self.apply_rank(member, count); updated += 1
        await interaction.followup.send(f"Recalcul terminé pour {updated} membre(s). Vérifie que les identifiants de rôles sont configurés et que le rôle du bot est assez haut.", ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(CommunityRanks(bot))

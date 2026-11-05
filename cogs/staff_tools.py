"""Signalements, alertes internes et messages anonymes facultatifs."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
from datetime import datetime, timezone
from collections import defaultdict, deque
import time
import discord
from discord import app_commands
from discord.ext import commands
from config import ALERT_LOG_CHANNEL_ID, STAFF_ROLE_ID, ANONYMOUS_CHANNEL_ID, GUILD_ID
from .storage import db

class StaffTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.anonymous_posts: dict[int, deque[float]] = defaultdict(deque)

    @app_commands.command(name="signaler", description="Transmettre discrètement un signalement à l'équipe.")
    @app_commands.describe(motif="Explique brièvement ce qui pose problème", salon="Salon concerné, si applicable", message_id="Identifiant du message concerné, si disponible")
    async def signaler(self, interaction: discord.Interaction, motif: app_commands.Range[str,5,1200], salon: discord.TextChannel | None = None, message_id: str | None = None):
        channel = self.bot.get_channel(ALERT_LOG_CHANNEL_ID) if ALERT_LOG_CHANNEL_ID else None
        if not channel:
            await interaction.response.send_message("Le canal de signalement n'est pas configuré. Contacte directement un membre de l'équipe.", ephemeral=True); return
        embed = horizons_embed(title="🚩 Nouveau signalement", description=motif, color=discord.Color.orange())
        embed.add_field(name="Auteur", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.add_field(name="Salon", value=salon.mention if salon else "Non précisé", inline=True)
        if message_id: embed.add_field(name="Message concerné", value=message_id[:40], inline=True)
        embed.set_footer(text="Signalement confidentiel • HORIZONS")
        posted = await channel.send(embed=embed)
        with db() as conn:
            conn.execute("INSERT INTO staff_alerts(guild_id,user_id,reporter_id,reason,channel_id,message_id,created_at) VALUES(?,?,?,?,?,?,?)", (interaction.guild_id or GUILD_ID or 0, interaction.user.id, interaction.user.id, motif, salon.id if salon else None, message_id, datetime.now(timezone.utc).isoformat()))
        await interaction.response.send_message("Merci. Ton signalement a été transmis à l'équipe de manière confidentielle.", ephemeral=True)

    @app_commands.command(name="alerte_equipe", description="Envoyer une alerte urgente à l'équipe HORIZONS.")
    async def alerte_equipe(self, interaction: discord.Interaction, message: app_commands.Range[str,5,1000]):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (member.guild_permissions.administrator or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles)))
        if not allowed:
            await interaction.response.send_message("Commande réservée à l'équipe.", ephemeral=True); return
        channel = self.bot.get_channel(ALERT_LOG_CHANNEL_ID) if ALERT_LOG_CHANNEL_ID else None
        if not channel:
            await interaction.response.send_message("Canal d'alerte non configuré.", ephemeral=True); return
        embed = horizons_embed(title="🚨 Alerte équipe", description=message, color=discord.Color.red())
        embed.add_field(name="Émise par", value=interaction.user.mention)
        await channel.send(content=f"<@&{STAFF_ROLE_ID}>" if STAFF_ROLE_ID else None, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
        await interaction.response.send_message("Alerte transmise à l'équipe.", ephemeral=True)

    @app_commands.command(name="message_anonyme", description="Publier un message sans afficher ton identité (si le salon est configuré).")
    async def message_anonyme(self, interaction: discord.Interaction, message: app_commands.Range[str,5,1500]):
        channel = self.bot.get_channel(ANONYMOUS_CHANNEL_ID) if ANONYMOUS_CHANNEL_ID else None
        if not channel:
            await interaction.response.send_message("La publication anonyme n'est pas activée pour le moment.", ephemeral=True); return
        now = time.monotonic()
        history = self.anonymous_posts[interaction.user.id]
        while history and now - history[0] >= 600:
            history.popleft()
        if len(history) >= 2:
            retry_after = max(1, int(600 - (now - history[0])))
            await interaction.response.send_message(
                f"Tu as atteint la limite de publications anonymes. Réessaie dans {retry_after} seconde(s).",
                ephemeral=True,
            )
            return
        history.append(now)
        embed = horizons_embed(title="💬 Un message de la communauté", description=message, color=discord.Color.teal())
        embed.set_footer(text="Message transmis anonymement via HORIZONS")
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        # L'identité reste cachée aux membres, mais un journal réservé à l'équipe
        # permet de traiter les abus et signalements éventuels.
        staff_log = self.bot.get_channel(ALERT_LOG_CHANNEL_ID) if ALERT_LOG_CHANNEL_ID else None
        if staff_log:
            audit = horizons_embed(
                title="🧾 Journal interne — publication anonyme",
                description=message,
                color=discord.Color.dark_teal(),
            )
            audit.add_field(name="Auteur (équipe uniquement)", value=f"{interaction.user} (`{interaction.user.id}`)")
            audit.add_field(name="Salon de publication", value=channel.mention)
            await staff_log.send(embed=audit, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message(
            "Ton message a été transmis anonymement. Ton identité n'est pas affichée aux membres ; l'équipe conserve une trace interne pour prévenir les abus.",
            ephemeral=True,
        )

async def setup(bot: commands.Bot): await bot.add_cog(StaffTools(bot))

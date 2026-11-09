"""Commandes générales et informations HORIZONS."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from config import LOCAL_TIMEZONE, GUILD_ID

class General(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    @app_commands.command(name="ping", description="Vérifier si le bot HORIZONS répond.")
    async def ping(self, interaction: discord.Interaction):
        ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong ! Latence : **{ms} ms**", ephemeral=True)

    async def _send_command_guide(self, interaction: discord.Interaction, audience: str) -> None:
        """Affiche uniquement les commandes réellement chargées, en pages privées."""
        from cogs.command_catalog import build_catalog_embeds
        pages = build_catalog_embeds(self.bot, audience=audience)
        # Discord autorise au maximum 10 embeds par message ; limiter davantage
        # pour rester sous la limite cumulée de 6000 caractères par message.
        await interaction.response.defer(ephemeral=True)
        for page in pages:
            await interaction.followup.send(embed=page, ephemeral=True)

    @app_commands.command(name="aide", description="Consulter les commandes accessibles aux membres HORIZONS.")
    async def aide(self, interaction: discord.Interaction):
        await self._send_command_guide(interaction, "members")

    @app_commands.command(name="aidestaff", description="Consulter les commandes et permissions de l'équipe HORIZONS.")
    @app_commands.guild_only()
    async def aidestaff(self, interaction: discord.Interaction):
        from cogs.staff_dashboard import access_level
        if not isinstance(interaction.user, discord.Member) or access_level(interaction.user) is None:
            await interaction.response.send_message("🔒 Cette aide est réservée à l'équipe HORIZONS.", ephemeral=True)
            return
        await self._send_command_guide(interaction, "staff")

    @app_commands.command(name="profil", description="Afficher les informations publiques d'un membre.")
    async def profil(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        target = membre or interaction.user
        if not isinstance(target, discord.Member):
            await interaction.response.send_message("Ce profil n'est pas disponible ici.", ephemeral=True); return
        embed = horizons_embed(title=f"Profil de {target.display_name}", color=target.color if target.color.value else discord.Color.blurple())
        embed.set_author(name=f'Membre : {target.display_name}', icon_url=target.display_avatar.url)
        embed.add_field(name="Compte créé", value=discord.utils.format_dt(target.created_at, style="D"), inline=True)
        if target.joined_at: embed.add_field(name="A rejoint HORIZONS", value=discord.utils.format_dt(target.joined_at, style="D"), inline=True)
        visible_roles = [r.mention for r in reversed(target.roles[1:]) if not r.is_default()]
        embed.add_field(name="Rôles", value=", ".join(visible_roles[:15]) if visible_roles else "Aucun rôle affiché", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serveur", description="Afficher les informations du serveur.")
    async def serveur(self, interaction: discord.Interaction):
        g = interaction.guild
        if not g:
            await interaction.response.send_message("Cette commande est disponible sur le serveur.", ephemeral=True); return
        embed = horizons_embed(title=f"🌅 {g.name}", description=g.description or "Nos différences nous rapprochent.", color=discord.Color.blurple())
        embed.add_field(name="Membres", value=str(g.member_count or "—"))
        embed.add_field(name="Créé le", value=discord.utils.format_dt(g.created_at, style="D"))
        if g.icon: embed.set_image(url=g.icon.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="proposer", description="Transmettre une idée à l'équipe HORIZONS.")
    @app_commands.describe(idee="Ton idée ou ta suggestion")
    async def proposer(self, interaction: discord.Interaction, idee: app_commands.Range[str, 10, 1500]):
        from config import SUGGESTION_CHANNEL_ID
        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID) if SUGGESTION_CHANNEL_ID else None
        if channel is None:
            await interaction.response.send_message("Le canal des propositions n'est pas encore configuré. Tu peux contacter l'équipe.", ephemeral=True); return
        embed = horizons_embed(title="💡 Nouvelle proposition", description=idee, color=discord.Color.teal())
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.timestamp = datetime.now(LOCAL_TIMEZONE)
        if isinstance(channel, discord.ForumChannel):
            title = " ".join(idee.split()).strip()
            title = title[:97].rstrip()
            if len(" ".join(idee.split())) > 97:
                title += "..."
            await channel.create_thread(name=f"💡 {title}"[:100], embed=embed)
        elif isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.send(embed=embed)
        else:
            await interaction.response.send_message(
                "Le salon des propositions n'est pas configuré avec un type compatible. Contacte l'équipe.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message("Merci ! Ta proposition a été transmise à l'équipe.", ephemeral=True)

    @app_commands.command(name="presentation", description="Recevoir un rappel pour se présenter.")
    async def presentation(self, interaction: discord.Interaction):
        from config import INTRO_CHANNEL_ID
        channel = self.bot.get_channel(INTRO_CHANNEL_ID) if INTRO_CHANNEL_ID else None
        mention = channel.mention if channel else "le salon de présentation"
        await interaction.response.send_message(f"Bienvenue dans HORIZONS ! Tu peux faire connaissance avec la communauté dans {mention}.", ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(General(bot))

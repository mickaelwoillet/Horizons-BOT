"""Publication d'annonces HORIZONS par les membres habilités."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import discord
from discord import app_commands
from discord.ext import commands
from config import STAFF_ROLE_ID, DEFAULT_ANNOUNCEMENT_IMAGE_URL

class Announcements(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    @app_commands.command(name="annonce", description="Publier une annonce officielle dans un salon.")
    @app_commands.describe(salon="Salon de publication", titre="Titre de l'annonce", message="Contenu", image="URL facultative d'une image")
    async def annonce(self, interaction: discord.Interaction, salon: discord.TextChannel, titre: app_commands.Range[str,3,200], message: app_commands.Range[str,5,3500], image: str | None = None):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (member.guild_permissions.administrator or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles)))
        if not allowed:
            await interaction.response.send_message("Cette commande est réservée à l'équipe HORIZONS.", ephemeral=True); return
        embed = horizons_embed(title=f"📢 {titre}", description=message, color=discord.Color.blurple())
        embed.set_footer(text="HORIZONS • Nos différences nous rapprochent")
        if image:
            if not image.startswith(("https://", "http://")):
                await interaction.response.send_message("L'image doit être une URL HTTP ou HTTPS.", ephemeral=True); return
            embed.set_image(url=image)
        elif DEFAULT_ANNOUNCEMENT_IMAGE_URL:
            embed.set_image(url=DEFAULT_ANNOUNCEMENT_IMAGE_URL)
        embed.timestamp = discord.utils.utcnow()
        await salon.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        await interaction.response.send_message(f"Annonce publiée dans {salon.mention}.", ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(Announcements(bot))

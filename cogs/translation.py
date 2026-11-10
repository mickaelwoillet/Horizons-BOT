"""Traduction facultative via une instance LibreTranslate configurée par l'administrateur."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from config import TRANSLATE_API_URL, TRANSLATE_API_KEY

LANGUAGES = [
    app_commands.Choice(name="Français", value="fr"),
    app_commands.Choice(name="Anglais", value="en"),
    app_commands.Choice(name="Allemand", value="de"),
    app_commands.Choice(name="Espagnol", value="es"),
    app_commands.Choice(name="Italien", value="it"),
    app_commands.Choice(name="Portugais", value="pt"),
    app_commands.Choice(name="Néerlandais", value="nl"),
    app_commands.Choice(name="Arabe", value="ar"),
    app_commands.Choice(name="Turc", value="tr"),
    app_commands.Choice(name="Polonais", value="pl"),
]

class Translation(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    async def traduire(self, interaction: discord.Interaction, texte: app_commands.Range[str,1,1800], langue: app_commands.Choice[str]):
        if not TRANSLATE_API_URL:
            await interaction.response.send_message("La traduction n'est pas encore configurée par l'équipe HORIZONS.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True, thinking=True)
        payload = {"q": texte, "source": "auto", "target": langue.value, "format": "text"}
        if TRANSLATE_API_KEY: payload["api_key"] = TRANSLATE_API_KEY
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(TRANSLATE_API_URL, json=payload) as response:
                    if response.status != 200:
                        await interaction.followup.send(f"Le service de traduction a répondu avec le statut HTTP {response.status}.", ephemeral=True); return
                    data = await response.json(content_type=None)
            translated = data.get("translatedText") if isinstance(data,dict) else None
            if not isinstance(translated,str) or not translated.strip():
                await interaction.followup.send("Le service n'a pas renvoyé de traduction exploitable.", ephemeral=True); return
            embed = horizons_embed(title=f"🌍 Traduction • {langue.name}", description=translated[:4000], color=discord.Color.teal())
            embed.set_footer(text="HORIZONS • La traduction automatique peut comporter des erreurs.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            await interaction.followup.send("Le service de traduction est momentanément inaccessible. Réessaie plus tard.", ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(Translation(bot))

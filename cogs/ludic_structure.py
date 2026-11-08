"""Création idempotente de l'espace ludique et des rôles de constellations."""
from __future__ import annotations
import json
import logging
import discord
from discord import app_commands
from discord.ext import commands
from cogs.storage import db
from cogs.embed_theme import horizons_embed
from config import GUILD_ID

log = logging.getLogger(__name__)

CATEGORY_NAME = "🎮・𝐉𝐄𝐔𝐗 & 𝐂𝐎𝐍𝐒𝐓𝐄𝐋𝐋𝐀𝐓𝐈𝐎𝐍𝐒"
CHANNELS = {
    "arcade": ("🎮・𝗮𝗿𝗰𝗮𝗱𝗲-𝗵𝗼𝗿𝗶𝘇𝗼𝗻𝘀", "Les jeux interactifs HORIZONS : défis individuels et parties collectives."),
    "treasures": ("🌌・𝘁𝗿é𝘀𝗼𝗿𝘀-𝗱𝘂-𝗰𝗶𝗲𝗹", "Cartes à gratter, étoiles, collections et constellations HORIZONS."),
}
ROLES = [
    ("🌅 Éclat des Origines", 0xD9A441),
    ("💗 Gardien des Liens", 0xD982A8),
    ("🔥 Gardien des Forces", 0xD96B42),
    ("✨ Porteur de Lumière", 0xE5D77A),
    ("🌌 Gardien de l'Infini", 0x7788C8),
    ("🌟 Gardien des 20 étoiles", 0xF3C969),
]

class LudicStructure(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    @app_commands.command(name="ajoutstructure", description="Créer l'espace Jeux & Constellations HORIZONS.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def ajoutstructure(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None or guild.id != GUILD_ID:
            await interaction.response.send_message("Cette commande doit être utilisée sur le serveur HORIZONS.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True, thinking=True)
        bot_member = guild.get_member(interaction.client.user.id) if interaction.client.user else None
        bot_role = bot_member.top_role if bot_member else None
        if bot_role is None or not bot_member.guild_permissions.manage_roles or not bot_member.guild_permissions.manage_channels:
            await interaction.followup.send("Il me manque la permission **Gérer les rôles** ou **Gérer les salons**.", ephemeral=True); return

        created = {"category": False, "channels": [], "roles": []}
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
            }
            member_role = guild.get_role(1566561934533468294)
            if member_role:
                overwrites[member_role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, embed_links=True, attach_files=True, add_reactions=True)
            for role_id in (1566561935879704606, 1566561900865785918, 1566561912794124338, 1566561919647875152, 1566561923670212828, 1566561889188839477, 1566561887305339001):
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, embed_links=True, attach_files=True, add_reactions=True)
            if bot_role:
                overwrites[bot_role] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, manage_channels=True, manage_messages=True, embed_links=True, attach_files=True)
            category = await guild.create_category(CATEGORY_NAME, overwrites=overwrites, reason="Création de l'univers ludique HORIZONS")
            created["category"] = True

        channel_ids = {}
        for key, (name, topic) in CHANNELS.items():
            channel = discord.utils.get(guild.text_channels, name=name)
            if channel is None:
                channel = await guild.create_text_channel(name, category=category, overwrites=category.overwrites, topic=topic, reason="Création de l'univers ludique HORIZONS")
                created["channels"].append(name)
            elif channel.category_id != category.id:
                await channel.edit(category=category, sync_permissions=True, reason="Rattachement à l'univers ludique HORIZONS")
            channel_ids[key] = channel.id

        role_ids = {}
        for name, color in ROLES:
            role = discord.utils.get(guild.roles, name=name)
            if role is None:
                role = await guild.create_role(name=name, colour=discord.Colour(color), hoist=False, mentionable=False, reason="Rôles de progression des constellations HORIZONS")
                created["roles"].append(name)
            role_ids[name] = role.id

        settings = {
            "category_id": category.id,
            "arcade_channel_id": channel_ids["arcade"],
            "treasures_channel_id": channel_ids["treasures"],
            "constellation_role_ids": role_ids,
        }
        with db() as conn:
            for key, value in settings.items():
                conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"ludic:{guild.id}:{key}", json.dumps(value, ensure_ascii=False)))
            info_row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (f"ludic:{guild.id}:arcade_info_message_id",)).fetchone()
        # Publie immédiatement le panneau d'accueil de l'Arcade. Les tâches
        # périodiques le supprimeront puis le republieront toutes les deux heures.
        arcade_cog = self.bot.get_cog("HorizonsArcade")
        arcade_channel = guild.get_channel(channel_ids["arcade"])
        if arcade_cog and isinstance(arcade_channel, discord.TextChannel):
            info_message = None
            if info_row:
                try:
                    info_message = await arcade_channel.fetch_message(int(json.loads(info_row[0])))
                    await info_message.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                    info_message = None
            try:
                info_message = await arcade_channel.send(embed=arcade_cog.build_arcade_embed())
                with db() as conn:
                    conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"ludic:{guild.id}:arcade_info_message_id", json.dumps(info_message.id)))
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Impossible de publier le panneau d'accueil de l'Arcade HORIZONS.")
        # Le salon Trésors reçoit lui aussi son panneau, republié toutes les 2 h.
        treasures_cog = self.bot.get_cog("CelestialTreasures")
        treasures_channel = guild.get_channel(channel_ids["treasures"])
        with db() as conn:
            treasures_row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (f"ludic:{guild.id}:treasures_info_message_id",)).fetchone()
        if treasures_cog and isinstance(treasures_channel, discord.TextChannel):
            treasures_message = None
            if treasures_row:
                try:
                    treasures_message = await treasures_channel.fetch_message(int(json.loads(treasures_row[0])))
                    await treasures_message.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                    treasures_message = None
            try:
                treasures_message = await treasures_channel.send(embed=treasures_cog.build_treasures_embed())
                with db() as conn:
                    conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"ludic:{guild.id}:treasures_info_message_id", json.dumps(treasures_message.id)))
            except (discord.Forbidden, discord.HTTPException):
                log.exception("Impossible de publier le panneau Trésors du Ciel HORIZONS.")
        embed = horizons_embed(title="🌌 Univers ludique HORIZONS configuré", description="La structure est prête. Les éléments déjà présents ont été conservés et réutilisés.")
        embed.add_field(name="Catégorie", value=f"{category.name} {'(créée)' if created['category'] else '(déjà présente)'}", inline=False)
        embed.add_field(name="Salons", value="\n".join(f"{name} — {'créé' if name in created['channels'] else 'réutilisé'}" for name, _ in CHANNELS.values()), inline=False)
        embed.add_field(name="Rôles de constellations", value="\n".join(f"{name} — {'créé' if name in created['roles'] else 'réutilisé'}" for name, _ in ROLES), inline=False)
        embed.set_footer(text="HORIZONS • Aucun salon de routine quotidienne n'a été modifié")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot): await bot.add_cog(LudicStructure(bot))

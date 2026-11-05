"""Journaux d'audit et messages de bienvenue/départ."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
from datetime import datetime, timezone
import discord
from discord.ext import commands
from config import LOG_CHANNEL_ID, MOD_LOG_CHANNEL_ID, LEAVE_CHANNEL_ID, WELCOME_CHANNEL_ID, NEW_MEMBER_ROLE_ID

class LoggingTools(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    async def send_log(self, guild: discord.Guild, title: str, description: str, color: discord.Color = discord.Color.blurple(), channel_id: int | None = None):
        cid = channel_id or LOG_CHANNEL_ID
        channel = guild.get_channel(cid) if cid else None
        if channel:
            embed = horizons_embed(title=title, description=description[:4000], color=color, timestamp=datetime.now(timezone.utc))
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.send_log(member.guild, "📥 Arrivée", f"{member.mention} (`{member.id}`) a rejoint le serveur.", discord.Color.green())
        # Tous les nouveaux arrivants commencent avec le rôle temporaire.
        newcomer_role = member.guild.get_role(NEW_MEMBER_ROLE_ID) if NEW_MEMBER_ROLE_ID else None
        if newcomer_role and newcomer_role not in member.roles:
            try:
                await member.add_roles(newcomer_role, reason="Accueil automatique HORIZONS")
            except discord.Forbidden:
                await self.send_log(member.guild, "⚠️ Rôle de bienvenue non attribué",
                    f"Impossible d'attribuer {newcomer_role.mention} à {member.mention}. Vérifier la hiérarchie des rôles et la permission Gérer les rôles.", discord.Color.red())
        # Le message d’accueil guidé est désormais géré par cogs.smart_welcome.

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.send_log(member.guild, "📤 Départ", f"**{discord.utils.escape_markdown(str(member))}** (`{member.id}`) a quitté le serveur.", discord.Color.orange())
        # Le salon d'au revoir est volontairement le même que celui des arrivées.
        leave_id = LEAVE_CHANNEL_ID or WELCOME_CHANNEL_ID
        channel = member.guild.get_channel(leave_id) if leave_id else None
        if channel:
            embed = horizons_embed(
                title="👋 Un horizon se referme",
                description=f"**{discord.utils.escape_markdown(member.display_name)}** vient de quitter HORIZONS.\n\nNous lui souhaitons une bonne continuation et lui adressons nos meilleurs vœux pour la suite. 💜",
                color=discord.Color.orange())
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot: return
        content = message.content.strip() or "[contenu non textuel ou indisponible]"
        content = discord.utils.escape_markdown(content[:1200])
        await self.send_log(message.guild, "🗑️ Message supprimé", f"Auteur : {message.author.mention} (`{message.author.id}`)\nSalon : {message.channel.mention}\nContenu :\n{content}", discord.Color.orange())

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content: return
        old = discord.utils.escape_markdown(before.content[:900] or "[vide]")
        new = discord.utils.escape_markdown(after.content[:900] or "[vide]")
        await self.send_log(before.guild, "✏️ Message modifié", f"Auteur : {before.author.mention}\nSalon : {before.channel.mention}\nAvant :\n{old}\n\nAprès :\n{new}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel: return
        if before.channel is None and after.channel:
            detail = f"{member.mention} a rejoint {after.channel.mention}."
        elif after.channel is None and before.channel:
            detail = f"{member.mention} a quitté {before.channel.mention}."
        else:
            detail = f"{member.mention} est passé de {before.channel.mention} à {after.channel.mention}."
        await self.send_log(member.guild, "🔊 Activité vocale", detail)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        old = {r.id for r in before.roles}; new = {r.id for r in after.roles}
        added = [r.mention for r in after.roles if r.id in new-old]
        removed = [r.mention for r in before.roles if r.id in old-new]
        if added or removed:
            parts = []
            if added: parts.append("Ajoutés : " + ", ".join(added))
            if removed: parts.append("Retirés : " + ", ".join(removed))
            await self.send_log(after.guild, "🎭 Rôles modifiés", f"Membre : {after.mention}\n" + "\n".join(parts))

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        await self.send_log(role.guild, "🗑️ Rôle supprimé", f"Rôle : **{role.name}** (`{role.id}`)")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        await self.send_log(role.guild, "🎭 Rôle créé", f"Rôle : {role.mention} (`{role.id}`)")

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        await self.send_log(guild, "⛔ Bannissement détecté", f"Utilisateur : **{discord.utils.escape_markdown(str(user))}** (`{user.id}`).", discord.Color.red(), MOD_LOG_CHANNEL_ID)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        await self.send_log(guild, "✅ Débannissement détecté", f"Utilisateur : **{discord.utils.escape_markdown(str(user))}** (`{user.id}`).", discord.Color.green(), MOD_LOG_CHANNEL_ID)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        changes = []
        if before.name != after.name: changes.append(f"Nom : **{before.name}** → **{after.name}**")
        if before.permissions != after.permissions: changes.append("Permissions modifiées")
        if changes:
            await self.send_log(after.guild, "🎭 Rôle modifié", f"Rôle : {after.mention} (`{after.id}`)\n" + "\n".join(changes))

async def setup(bot: commands.Bot): await bot.add_cog(LoggingTools(bot))

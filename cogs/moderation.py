"""Modération HORIZONS : sanctions, avertissements, notes et nettoyage."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands
from .storage import db
from config import MOD_LOG_CHANNEL_ID, STAFF_ROLE_ID, INFRACTION_LOG_CHANNEL_ID, ADMIN_BOT_LOG_CHANNEL_ID, MESSAGE_LOG_CHANNEL_ID


def staff_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return False
        with db() as conn:
            active = conn.execute("SELECT 1 FROM staff_shifts WHERE guild_id=? AND user_id=? AND ended_at IS NULL LIMIT 1", (interaction.guild_id, interaction.user.id)).fetchone()
        if not active:
            return False
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.moderate_members: return True
        return bool(STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles))
    return app_commands.check(predicate)

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot): self.bot = bot

    async def log_action(self, guild: discord.Guild, title: str, description: str, color: discord.Color = discord.Color.orange(), channel_id: int | None = None):
        cid = channel_id or ADMIN_BOT_LOG_CHANNEL_ID or MOD_LOG_CHANNEL_ID or 0
        channel = guild.get_channel(cid) if cid else None
        if channel:
            embed = horizons_embed(title=title, description=description, color=color, timestamp=datetime.now(timezone.utc))
            await channel.send(embed=embed)

    @app_commands.command(name="avertir", description="Enregistrer un avertissement pour un membre.")
    @staff_check()
    async def avertir(self, interaction: discord.Interaction, membre: discord.Member, raison: app_commands.Range[str, 3, 1000]):
        with db() as conn:
            cur = conn.execute("INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)", (interaction.guild_id,membre.id,interaction.user.id,raison,datetime.now(timezone.utc).isoformat()))
            warning_id = cur.lastrowid
        await interaction.response.send_message(f"⚠️ Avertissement **#{warning_id}** enregistré pour {membre.mention}.", ephemeral=True)
        automod = self.bot.get_cog("AutoModeration")
        if automod:
            await automod.register_manual_infraction(interaction.guild, membre, raison, interaction.user)
        else:
            await self.log_action(interaction.guild, "⚠️ Avertissement", f"Membre : {membre.mention}\nModérateur : {interaction.user.mention}\nMotif : {raison}\nRéférence : #{warning_id}", channel_id=INFRACTION_LOG_CHANNEL_ID)
        try: await membre.send(f"Tu as reçu un avertissement sur **{interaction.guild.name}**.\nMotif : {raison}")
        except discord.Forbidden: pass

    @app_commands.command(name="avertissements", description="Consulter les avertissements actifs d'un membre.")
    @staff_check()
    async def avertissements(self, interaction: discord.Interaction, membre: discord.Member):
        with db() as conn:
            rows = conn.execute("SELECT id,reason,moderator_id,created_at FROM warnings WHERE guild_id=? AND user_id=? AND active=1 ORDER BY id DESC LIMIT 15", (interaction.guild_id,membre.id)).fetchall()
        if not rows: await interaction.response.send_message(f"Aucun avertissement actif pour {membre.mention}.", ephemeral=True); return
        lines = [f"**#{r['id']}** — {r['reason']}\nDate : {r['created_at']} · Modérateur : <@{r['moderator_id']}>" for r in rows]
        await interaction.response.send_message(embed=horizons_embed(title=f"Avertissements — {membre}", description="\n\n".join(lines), color=discord.Color.orange()), ephemeral=True)

    @app_commands.command(name="retirer_avertissement", description="Clôturer un avertissement par son numéro.")
    @staff_check()
    async def retirer_avertissement(self, interaction: discord.Interaction, numero: app_commands.Range[int,1,999999]):
        with db() as conn:
            cur = conn.execute("UPDATE warnings SET active=0 WHERE id=? AND guild_id=? AND active=1", (numero,interaction.guild_id))
        if not cur.rowcount: await interaction.response.send_message("Aucun avertissement actif ne correspond à ce numéro.", ephemeral=True); return
        await interaction.response.send_message(f"L'avertissement **#{numero}** a été clôturé.", ephemeral=True)

    @app_commands.command(name="timeout", description="Mettre temporairement un membre en sourdine.")
    @staff_check()
    async def timeout(self, interaction: discord.Interaction, membre: discord.Member, minutes: app_commands.Range[int,1,40320], raison: str = "Non précisée"):
        if membre.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
            await interaction.response.send_message("Tu ne peux pas sanctionner un membre ayant un rôle égal ou supérieur au tien.", ephemeral=True); return
        await membre.timeout(timedelta(minutes=minutes), reason=f"{raison} | par {interaction.user}")
        await interaction.response.send_message(f"{membre.mention} est mis en timeout pendant **{minutes} min**.", ephemeral=True)
        await self.log_action(interaction.guild, "🔇 Timeout", f"Membre : {membre.mention}\nDurée : {minutes} min\nMotif : {raison}\nPar : {interaction.user.mention}", channel_id=INFRACTION_LOG_CHANNEL_ID)

    @app_commands.command(name="untimeout", description="Retirer le timeout d'un membre.")
    @staff_check()
    async def untimeout(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Fin de sanction"):
        await membre.timeout(None, reason=f"{raison} | par {interaction.user}")
        await interaction.response.send_message(f"Le timeout de {membre.mention} a été retiré.", ephemeral=True)
        await self.log_action(interaction.guild, "🔊 Fin de timeout", f"Membre : {membre.mention}\nPar : {interaction.user.mention}", discord.Color.green(), INFRACTION_LOG_CHANNEL_ID)

    @app_commands.command(name="expulser", description="Expulser un membre du serveur.")
    @staff_check()
    async def expulser(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Non précisée"):
        if membre == interaction.user or membre.id == interaction.guild.owner_id or membre.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Cette action n'est pas autorisée sur ce membre.", ephemeral=True); return
        await membre.kick(reason=f"{raison} | par {interaction.user}")
        await interaction.response.send_message(f"{membre} a été expulsé. Motif : {raison}", ephemeral=True)
        await self.log_action(interaction.guild, "👢 Expulsion", f"Membre : {membre} (`{membre.id}`)\nMotif : {raison}\nPar : {interaction.user.mention}", channel_id=INFRACTION_LOG_CHANNEL_ID)

    @app_commands.command(name="bannir", description="Bannir un membre du serveur.")
    @staff_check()
    async def bannir(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Non précisée"):
        if membre == interaction.user or membre.id == interaction.guild.owner_id or membre.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Cette action n'est pas autorisée sur ce membre.", ephemeral=True); return
        if not hasattr(self.bot, "moderation_ban_ids"): self.bot.moderation_ban_ids = set()
        self.bot.moderation_ban_ids.add(membre.id)
        try:
            await membre.ban(reason=f"{raison} | par {interaction.user}", delete_message_seconds=0)
        except (discord.Forbidden, discord.HTTPException):
            self.bot.moderation_ban_ids.discard(membre.id)
            raise
        await interaction.response.send_message(f"{membre} a été banni. Motif : {raison}", ephemeral=True)
        await self.log_action(interaction.guild, "⛔ Bannissement", f"Membre : {membre} (`{membre.id}`)\nMotif : {raison}\nPar : {interaction.user.mention}", discord.Color.red(), INFRACTION_LOG_CHANNEL_ID)

    @app_commands.command(name="debannir", description="Débannir un utilisateur à partir de son identifiant.")
    @staff_check()
    async def debannir(self, interaction: discord.Interaction, utilisateur_id: str, raison: str = "Réexamen de la sanction"):
        try: uid = int(utilisateur_id)
        except ValueError: await interaction.response.send_message("Identifiant Discord invalide.", ephemeral=True); return
        user = await self.bot.fetch_user(uid)
        if not hasattr(self.bot, "moderation_unban_ids"): self.bot.moderation_unban_ids = set()
        self.bot.moderation_unban_ids.add(uid)
        try:
            await interaction.guild.unban(user, reason=f"{raison} | par {interaction.user}")
        except (discord.Forbidden, discord.HTTPException):
            self.bot.moderation_unban_ids.discard(uid)
            raise
        await interaction.response.send_message(f"{user} a été débanni.", ephemeral=True)
        await self.log_action(interaction.guild, "✅ Débannissement", f"Utilisateur : {user} (`{uid}`)\nMotif : {raison}\nPar : {interaction.user.mention}", discord.Color.green(), INFRACTION_LOG_CHANNEL_ID)

    @app_commands.command(name="purger", description="Supprimer un nombre de messages dans le salon actuel.")
    @staff_check()
    async def purger(self, interaction: discord.Interaction, nombre: app_commands.Range[int,1,100]):
        if not isinstance(interaction.channel, discord.TextChannel): await interaction.response.send_message("Commande utilisable dans un salon textuel.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=nombre, reason=f"Nettoyage par {interaction.user}")
        await interaction.followup.send(f"🧹 {len(deleted)} message(s) supprimé(s).", ephemeral=True)
        await self.log_action(interaction.guild, "🧹 Purge", f"{len(deleted)} message(s) supprimé(s) dans {interaction.channel.mention} par {interaction.user.mention}", channel_id=MESSAGE_LOG_CHANNEL_ID)

    @app_commands.command(name="note_membre", description="Ajouter une note interne de modération à un membre.")
    @staff_check()
    async def note_membre(self, interaction: discord.Interaction, membre: discord.Member, note: app_commands.Range[str,3,1000]):
        with db() as conn:
            conn.execute("INSERT INTO member_notes(guild_id,user_id,moderator_id,note,created_at) VALUES(?,?,?,?,?)", (interaction.guild_id,membre.id,interaction.user.id,note,datetime.now(timezone.utc).isoformat()))
        await interaction.response.send_message(f"Note interne enregistrée pour {membre.mention}.", ephemeral=True)
        await self.log_action(interaction.guild, "📝 Note interne", f"Membre : {membre.mention}\nNote : {note}\nPar : {interaction.user.mention}", channel_id=INFRACTION_LOG_CHANNEL_ID)

async def setup(bot: commands.Bot): await bot.add_cog(Moderation(bot))

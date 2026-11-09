"""Signalements, alertes internes et messages anonymes facultatifs."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, send_official_panel, edit_official_panel, wait_for_logo_ready
from datetime import datetime, timezone
import discord
from discord import app_commands
from discord.ext import commands
from config import ALERT_LOG_CHANNEL_ID, STAFF_ROLE_ID, ANONYMOUS_CHANNEL_ID, GUILD_ID
from .storage import db

class StaffTools(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Compteurs persistants : survivent aux redémarrages et aux déploiements.
        with db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS anonymous_rate_limits (
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_anonymous_rate ON anonymous_rate_limits(guild_id,user_id,created_at)")

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

    async def publish_anonymous(self, interaction: discord.Interaction, message: str):
        """Publication anonyme avec journal préalable obligatoire et anti-spam."""
        if not interaction.guild or interaction.guild.id != GUILD_ID:
            await interaction.response.send_message("Cette fonction est réservée à HORIZONS.", ephemeral=True)
            return
        channel = self.bot.get_channel(ANONYMOUS_CHANNEL_ID)
        staff_log = self.bot.get_channel(ALERT_LOG_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel) or not isinstance(staff_log, discord.TextChannel):
            await interaction.response.send_message("Publication indisponible : salon ou journal de modération inaccessible.", ephemeral=True)
            return
        if staff_log.permissions_for(interaction.guild.default_role).view_channel:
            await interaction.response.send_message("Publication indisponible : le journal de modération doit être privé.", ephemeral=True)
            return
        now = int(datetime.now(timezone.utc).timestamp())
        # Réserver une place atomiquement avant toute opération Discord.
        with db() as conn:
            conn.execute("DELETE FROM anonymous_rate_limits WHERE created_at <= ?", (now - 600,))
            recent = conn.execute("SELECT COUNT(*) FROM anonymous_rate_limits WHERE guild_id=? AND user_id=?", (interaction.guild.id, interaction.user.id)).fetchone()[0]
            if recent >= 2:
                await interaction.response.send_message("Limite atteinte : deux messages par période de dix minutes.", ephemeral=True)
                return
            conn.execute("INSERT INTO anonymous_rate_limits(guild_id,user_id,created_at) VALUES(?,?,?)", (interaction.guild.id, interaction.user.id, now))
        def release_reservation():
            with db() as conn:
                conn.execute("DELETE FROM anonymous_rate_limits WHERE rowid=(SELECT rowid FROM anonymous_rate_limits WHERE guild_id=? AND user_id=? AND created_at=? ORDER BY rowid DESC LIMIT 1)", (interaction.guild.id, interaction.user.id, now))
        await interaction.response.defer(ephemeral=True, thinking=True)
        audit = horizons_embed(title="🧾 Publication anonyme — journal confidentiel", description=message)
        audit.add_field(name="Auteur", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        audit.add_field(name="Destination", value=channel.mention, inline=True)
        audit.add_field(name="Horodatage UTC", value=datetime.now(timezone.utc).isoformat(), inline=False)
        try:
            audit_message = await staff_log.send(embed=audit, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException):
            release_reservation()
            await interaction.followup.send("Publication annulée : impossible de conserver le journal confidentiel.", ephemeral=True)
            return
        embed = horizons_embed(title="💌 Paroles libres", description=message)
        embed.set_footer(text="Message anonyme pour les membres • Auteur identifiable par la modération")
        try:
            published = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException):
            release_reservation()
            await interaction.followup.send("Publication impossible ; le journal interne a conservé la tentative.", ephemeral=True)
            return
        try:
            audit.add_field(name="Message publié", value=f"{published.jump_url} (`{published.id}`)", inline=False)
            await audit_message.edit(embed=audit)
        except (discord.Forbidden, discord.HTTPException):
            pass
        await interaction.followup.send("Ton message a été publié sans afficher ton identité aux membres. 💌", ephemeral=True)

    @app_commands.command(name="message_anonyme", description="Publier anonymement dans Paroles libres.")
    async def message_anonyme(self, interaction: discord.Interaction, message: app_commands.Range[str,5,1500]):
        await self.publish_anonymous(interaction, message)


class AnonymousModal(discord.ui.Modal, title="Écrire dans Paroles libres"):
    message = discord.ui.TextInput(label="Ton message", style=discord.TextStyle.paragraph,
                                   placeholder="Exprime-toi avec respect…", min_length=5, max_length=1500)

    def __init__(self, cog: StaffTools):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.publish_anonymous(interaction, str(self.message.value))


class AnonymousPanel(discord.ui.View):
    def __init__(self, cog: StaffTools):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Écrire anonymement", emoji="💌", style=discord.ButtonStyle.primary,
                       custom_id="horizons:anonymous:write:v1")
    async def write(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnonymousModal(self.cog))


class AnonymousPanelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.done = False

    @commands.Cog.listener()
    async def on_ready(self):
        if self.done:
            return
        cog = self.bot.get_cog("StaffTools")
        if cog is None:
            return
        self.bot.add_view(AnonymousPanel(cog))
        channel = self.bot.get_channel(ANONYMOUS_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        await wait_for_logo_ready()
        try:
            # Le panneau est recherché, puis modifié ; jamais dupliqué volontairement.
            async for msg in channel.history(limit=150):
                if msg.author.id != self.bot.user.id or not msg.embeds:
                    continue
                if any("Paroles libres — écrire anonymement" in (e.title or "") for e in msg.embeds):
                    await edit_official_panel(msg, embed=self.panel_embed(), view=AnonymousPanel(cog))
                    self.done = True
                    return
            await send_official_panel(channel, embed=self.panel_embed(), view=AnonymousPanel(cog))
            self.done = True
        except (discord.Forbidden, discord.HTTPException):
            pass

    @staticmethod
    def panel_embed():
        return horizons_embed(title="💌 Paroles libres — écrire anonymement",
            description="Un espace pour partager tes pensées sans afficher ton pseudo. "
                        "Clique sur **Écrire anonymement** pour ouvrir le formulaire privé.\n\n"
                        "**Confidentialité :** les membres ne voient pas ton identité, mais l'équipe "
                        "de modération conserve un journal associant ton compte au message, "
                        "afin de traiter les abus. Deux messages maximum toutes les dix minutes.\n\n"
                        "Pas d'insultes, de harcèlement ni d'informations personnelles concernant autrui.")

async def setup(bot: commands.Bot):
    await bot.add_cog(StaffTools(bot))
    await bot.add_cog(AnonymousPanelManager(bot))

"""Tickets privés HORIZONS avec commande slash et panneau permanent."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import STAFF_ROLE_ID, TICKET_CATEGORY_ID, TICKET_REQUEST_CHANNEL_ID
from .storage import db

log = logging.getLogger(__name__)


async def close_ticket(interaction: discord.Interaction, ticket_id: int):
    with db() as conn:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE id=? AND status='open'", (ticket_id,)
        ).fetchone()
        if not ticket:
            await interaction.response.send_message("Ce ticket est déjà fermé.", ephemeral=True)
            return
        is_staff = isinstance(interaction.user, discord.Member) and (
            interaction.user.guild_permissions.administrator
            or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles))
        )
        if interaction.user.id != ticket["opener_id"] and not is_staff:
            await interaction.response.send_message(
                "Seul l'auteur du ticket ou l'équipe peut le fermer.", ephemeral=True
            )
            return
        conn.execute(
            "UPDATE tickets SET status='closed',closed_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), ticket_id),
        )

    channel = interaction.guild.get_channel(ticket["channel_id"]) if interaction.guild else None
    if isinstance(channel, discord.TextChannel):
        opener = interaction.guild.get_member(ticket["opener_id"])
        if opener:
            try:
                await channel.set_permissions(opener, send_messages=False, reason="Ticket fermé")
            except discord.Forbidden:
                pass
        try:
            await channel.edit(name=f"ferme-{channel.name}"[:95], reason="Ticket fermé")
        except discord.HTTPException:
            pass
    await interaction.response.send_message(
        "🔒 Ticket fermé. Le salon est conservé pour l'historique de l'équipe.", ephemeral=True
    )


class TicketView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(
        label="Fermer le ticket", style=discord.ButtonStyle.danger,
        emoji="🔒", custom_id="horizons:ticket:close"
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await close_ticket(interaction, self.ticket_id)


class TicketOpenModal(discord.ui.Modal, title="Ouvrir un ticket HORIZONS"):
    sujet = discord.ui.TextInput(
        label="Sujet de ta demande", placeholder="Ex. : Besoin d'aide sur le serveur",
        min_length=3, max_length=80
    )
    details = discord.ui.TextInput(
        label="Explique ta demande", style=discord.TextStyle.paragraph,
        placeholder="Décris ce dont tu as besoin…", min_length=10, max_length=1500
    )

    def __init__(self, cog: "Tickets"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.create_ticket(interaction, str(self.sujet.value), str(self.details.value))


class TicketPanelView(discord.ui.View):
    def __init__(self, cog: "Tickets"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Créer un ticket", style=discord.ButtonStyle.primary,
        emoji="🎫", custom_id="horizons:ticket:open"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketOpenModal(self.cog))


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_ready = False

    async def cog_load(self):
        with db() as conn:
            rows = conn.execute(
                "SELECT id,message_id FROM tickets WHERE status='open' AND message_id IS NOT NULL"
            ).fetchall()
        for row in rows:
            self.bot.add_view(TicketView(row["id"]), message_id=row["message_id"])

    @commands.Cog.listener()
    async def on_ready(self):
        await wait_for_logo_ready()
        if self.panel_ready or not TICKET_REQUEST_CHANNEL_ID:
            return
        channel = self.bot.get_channel(TICKET_REQUEST_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(TICKET_REQUEST_CHANNEL_ID)
            except discord.HTTPException:
                log.exception("Salon de demande de tickets introuvable.")
                return
        if not isinstance(channel, discord.TextChannel):
            log.error("TICKET_REQUEST_CHANNEL_ID ne désigne pas un salon textuel.")
            return

        try:
            async for message in channel.history(limit=50):
                if message.author.id != self.bot.user.id:
                    continue
                if any(
                    embed.footer and embed.footer.text == "HORIZONS • Demande de ticket"
                    for embed in message.embeds
                ):
                    self.bot.add_view(TicketPanelView(self), message_id=message.id)
                    self.panel_ready = True
                    return
        except discord.Forbidden:
            log.warning("Impossible de vérifier l'ancien panneau : permission Lire l'historique manquante.")

        embed = horizons_embed(
            title="🎫 Besoin d'aide ?",
            description=(
                "Clique sur **Créer un ticket** pour contacter l'équipe HORIZONS en privé. "
                "Un salon réservé à toi et à l'équipe sera créé automatiquement."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Avant d'ouvrir un ticket",
            value="Explique clairement ta demande et évite de transmettre des informations personnelles sensibles.",
            inline=False,
        )
        embed.set_footer(text="HORIZONS • Demande de ticket")
        try:
            message = await channel.send(embed=embed, view=TicketPanelView(self))
            self.bot.add_view(TicketPanelView(self), message_id=message.id)
            self.panel_ready = True
        except discord.HTTPException:
            log.exception("Impossible de publier le panneau de tickets.")

    async def create_ticket(self, interaction: discord.Interaction, sujet: str, details: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            if interaction.response.is_done():
                await interaction.followup.send("Cette commande est disponible sur le serveur.", ephemeral=True)
            else:
                await interaction.response.send_message("Cette commande est disponible sur le serveur.", ephemeral=True)
            return

        with db() as conn:
            existing = conn.execute(
                "SELECT channel_id FROM tickets WHERE guild_id=? AND opener_id=? AND status='open'",
                (interaction.guild_id, interaction.user.id),
            ).fetchone()
        if existing:
            channel = interaction.guild.get_channel(existing["channel_id"])
            if channel:
                msg = f"Tu as déjà un ticket ouvert : {channel.mention}."
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
                return
            with db() as conn:
                conn.execute(
                    "UPDATE tickets SET status='closed',closed_at=? WHERE channel_id=?",
                    (datetime.now(timezone.utc).isoformat(), existing["channel_id"]),
                )

        category = interaction.guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
        if category and not isinstance(category, discord.CategoryChannel):
            category = None
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True
            ),
        }
        bot_member = interaction.guild.me
        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True
            )
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                manage_messages=True
            )

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        channel = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}"[:90], category=category,
            overwrites=overwrites,
            topic=f"Ticket privé HORIZONS • Ouvert par {interaction.user} ({interaction.user.id})",
        )
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO tickets(guild_id,channel_id,opener_id,subject,created_at) VALUES(?,?,?,?,?)",
                (interaction.guild_id, channel.id, interaction.user.id, sujet,
                 datetime.now(timezone.utc).isoformat()),
            )
            ticket_id = cur.lastrowid

        embed = horizons_embed(title=f"🎫 {sujet}", description=details, color=discord.Color.blurple())
        embed.add_field(name="Ouvert par", value=interaction.user.mention)
        embed.add_field(name="Référence", value=f"#{ticket_id}")
        embed.set_footer(text="HORIZONS • L'équipe te répondra dès que possible.")
        message = await channel.send(
            content=f"{interaction.user.mention}" + (f" <@&{STAFF_ROLE_ID}>" if STAFF_ROLE_ID else ""),
            embed=embed, view=TicketView(ticket_id),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True),
        )
        with db() as conn:
            conn.execute("UPDATE tickets SET message_id=? WHERE id=?", (message.id, ticket_id))
        self.bot.add_view(TicketView(ticket_id), message_id=message.id)
        await interaction.followup.send(f"Ton espace privé est prêt : {channel.mention}.", ephemeral=True)

    async def ticket_ouvrir(
        self, interaction: discord.Interaction,
        sujet: app_commands.Range[str, 3, 80],
        details: app_commands.Range[str, 10, 1500],
    ):
        await self.create_ticket(interaction, sujet, details)

    async def ticket_fermer(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Cette commande doit être utilisée dans un ticket.", ephemeral=True)
            return
        with db() as conn:
            row = conn.execute(
                "SELECT id FROM tickets WHERE channel_id=? AND status='open'",
                (interaction.channel.id,),
            ).fetchone()
        if not row:
            await interaction.response.send_message("Ce salon n'est pas un ticket ouvert.", ephemeral=True)
            return
        await close_ticket(interaction, row["id"])


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

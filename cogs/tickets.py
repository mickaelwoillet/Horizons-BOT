"""Tickets privés HORIZONS avec commande slash et panneau permanent."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

import logging
import io
import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import STAFF_ROLE_ID, TICKET_CATEGORY_ID, TICKET_REQUEST_CHANNEL_ID
from .storage import db

log = logging.getLogger(__name__)


TICKET_LOG_CHANNEL_ID = int(os.getenv("TICKET_LOG_CHANNEL_ID", "1568965253817962506") or 0)
_CLOSING_TICKETS: set[int] = set()


def _transcript_line(message: discord.Message) -> str:
    date = message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    parts = [f"[{date}] {message.author} (ID: {message.author.id}) | message {message.id}"]
    if message.content:
        parts.append(message.content)
    for attachment in message.attachments:
        parts.append(f"[PIÈCE JOINTE] {attachment.filename} | {attachment.url}")
    for embed in message.embeds:
        parts.append(f"[EMBED] Titre: {embed.title or '-'} | Description: {embed.description or '-'} | URL: {embed.url or '-'}")
        for field in embed.fields:
            parts.append(f"  {field.name}: {field.value}")
    if message.stickers:
        parts.extend(f"[STICKER] {sticker.name} ({sticker.id})" for sticker in message.stickers)
    if message.reference and message.reference.message_id:
        parts.append(f"[RÉPONSE À] {message.reference.message_id}")
    if message.edited_at:
        parts.append(f"[MODIFIÉ] {message.edited_at.isoformat()}")
    return "\n".join(parts) + "\n" + ("-" * 65) + "\n"


async def archive_ticket(interaction: discord.Interaction, ticket, channel: discord.TextChannel) -> bool:
    """Publie le transcript intégral avant la clôture. Ne ferme rien en cas d'échec."""
    guild = interaction.guild
    logs = guild.get_channel(TICKET_LOG_CHANNEL_ID) if guild else None
    if logs is None and guild and TICKET_LOG_CHANNEL_ID:
        try:
            logs = await guild.fetch_channel(TICKET_LOG_CHANNEL_ID)
        except discord.HTTPException:
            pass
    if not isinstance(logs, discord.TextChannel):
        log.error("Salon logs tickets introuvable : %s", TICKET_LOG_CHANNEL_ID)
        return False
    message_count = 0
    lines = [f"HORIZONS — ARCHIVE INTÉGRALE DU TICKET #{ticket['id']}",
             f"Sujet : {ticket['subject']}",
             f"Ouvert par : {ticket['opener_id']}",
             f"Responsable : {ticket['claimed_by'] if 'claimed_by' in ticket.keys() else '-'}",
             f"Ouvert le : {ticket['created_at']}",
             f"Fermé le : {datetime.now(timezone.utc).isoformat()}",
             f"Fermé par : {interaction.user} ({interaction.user.id})", "=" * 65]
    try:
        async for message in channel.history(limit=None, oldest_first=True):
            lines.append(_transcript_line(message))
            message_count += 1
    except (discord.HTTPException, discord.Forbidden):
        log.exception("Impossible de lire l'historique complet du ticket #%s", ticket['id'])
        return False
    text = "\n".join(lines).encode("utf-8")
    # Une archive de grande taille est découpée sans perte en fichiers successifs.
    chunk_size = 7_000_000
    # Ne jamais découper au milieu d'un caractère UTF-8 : les archives
    # comportent des accents et des emojis qui doivent rester lisibles.
    chunks = []
    offset = 0
    while offset < len(text):
        end = min(offset + chunk_size, len(text))
        if end < len(text):
            while end > offset and (text[end] & 0xC0) == 0x80:
                end -= 1
        if end <= offset:
            raise ValueError('Impossible de découper le transcript UTF-8')
        chunks.append(text[offset:end])
        offset = end
    uploaded_messages = []
    try:
        for idx, chunk in enumerate(chunks, 1):
            file = discord.File(io.BytesIO(chunk), filename=f"ticket-{ticket['id']}-partie-{idx}.txt")
            posted = await logs.send(
                content=(f"📁 **Archive du ticket #{ticket['id']}** — {ticket['subject']}\n"
                         f"Auteur : <@{ticket['opener_id']}> • Fermé par : {interaction.user.mention}\n"
                         f"Partie {idx}/{len(chunks)} • {message_count} messages") if idx == 1 else
                         f"📁 Ticket #{ticket['id']} — suite {idx}/{len(chunks)}",
                file=file,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            uploaded_messages.append(posted)
    except discord.HTTPException:
        log.exception("Échec de l'envoi de l'archive du ticket #%s", ticket['id'])
        # Une archive multipartielle incomplète ne doit pas rester présentée
        # comme une archive exploitable. Nettoyer les parties déjà envoyées.
        for posted in reversed(uploaded_messages):
            try:
                await posted.delete()
            except discord.HTTPException:
                log.warning("Archive ticket #%s : impossible de retirer la partie %s", ticket['id'], posted.id)
        return False
    return True


async def close_ticket(interaction: discord.Interaction, ticket_id: int):
    """Sérialise les clôtures pour ne pas envoyer plusieurs transcriptions."""
    if ticket_id in _CLOSING_TICKETS:
        await interaction.response.send_message(
            "Une clôture et son archivage sont déjà en cours pour ce ticket.", ephemeral=True
        )
        return
    _CLOSING_TICKETS.add(ticket_id)
    try:
        await _close_ticket_locked(interaction, ticket_id)
    finally:
        _CLOSING_TICKETS.discard(ticket_id)


async def _close_ticket_locked(interaction: discord.Interaction, ticket_id: int):
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
        claimed_by = ticket["claimed_by"] if "claimed_by" in ticket.keys() else None
        is_admin = isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.administrator
        is_owner = bool(interaction.guild and interaction.guild.owner_id == interaction.user.id)
        if interaction.user.id != ticket["opener_id"] and not is_admin and not is_owner:
            if claimed_by is not None and interaction.user.id != claimed_by:
                await interaction.response.send_message(
                    f"Ce ticket est pris en charge par <@{claimed_by}>. "
                    "Seul son responsable, son auteur ou un administrateur peut le fermer.", ephemeral=True
                )
                return
            if not is_staff:
                await interaction.response.send_message(
                    "Seul l'auteur du ticket ou l'équipe peut le fermer.", ephemeral=True
                )
                return

    channel = interaction.guild.get_channel(ticket["channel_id"]) if interaction.guild else None
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Salon du ticket introuvable : archivage impossible.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await archive_ticket(interaction, ticket, channel):
        await interaction.followup.send(
            "⚠️ L'archive intégrale n'a pas pu être envoyée dans logs-tickets. "
            "Le ticket reste ouvert pour éviter toute perte de conversation.", ephemeral=True)
        return
    with db() as conn:
        conn.execute("UPDATE tickets SET status='closed',closed_at=? WHERE id=? AND status='open'",
                     (datetime.now(timezone.utc).isoformat(), ticket_id))
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
    await interaction.followup.send(
        "🔒 Ticket fermé. Son historique complet a été archivé dans logs-tickets. "
        "Le salon reste conservé pour l'équipe.", ephemeral=True
    )


async def claim_ticket(interaction: discord.Interaction, ticket_id: int):
    """Attribution atomique : un seul membre de l'équipe peut prendre le ticket."""
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Action réservée au staff du serveur.", ephemeral=True)
        return
    is_staff = (interaction.guild.owner_id == interaction.user.id
                or interaction.user.guild_permissions.administrator
                or any(role.id == STAFF_ROLE_ID for role in interaction.user.roles))
    if not is_staff:
        await interaction.response.send_message("Seul le staff peut prendre en charge un ticket.", ephemeral=True)
        return
    with db() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id=? AND status='open'", (ticket_id,)).fetchone()
        if not ticket:
            await interaction.response.send_message("Ce ticket est fermé.", ephemeral=True)
            return
        changed = conn.execute(
            "UPDATE tickets SET claimed_by=? WHERE id=? AND status='open' AND claimed_by IS NULL",
            (interaction.user.id, ticket_id),
        ).rowcount
        owner = conn.execute("SELECT claimed_by FROM tickets WHERE id=?", (ticket_id,)).fetchone()[0]
    if not changed:
        await interaction.response.send_message(
            "Ce ticket est déjà attribué " + ("à toi." if owner == interaction.user.id else f"à <@{owner}>."),
            ephemeral=True,
        )
        return
    channel = interaction.guild.get_channel(ticket['channel_id'])
    if not isinstance(channel, discord.TextChannel):
        with db() as conn:
            conn.execute("UPDATE tickets SET claimed_by=NULL WHERE id=? AND claimed_by=?",
                         (ticket_id, interaction.user.id))
        await interaction.response.send_message("Salon du ticket introuvable : attribution annulée.", ephemeral=True)
        return
    if isinstance(channel, discord.TextChannel):
        try:
            staff_role = interaction.guild.get_role(STAFF_ROLE_ID) if STAFF_ROLE_ID else None
            if staff_role:
                await channel.set_permissions(staff_role, view_channel=True, read_message_history=True,
                                              send_messages=False, reason="Ticket attribué à un membre du staff")
            await channel.set_permissions(interaction.user, view_channel=True, send_messages=True,
                                          read_message_history=True, reason="Responsable du ticket")
            await channel.send(f"🛡️ Ticket pris en charge par {interaction.user.mention}. "
                               "Les autres membres du staff peuvent le consulter sans intervenir.",
                               allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            log.exception("Ticket #%s : permissions non mises à jour", ticket_id)
            # Une prise en charge n'est effective que si les permissions Discord ont été appliquées.
            with db() as conn:
                conn.execute("UPDATE tickets SET claimed_by=NULL WHERE id=? AND claimed_by=?",
                             (ticket_id, interaction.user.id))
            await interaction.response.send_message(
                "La prise en charge a échoué : permissions du salon non mises à jour. "
                "Le ticket reste disponible ; préviens le fondateur si le problème persiste.",
                ephemeral=True)
            return
    await interaction.response.send_message("✅ Tu es désormais responsable de ce ticket.", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    @discord.ui.button(label="Prendre en charge", style=discord.ButtonStyle.success,
                       emoji="🛡️", custom_id="horizons:ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await claim_ticket(interaction, self.ticket_id)

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
            columns = {row[1] for row in conn.execute("PRAGMA table_info(tickets)")}
            if "claimed_by" not in columns:
                conn.execute("ALTER TABLE tickets ADD COLUMN claimed_by INTEGER")
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
            async for message in channel.history(limit=None):
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
            log.warning("Impossible de vérifier l'ancien panneau : permission Lire l'historique manquante. Aucune création automatique pour éviter un doublon.")
            return
        except discord.HTTPException:
            log.exception("Impossible de parcourir l'historique du panneau de tickets. Création reportée pour éviter un doublon.")
            return

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

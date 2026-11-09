"""Événements communautaires avec inscriptions persistantes."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import LOCAL_TIMEZONE, STAFF_ROLE_ID, ANIMATOR_ROLE_ID, AGENDA_CHANNEL_ID
from .storage import db
from .sky_map import grant as grant_sky_star
import logging

log = logging.getLogger(__name__)

class EventRSVPView(discord.ui.View):
    def __init__(self, event_id: int):
        super().__init__(timeout=None)
        self.event_id = event_id

    async def _respond(self, interaction: discord.Interaction, response: str):
        with db() as conn:
            event = conn.execute("SELECT status FROM events WHERE id=?", (self.event_id,)).fetchone()
            if not event or event["status"] != "open":
                await interaction.response.send_message("Les inscriptions à cet événement sont fermées.", ephemeral=True); return
            conn.execute("INSERT INTO event_rsvps(event_id,user_id,response,created_at) VALUES(?,?,?,?) ON CONFLICT(event_id,user_id) DO UPDATE SET response=excluded.response,created_at=excluded.created_at", (self.event_id,interaction.user.id,response,discord.utils.utcnow().isoformat()))
        await interaction.response.send_message("Ta réponse a été enregistrée. Tu peux la modifier en cliquant sur l'autre bouton.", ephemeral=True)

    @discord.ui.button(label="Je participe", style=discord.ButtonStyle.success, emoji="🙋", custom_id="horizons:event:yes")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button): await self._respond(interaction, "yes")

    @discord.ui.button(label="Peut-être", style=discord.ButtonStyle.secondary, emoji="🤔", custom_id="horizons:event:maybe")
    async def maybe(self, interaction: discord.Interaction, button: discord.ui.Button): await self._respond(interaction, "maybe")

    @discord.ui.button(label="Je ne participe plus", style=discord.ButtonStyle.danger, emoji="✖️", custom_id="horizons:event:no")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        with db() as conn: conn.execute("DELETE FROM event_rsvps WHERE event_id=? AND user_id=?", (self.event_id,interaction.user.id))
        await interaction.response.send_message("Ton inscription a été retirée.", ephemeral=True)

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.event_reminders.start()

    def cog_unload(self):
        self.event_reminders.cancel()

    async def cog_load(self):
        with db() as conn: rows = conn.execute("SELECT id,message_id FROM events WHERE status='open' AND message_id IS NOT NULL").fetchall()
        for row in rows:
            self.bot.add_view(EventRSVPView(row["id"]), message_id=row["message_id"])

    @app_commands.command(name="evenement_creer", description="Créer un rendez-vous communautaire HORIZONS.")
    @app_commands.describe(date_heure="Format JJ/MM/AAAA HH:MM, heure de Paris", salon="Salon de publication (Agenda par défaut)")
    async def evenement_creer(self, interaction: discord.Interaction, titre: app_commands.Range[str,3,100], date_heure: str, description: app_commands.Range[str,5,1800], lieu: str = "En ligne / à préciser", salon: discord.TextChannel | None = None):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (member.guild_permissions.administrator or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles)) or (ANIMATOR_ROLE_ID and any(r.id == ANIMATOR_ROLE_ID for r in member.roles)))
        if not allowed:
            await interaction.response.send_message("Cette commande est réservée à l'équipe et aux animateurs HORIZONS.", ephemeral=True); return
        if salon is None:
            salon = interaction.guild.get_channel(AGENDA_CHANNEL_ID) if interaction.guild else None
            if salon is None:
                try:
                    salon = await self.bot.fetch_channel(AGENDA_CHANNEL_ID)
                except discord.HTTPException:
                    salon = None
        if not isinstance(salon, discord.TextChannel):
            await interaction.response.send_message("Je ne trouve pas le salon Agenda. Vérifie son identifiant et les permissions du bot.", ephemeral=True); return
        try: starts = datetime.strptime(date_heure, "%d/%m/%Y %H:%M").replace(tzinfo=LOCAL_TIMEZONE)
        except ValueError:
            await interaction.response.send_message("Format invalide. Exemple : `25/11/2026 18:30`.", ephemeral=True); return
        if starts <= discord.utils.utcnow().astimezone(LOCAL_TIMEZONE):
            await interaction.response.send_message("La date doit être située dans le futur.", ephemeral=True); return
        with db() as conn:
            cur = conn.execute("INSERT INTO events(guild_id,channel_id,creator_id,title,description,starts_at,location,created_at) VALUES(?,?,?,?,?,?,?,?)", (interaction.guild_id,salon.id,interaction.user.id,titre,description,starts.isoformat(),lieu,discord.utils.utcnow().isoformat()))
            event_id = cur.lastrowid
        embed = horizons_embed(title=f"📅 {titre}", description=description, color=discord.Color.blurple())
        embed.add_field(name="Date", value=discord.utils.format_dt(starts, style="F"), inline=False)
        embed.add_field(name="Lieu", value=lieu, inline=False)
        embed.add_field(name="Organisé par", value=interaction.user.mention)
        embed.set_footer(text=f"HORIZONS • Événement #{event_id} • Indique ta présence ci-dessous")
        await interaction.response.defer(ephemeral=True)
        message = await salon.send(embed=embed, view=EventRSVPView(event_id))
        with db() as conn: conn.execute("UPDATE events SET message_id=? WHERE id=?", (message.id,event_id))
        self.bot.add_view(EventRSVPView(event_id), message_id=message.id)
        await interaction.followup.send(f"Événement publié dans {salon.mention}.", ephemeral=True)

    @app_commands.command(name="evenements", description="Afficher les prochains événements HORIZONS.")
    async def evenements(self, interaction: discord.Interaction):
        with db() as conn:
            rows = conn.execute("SELECT id,title,starts_at,location,channel_id FROM events WHERE guild_id=? AND status='open' ORDER BY starts_at LIMIT 10", (interaction.guild_id,)).fetchall()
        if not rows: await interaction.response.send_message("Aucun événement à venir n'est actuellement programmé.", ephemeral=True); return
        embed = horizons_embed(title="📅 Les prochains rendez-vous", color=discord.Color.blurple())
        for row in rows:
            try: dt = datetime.fromisoformat(row["starts_at"])
            except ValueError: dt = None
            date = discord.utils.format_dt(dt, style="F") if dt else row["starts_at"]
            channel = interaction.guild.get_channel(row["channel_id"])
            embed.add_field(name=f"#{row['id']} — {row['title']}", value=f"{date}\n{row['location']}\n{channel.mention if channel else 'Salon indisponible'}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="evenement_fermer", description="Fermer les inscriptions d'un événement.")
    async def evenement_fermer(self, interaction: discord.Interaction, numero: app_commands.Range[int,1,999999]):
        with db() as conn:
            row = conn.execute("SELECT message_id,channel_id,creator_id FROM events WHERE id=? AND guild_id=? AND status='open'", (numero,interaction.guild_id)).fetchone()
            if not row: await interaction.response.send_message("Événement ouvert introuvable.", ephemeral=True); return
            is_staff = isinstance(interaction.user, discord.Member) and (interaction.user.guild_permissions.administrator or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles)))
            if row["creator_id"] != interaction.user.id and not is_staff:
                await interaction.response.send_message("Seul le créateur ou l'équipe peut fermer cet événement.", ephemeral=True); return
            conn.execute("UPDATE events SET status='closed' WHERE id=?", (numero,))
        channel = interaction.guild.get_channel(row["channel_id"])
        if channel and row["message_id"]:
            try:
                msg = await channel.fetch_message(row["message_id"])
                await msg.edit(view=None)
            except discord.HTTPException: pass
        await interaction.response.send_message(f"Les inscriptions à l'événement **#{numero}** sont fermées.", ephemeral=True)

    @app_commands.command(name="evenement_presence", description="Confirmer la présence réelle à un événement terminé.")
    @app_commands.describe(numero="Numéro de l'événement", membre="Membre réellement présent")
    async def evenement_presence(self, interaction: discord.Interaction, numero: app_commands.Range[int, 1, 999999], membre: discord.Member):
        if interaction.guild_id is None:
            await interaction.response.send_message("Cette commande est réservée au serveur.", ephemeral=True)
            return
        with db() as conn:
            event = conn.execute(
                "SELECT creator_id,starts_at,title FROM events WHERE id=? AND guild_id=?",
                (numero, interaction.guild_id),
            ).fetchone()
            if not event:
                await interaction.response.send_message("Événement introuvable.", ephemeral=True)
                return
            is_staff = isinstance(interaction.user, discord.Member) and (
                interaction.user.guild_permissions.administrator
                or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in interaction.user.roles))
            )
            if event["creator_id"] != interaction.user.id and not is_staff:
                await interaction.response.send_message("Seul l'organisateur ou le staff peut confirmer une présence.", ephemeral=True)
                return
            try:
                starts_at = datetime.fromisoformat(event["starts_at"])
                if starts_at.tzinfo is None:
                    starts_at = starts_at.replace(tzinfo=LOCAL_TIMEZONE)
            except (TypeError, ValueError):
                await interaction.response.send_message("Date de l'événement invalide.", ephemeral=True)
                return
            if starts_at > datetime.now(timezone.utc):
                await interaction.response.send_message("La présence ne peut être confirmée avant le début de l'événement.", ephemeral=True)
                return
            rsvp = conn.execute(
                "SELECT response FROM event_rsvps WHERE event_id=? AND user_id=?",
                (numero, membre.id),
            ).fetchone()
            if not rsvp or rsvp["response"] != "yes":
                await interaction.response.send_message("Ce membre n'est pas inscrit comme participant à cet événement.", ephemeral=True)
                return
            inserted = conn.execute(
                "INSERT OR IGNORE INTO event_attendance(event_id,user_id,confirmed_by,confirmed_at) VALUES(?,?,?,?)",
                (numero, membre.id, interaction.user.id, discord.utils.utcnow().isoformat()),
            ).rowcount
        if not inserted:
            await interaction.response.send_message("Cette présence a déjà été confirmée.", ephemeral=True)
            return
        # Une présence confirmée (et non une inscription) débloque Main Tendue.
        # Le journal métier est conservé même si l'attribution de l'étoile échoue.
        new_star = False
        try:
            new_star = grant_sky_star(interaction.guild_id, membre.id, "origins.activity")
        except Exception:
            log.exception("Échec de l'attribution Main Tendue pour %s", membre.id)
        message = f"Présence de {membre.display_name} confirmée pour **{event['title']}**."
        if new_star:
            message += " ✦ L'étoile **Main Tendue** vient d'être débloquée dans sa Carte du Ciel !"
        await interaction.response.send_message(
            message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @tasks.loop(minutes=5)
    async def event_reminders(self):
        now = datetime.now(timezone.utc)
        for reminder_type, delta in (("24h", timedelta(hours=24)), ("1h", timedelta(hours=1))):
            with db() as conn:
                candidates = conn.execute(
                    "SELECT id,title,starts_at,location FROM events WHERE status='open'"
                ).fetchall()
            events = []
            for candidate in candidates:
                try:
                    starts_at = datetime.fromisoformat(candidate["starts_at"]).astimezone(timezone.utc)
                except (TypeError, ValueError):
                    continue
                if now + delta < starts_at <= now + delta + timedelta(minutes=5):
                    events.append(candidate)
            for event in events:
                with db() as conn:
                    attendees = conn.execute(
                        "SELECT user_id FROM event_rsvps WHERE event_id=? AND response='yes'",
                        (event["id"],),
                    ).fetchall()
                for attendee in attendees:
                    user_id = int(attendee["user_id"])
                    with db() as conn:
                        inserted = conn.execute(
                            "INSERT OR IGNORE INTO event_reminders(event_id,user_id,reminder_type,sent_at) VALUES(?,?,?,?)",
                            (event["id"], user_id, reminder_type, now.isoformat()),
                        ).rowcount
                    if not inserted:
                        continue
                    try:
                        user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                        when = datetime.fromisoformat(event["starts_at"])
                        await user.send(
                            f"⏰ Petit rappel HORIZONS : **{event['title']}** commence dans "
                            f"{'24 heures' if reminder_type == '24h' else '1 heure'} "
                            f"({discord.utils.format_dt(when, style='F')}).\nLieu : {event['location']}"
                        )
                    except (discord.Forbidden, discord.HTTPException):
                        pass

    @event_reminders.before_loop
    async def before_event_reminders(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot): await bot.add_cog(Events(bot))

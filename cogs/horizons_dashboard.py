"""Tableau de bord analytique HORIZONS — statistiques collectives réservées au staff."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import DATA_DIR, GUILD_ID, LOCAL_TIMEZONE
from cogs.embed_theme import horizons_embed
from .staff_dashboard import access_level
from .storage import db

log = logging.getLogger(__name__)

SECTIONS = {
    "overview": "📊 Vue générale",
    "activity": "💬 Activité communautaire",
    "community": "💜 Vie communautaire",
    "animations": "🎉 Animations et expériences",
    "publications": "📣 Publications automatiques",
    "technical": "⚙️ État technique",
}
PERIODS = {
    "compare": "Comparaison 7 / 30 jours",
    "7": "7 derniers jours",
    "30": "30 derniers jours",
}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _period_bounds(days: int) -> tuple[str, str, str, str]:
    today = datetime.now(timezone.utc).date()
    current_start = today - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return current_start.isoformat(), today.isoformat(), previous_start.isoformat(), previous_end.isoformat()


def _read_json(filename: str) -> dict:
    try:
        value = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _count(conn, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def _range_count(conn, table: str, date_column: str, guild_id: int, start: str, end: str, extra: str = "", extra_params: tuple = ()) -> int:
    # table/date_column/extra sont des constantes internes au module, jamais des entrées utilisateur.
    sql = f"SELECT COUNT(*) FROM {table} WHERE guild_id=? AND substr({date_column},1,10) BETWEEN ? AND ? {extra}"
    return _count(conn, sql, (guild_id, start, end, *extra_params))


def _next_weekday(hour: int, minute: int, weekdays: tuple[int, ...] | None = None) -> datetime:
    now = datetime.now(LOCAL_TIMEZONE)
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for offset in range(8):
        current = candidate + timedelta(days=offset)
        if (weekdays is None or current.weekday() in weekdays) and current > now:
            return current
    return candidate + timedelta(days=7)


def _fmt_next(hour: int, minute: int, weekdays: tuple[int, ...] | None = None) -> str:
    return _next_weekday(hour, minute, weekdays).strftime("%a. %d/%m à %H:%M")


def _fmt_date(value: str | None) -> str:
    if not value:
        return "Pas encore enregistrée"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(LOCAL_TIMEZONE).strftime("%d/%m/%Y à %H:%M")
    except (ValueError, TypeError):
        return str(value)[:40]


class DashboardView(discord.ui.View):
    def __init__(self, cog: "HorizonsDashboard", user_id: int, section: str = "overview", period: str = "compare"):
        super().__init__(timeout=900)
        self.cog = cog
        self.user_id = user_id
        self.section = section
        self.period = period
        self.add_item(SectionSelect(section))
        self.add_item(PeriodSelect(period))
        self.add_item(RefreshButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce tableau de bord appartient à un autre membre du staff.", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("L'accès au tableau de bord est réservé au staff autorisé.", ephemeral=True)
            return False
        return True

    async def refresh(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Cette commande doit être utilisée sur HORIZONS.", ephemeral=True)
            return
        embed = self.cog.build_embed(interaction.guild, self.section, self.period)
        await interaction.response.edit_message(embed=embed, view=DashboardView(self.cog, self.user_id, self.section, self.period))


class SectionSelect(discord.ui.Select):
    def __init__(self, selected: str):
        options = [discord.SelectOption(label=label, value=key, default=(key == selected)) for key, label in SECTIONS.items()]
        super().__init__(placeholder="Choisir une rubrique", min_values=1, max_values=1, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        view: DashboardView = self.view
        view.section = self.values[0]
        await view.refresh(interaction)


class PeriodSelect(discord.ui.Select):
    def __init__(self, selected: str):
        options = [discord.SelectOption(label=label, value=key, default=(key == selected)) for key, label in PERIODS.items()]
        super().__init__(placeholder="Période d'analyse", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        view: DashboardView = self.view
        view.period = self.values[0]
        await view.refresh(interaction)


class RefreshButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Actualiser", emoji="🔄", style=discord.ButtonStyle.primary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await self.view.refresh(interaction)


class HorizonsDashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_snapshot.start()

    def cog_unload(self):
        self.daily_snapshot.cancel()

    async def cog_load(self):
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO horizons_dashboard_meta(key,value) VALUES('tracking_started_at',?)",
                (datetime.now(timezone.utc).isoformat(),),
            )

    @commands.Cog.listener()
    async def on_ready(self):
        guild = self.bot.get_guild(GUILD_ID) if GUILD_ID else None
        if guild:
            self._save_member_snapshot(guild)

    @tasks.loop(time=time(hour=2, minute=10, tzinfo=LOCAL_TIMEZONE))
    async def daily_snapshot(self):
        guild = self.bot.get_guild(GUILD_ID) if GUILD_ID else None
        if guild:
            self._save_member_snapshot(guild)

    @daily_snapshot.before_loop
    async def before_daily_snapshot(self):
        await self.bot.wait_until_ready()

    def _save_member_snapshot(self, guild: discord.Guild) -> None:
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO horizons_dashboard_member_daily(guild_id,activity_date,member_count) VALUES(?,?,?) "
                    "ON CONFLICT(guild_id,activity_date) DO UPDATE SET member_count=excluded.member_count",
                    (guild.id, _today(), int(guild.member_count or 0)),
                )
        except Exception:
            log.exception("Impossible d'enregistrer le relevé quotidien des membres HORIZONS.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            self._record_membership_change(member.guild, joins=1)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.bot:
            self._record_membership_change(member.guild, leaves=1)

    def _record_membership_change(self, guild: discord.Guild, *, joins: int = 0, leaves: int = 0) -> None:
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO horizons_dashboard_member_daily(guild_id,activity_date,joins,leaves,member_count) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(guild_id,activity_date) DO UPDATE SET joins=joins+excluded.joins, leaves=leaves+excluded.leaves, member_count=excluded.member_count",
                    (guild.id, _today(), joins, leaves, int(guild.member_count or 0)),
                )
        except Exception:
            log.exception("Impossible d'enregistrer un mouvement de membres HORIZONS.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot or message.webhook_id:
            return
        if not (message.content.strip() or message.attachments or message.stickers):
            return
        channel = message.channel
        parent = getattr(channel, "parent", None)
        permission_channel = parent or channel
        if getattr(channel, "type", None) == discord.ChannelType.private_thread:
            return
        try:
            if not permission_channel.permissions_for(message.guild.default_role).view_channel:
                return
        except AttributeError:
            return
        category_name = (getattr(getattr(permission_channel, "category", None), "name", "") or "").casefold()
        channel_name = (getattr(permission_channel, "name", "") or "").casefold()
        if any(term in category_name or term in channel_name for term in ("staff", "journal technique", "logs", "modération")):
            return
        try:
            with db() as conn:
                conn.execute(
                    "INSERT INTO horizons_dashboard_message_daily(guild_id,activity_date,channel_id,message_count) VALUES(?,?,?,1) "
                    "ON CONFLICT(guild_id,activity_date,channel_id) DO UPDATE SET message_count=message_count+1",
                    (message.guild.id, _today(), permission_channel.id),
                )
        except Exception:
            log.exception("Impossible d'enregistrer l'activité agrégée HORIZONS.")

    def _message_stats(self, guild_id: int, days: int) -> tuple[int, int, list[tuple[int, int]]]:
        start, end, prev_start, prev_end = _period_bounds(days)
        with db() as conn:
            current = _count(conn, "SELECT COALESCE(SUM(message_count),0) FROM horizons_dashboard_message_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, start, end))
            previous = _count(conn, "SELECT COALESCE(SUM(message_count),0) FROM horizons_dashboard_message_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, prev_start, prev_end))
            top = conn.execute(
                "SELECT channel_id,SUM(message_count) total FROM horizons_dashboard_message_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ? GROUP BY channel_id ORDER BY total DESC LIMIT 5",
                (guild_id, start, end),
            ).fetchall()
            return current, previous, [(int(row[0]), int(row[1])) for row in top]

    def _active_members(self, guild_id: int, days: int) -> tuple[int, int]:
        start, end, prev_start, prev_end = _period_bounds(days)
        with db() as conn:
            current = _count(conn, "SELECT COUNT(DISTINCT user_id) FROM activity_days WHERE guild_id=? AND active_date BETWEEN ? AND ?", (guild_id, start, end))
            previous = _count(conn, "SELECT COUNT(DISTINCT user_id) FROM activity_days WHERE guild_id=? AND active_date BETWEEN ? AND ?", (guild_id, prev_start, prev_end))
        return current, previous

    def _member_stats(self, guild_id: int, days: int) -> tuple[int, int, int, int]:
        start, end, prev_start, prev_end = _period_bounds(days)
        with db() as conn:
            joins = _count(conn, "SELECT COALESCE(SUM(joins),0) FROM horizons_dashboard_member_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, start, end))
            leaves = _count(conn, "SELECT COALESCE(SUM(leaves),0) FROM horizons_dashboard_member_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, start, end))
            old_joins = _count(conn, "SELECT COALESCE(SUM(joins),0) FROM horizons_dashboard_member_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, prev_start, prev_end))
            old_leaves = _count(conn, "SELECT COALESCE(SUM(leaves),0) FROM horizons_dashboard_member_daily WHERE guild_id=? AND activity_date BETWEEN ? AND ?", (guild_id, prev_start, prev_end))
        return joins, leaves, old_joins, old_leaves

    def _window_text(self, current: int, previous: int, days: int, unit: str) -> str:
        if self._tracking_days() < days * 2:
            return f"**{current}** {unit} · période précédente : données encore en constitution"
        delta = current - previous
        sign = "+" if delta > 0 else ""
        return f"**{current}** {unit} · période précédente : **{previous}** · évolution : `{sign}{delta}`"

    def _tracking_days(self) -> int:
        with db() as conn:
            row = conn.execute("SELECT value FROM horizons_dashboard_meta WHERE key='tracking_started_at'").fetchone()
        if not row:
            return 0
        try:
            started = datetime.fromisoformat(row[0]).date()
            return max(0, (datetime.now(timezone.utc).date() - started).days + 1)
        except (ValueError, TypeError):
            return 0

    def build_embed(self, guild: discord.Guild, section: str, period: str) -> discord.Embed:
        if section == "overview":
            e = horizons_embed(title="📊 HORIZONS — Vue générale", description="Indicateurs collectifs de la communauté. Aucune statistique individuelle n'est affichée.", color=discord.Color.blurple())
            e.add_field(name="Comptes actuellement présents", value=f"**{guild.member_count or 0}**", inline=True)
            tracking = self._tracking_days()
            e.add_field(name="Collecte du tableau de bord", value=f"Depuis **{tracking} jour(s)**", inline=True)
            for days in self._selected_days(period):
                messages, old_messages, _ = self._message_stats(guild.id, days)
                active, old_active = self._active_members(guild.id, days)
                joins, leaves, old_joins, old_leaves = self._member_stats(guild.id, days)
                e.add_field(name=f"📆 {days} derniers jours", value=(
                    f"Messages : **{messages}** (période précédente : {old_messages if tracking >= days * 2 else 'en constitution'})\n"
                    f"Membres actifs : **{active}** (période précédente : {old_active if tracking >= days * 2 else 'en constitution'})\n"
                    f"Arrivées : **{joins}** · Départs : **{leaves}** · Solde : **{joins-leaves:+d}**\n"
                    f"Mouvements période précédente : {f'{old_joins} arrivée(s) / {old_leaves} départ(s)' if tracking >= days * 2 else 'en constitution'}"
                ), inline=False)
            e.set_footer(text="HORIZONS • Vue collective • Fuseau de référence des statistiques : UTC")
            return e

        if section == "activity":
            e = horizons_embed(title="💬 HORIZONS — Activité communautaire", description="Messages comptabilisés dans les salons visibles par tous. Les messages privés et espaces staff sont exclus.", color=discord.Color.teal())
            for days in self._selected_days(period):
                messages, previous, top = self._message_stats(guild.id, days)
                active, old_active = self._active_members(guild.id, days)
                active_text = f"Membres actifs suivis : **{active}**"
                if self._tracking_days() >= days * 2:
                    active_text += f" (période précédente : {old_active})"
                e.add_field(name=f"Sur {days} jours", value=self._window_text(messages, previous, days, "messages") + f"\n{active_text}", inline=False)
                if days == self._selected_days(period)[0]:
                    lines = []
                    for channel_id, total in top:
                        channel = guild.get_channel_or_thread(channel_id)
                        if channel:
                            lines.append(f"{channel.mention} — **{total}**")
                    e.add_field(name="Salons les plus actifs", value="\n".join(lines) or "Les premières données sont en cours de collecte.", inline=False)
            e.set_footer(text="Membre actif = activité enregistrée par le parcours HORIZONS (message d'au moins 25 caractères).")
            return e

        if section == "community":
            e = horizons_embed(title="💜 HORIZONS — Vie communautaire", description="Participations et initiatives enregistrées dans les outils HORIZONS.", color=discord.Color.magenta())
            for days in self._selected_days(period):
                start, end, prev_start, prev_end = _period_bounds(days)
                with db() as conn:
                    missions = _range_count(conn, "passport_completions", "completed_at", guild.id, start, end)
                    missions_old = _range_count(conn, "passport_completions", "completed_at", guild.id, prev_start, prev_end)
                    interests = _count(conn, "SELECT COUNT(*) FROM activity_request_interests i JOIN activity_requests r ON r.id=i.request_id WHERE r.guild_id=? AND substr(i.created_at,1,10) BETWEEN ? AND ?", (guild.id, start, end))
                    interests_old = _count(conn, "SELECT COUNT(*) FROM activity_request_interests i JOIN activity_requests r ON r.id=i.request_id WHERE r.guild_id=? AND substr(i.created_at,1,10) BETWEEN ? AND ?", (guild.id, prev_start, prev_end))
                    ideas = _range_count(conn, "community_ideas", "created_at", guild.id, start, end)
                    ideas_old = _range_count(conn, "community_ideas", "created_at", guild.id, prev_start, prev_end)
                    thanks = _range_count(conn, "solidarity_thanks", "created_at", guild.id, start, end)
                    thanks_old = _range_count(conn, "solidarity_thanks", "created_at", guild.id, prev_start, prev_end)
                e.add_field(name=f"Sur {days} jours · période précédente entre parenthèses", value=f"Missions validées : **{missions}** ({missions_old})\nIntérêts pour une activité : **{interests}** ({interests_old})\nSuggestions déposées : **{ideas}** ({ideas_old})\nRemerciements solidaires : **{thanks}** ({thanks_old})", inline=False)
            e.set_footer(text="Données agrégées issues des fonctionnalités existantes du bot.")
            return e

        if section == "animations":
            e = horizons_embed(title="🎉 HORIZONS — Animations et expériences", description="Suivi des rendez-vous et participations enregistrées.", color=discord.Color.gold())
            for days in self._selected_days(period):
                start, end, prev_start, prev_end = _period_bounds(days)
                with db() as conn:
                    missions = _range_count(conn, "passport_completions", "completed_at", guild.id, start, end)
                    missions_old = _range_count(conn, "passport_completions", "completed_at", guild.id, prev_start, prev_end)
                    challenge_joins = _count(conn, "SELECT COUNT(*) FROM collective_challenge_members m JOIN collective_challenges c ON c.id=m.challenge_id WHERE c.guild_id=? AND substr(m.joined_at,1,10) BETWEEN ? AND ?", (guild.id, start, end))
                    challenge_old = _count(conn, "SELECT COUNT(*) FROM collective_challenge_members m JOIN collective_challenges c ON c.id=m.challenge_id WHERE c.guild_id=? AND substr(m.joined_at,1,10) BETWEEN ? AND ?", (guild.id, prev_start, prev_end))
                    event_rsvps = _count(conn, "SELECT COUNT(*) FROM event_rsvps r JOIN events e ON e.id=r.event_id WHERE e.guild_id=? AND substr(r.created_at,1,10) BETWEEN ? AND ?", (guild.id, start, end))
                    event_rsvps_old = _count(conn, "SELECT COUNT(*) FROM event_rsvps r JOIN events e ON e.id=r.event_id WHERE e.guild_id=? AND substr(r.created_at,1,10) BETWEEN ? AND ?", (guild.id, prev_start, prev_end))
                    events = _range_count(conn, "events", "created_at", guild.id, start, end)
                    events_old = _range_count(conn, "events", "created_at", guild.id, prev_start, prev_end)
                e.add_field(name=f"Sur {days} jours · période précédente entre parenthèses", value=f"Missions validées : **{missions}** ({missions_old})\nParticipations aux défis collectifs : **{challenge_joins}** ({challenge_old})\nRéponses aux événements : **{event_rsvps}** ({event_rsvps_old})\nÉvénements créés : **{events}** ({events_old})", inline=False)
            e.set_footer(text="Une participation peut être comptabilisée à nouveau si elle concerne une activité différente.")
            return e

        if section == "publications":
            e = horizons_embed(title="📣 HORIZONS — Publications automatiques", description="État des extensions, derniers succès enregistrés et prochains passages programmés.", color=discord.Color.blurple())
            states = {
                "horizons_daily": _read_json("horizons_publications_history.json"),
                "calendar": _read_json("publication_calendar_history.json"),
                "weekly": _read_json("weekly_animations_history.json"),
            }
            tasks_info = [
                ("Horizon du jour", "HorizonsDaily", "horizon_of_day", "horizons_daily", 9, 30, None),
                ("Débat hebdomadaire", "HorizonsDaily", "weekly_debate", "horizons_debate", 19, 30, (6,)),
                ("Événement thématique (si date concernée)", "PublicationCalendar", "daily_thematic_event", "calendar", 8, 0, None),
                ("Quiz éditorial", "PublicationCalendar", "daily_quiz", "calendar", 13, 30, (0, 2, 5)),
                ("Inspiration du soir", "PublicationCalendar", "daily_inspiration", "calendar", 19, 30, (0, 2, 5)),
                ("Message bienveillant", "PublicationCalendar", "daily_positive_message", "calendar", 21, 30, (1, 3, 6)),
                ("Animation collective", "WeeklyAnimations", "friday_animation", "weekly_animations", 19, 30, (4,)),
            ]
            for label, cog_name, loop_name, state_key, hour, minute, weekdays in tasks_info:
                cog = self.bot.get_cog(cog_name)
                loop = getattr(cog, loop_name, None) if cog else None
                running = bool(loop and loop.is_running())
                if state_key == "horizons_daily":
                    last = states["horizons_daily"].get("published_horizon_date")
                elif state_key == "horizons_debate":
                    last = states["horizons_daily"].get("published_debate_week")
                elif state_key == "weekly_animations":
                    last = states["weekly"].get("published_at")
                else:
                    dates = states["calendar"].get("published_dates", {})
                    last = max(dates.values()) if dates else None
                status = "🟢 tâche active" if running else "🔴 tâche non active"
                next_run = _fmt_next(hour, minute, weekdays) if running else "Non programmée"
                e.add_field(name=label, value=f"{status}\nDernière réussite : `{last or 'Aucune enregistrée'}`\nProchain passage prévu : **{next_run}**", inline=False)
            e.set_footer(text="Une tâche active confirme son chargement, pas la réussite d'une publication future. Les erreurs restent consultables dans les journaux du bot.")
            return e

        e = horizons_embed(title="⚙️ HORIZONS — État technique", description="Contrôle des extensions utiles au fonctionnement du serveur.", color=discord.Color.dark_teal())
        extensions = [
            ("Publications quotidiennes", "cogs.horizons_daily"),
            ("Calendrier éditorial", "cogs.publication_calendar"),
            ("Animations hebdomadaires", "cogs.weekly_animations"),
            ("Activité et rangs", "cogs.community_ranks"),
            ("Expériences", "cogs.experiences"),
            ("Communauté", "cogs.community_hub"),
        ]
        for label, extension in extensions:
            loaded = extension in self.bot.extensions
            e.add_field(name=label, value="🟢 Chargée" if loaded else "🔴 Non chargée", inline=True)
        e.add_field(name="Base de données", value="🟢 SQLite accessible" if self._database_ok() else "🔴 Vérifier la base SQLite", inline=False)
        e.add_field(name="Collecte des messages", value=f"Active depuis **{self._tracking_days()} jour(s)**. Seuls les compteurs agrégés par jour et salon sont ajoutés.", inline=False)
        e.set_footer(text="HORIZONS • Aucun contenu de message ni classement individuel n'est enregistré par ce module.")
        return e

    def _database_ok(self) -> bool:
        try:
            with db() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            log.exception("Test de disponibilité SQLite impossible.")
            return False

    @staticmethod
    def _selected_days(period: str) -> tuple[int, ...]:
        return (7, 30) if period == "compare" else (int(period),)

    @app_commands.command(name="horizons_dashboard", description="Consulter les statistiques collectives HORIZONS (staff).")
    @app_commands.guild_only()
    async def horizons_dashboard(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Accès réservé au staff autorisé.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("Cette commande doit être utilisée sur le serveur HORIZONS.", ephemeral=True)
            return
        embed = self.build_embed(interaction.guild, "overview", "compare")
        view = DashboardView(self, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HorizonsDashboard(bot))

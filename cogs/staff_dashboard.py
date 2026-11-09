"""Centre de commandement staff HORIZONS — interface 100 % Discord."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed

from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, STAFF_ROLE_ID, ALERT_LOG_CHANNEL_ID
from .storage import db


def _has_role(member: discord.Member, role_id: int | None) -> bool:
    return bool(role_id and any(role.id == role_id for role in member.roles))


def access_level(member: discord.Member) -> str | None:
    """Hiérarchie : propriétaire > admin > modérateur > animateur."""
    if member.guild.owner_id == member.id:
        return "founder"
    if member.guild_permissions.administrator or _has_role(member, ADMIN_ROLE_ID):
        return "admin"
    if _has_role(member, MOD_ROLE_ID):
        return "moderator"
    if _has_role(member, ANIMATOR_ROLE_ID):
        return "animator"
    # Compatibilité avec l'ancien rôle staff global, si aucun rôle dédié ne correspond.
    if _has_role(member, STAFF_ROLE_ID):
        return "moderator"
    return None


# IDs facultatifs : à renseigner dans .env lorsque les rôles dédiés seront connus.
from config import ADMIN_ROLE_ID, MOD_ROLE_ID, ANIMATOR_ROLE_ID

SECTIONS = {
    "overview": ("📊 Vue générale", {"founder", "admin", "moderator", "animator"}),
    "members": ("👥 Membres", {"founder", "admin"}),
    "moderation": ("🛡️ Modération", {"founder", "admin", "moderator"}),
    "surveillance": ("👁️ Surveillance", {"founder", "admin", "moderator"}),
    "tickets": ("🎫 Tickets", {"founder", "admin", "moderator"}),
    "team": ("🤝 Équipe staff", {"founder", "admin"}),
    "tasks": ("📋 Tâches", {"founder", "admin", "moderator"}),
    "events": ("📅 Animations", {"founder", "admin", "animator"}),
    "ideas": ("💡 Boîte à idées", {"founder", "admin"}),
    "solidarity": ("💜 Solidarité", {"founder", "admin"}),
    "stats": ("📈 Statistiques", {"founder", "admin"}),
    "config": ("⚙️ Configuration", {"founder"}),
}


def can_view(level: str | None, section: str) -> bool:
    return bool(level and level in SECTIONS[section][1])


def is_on_service(guild_id: int, user_id: int) -> bool:
    with db() as conn:
        return conn.execute("SELECT 1 FROM staff_shifts WHERE guild_id=? AND user_id=? AND ended_at IS NULL LIMIT 1", (guild_id, user_id)).fetchone() is not None


def task_embed(guild: discord.Guild, status: str = "all", limit: int = 10) -> discord.Embed:
    where = "guild_id=?"
    args: list[object] = [guild.id]
    if status != "all":
        where += " AND status=?"
        args.append(status)
    with db() as conn:
        rows = conn.execute(
            f"SELECT id,title,description,assignee_id,creator_id,priority,status,due_at,created_at FROM staff_tasks WHERE {where} ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, id DESC LIMIT ?",
            (*args, limit),
        ).fetchall()
        counts = {r["status"]: r["n"] for r in conn.execute("SELECT status,COUNT(*) n FROM staff_tasks WHERE guild_id=? GROUP BY status", (guild.id,)).fetchall()}
    labels = {"todo": "À faire", "doing": "En cours", "done": "Terminée", "cancelled": "Annulée"}
    priorities = {"urgent": "🔴 Urgente", "high": "🟠 Haute", "normal": "🔵 Normale", "low": "⚪ Basse"}
    e = horizons_embed(title="📋 Suivi des tâches HORIZONS", description=" • ".join(f"**{labels[k]} :** {counts.get(k, 0)}" for k in labels), color=discord.Color.blurple())
    if not rows:
        e.add_field(name="Aucune tâche", value="Crée une tâche avec `/tache_creer`.", inline=False)
    for r in rows:
        due = f" • Échéance : {r['due_at']}" if r["due_at"] else ""
        e.add_field(name=f"#{r['id']} — {r['title'][:220]}", value=f"{priorities.get(r['priority'], '🔵 Normale')} • {labels.get(r['status'], r['status'])}\nResponsable : <@{r['assignee_id']}>\n{r['description'][:350]}{due}", inline=False)
    e.set_footer(text="HORIZONS • Les tâches servent à s'entraider, pas à classer les bénévoles")
    return e


class DashboardView(discord.ui.View):
    def __init__(self, cog: "StaffDashboard", user_id: int, on_service: bool = False, level: str | None = None):
        super().__init__(timeout=900)
        self.cog = cog
        self.user_id = user_id
        self.on_service = on_service
        self.level = level
        self.selected_member_id = None
        if on_service:
            self.add_item(DashboardSelect(cog))
            if level in {"founder", "admin", "moderator"}:
                self.add_item(ModerationTargetSelect())
                self.add_item(QuickModerationSelect(cog))
        if on_service:
            self.add_item(RefreshDashboardButton(cog))
        self.add_item(ShiftButton(cog, start=not on_service))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce dashboard appartient à une autre personne du staff. Lance `/dashboard` pour ouvrir le tien.", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Tu n'as plus accès à ce dashboard.", ephemeral=True)
            return False
        return True


class RefreshDashboardButton(discord.ui.Button):
    """Actualise le bilan du staff sans nouvelle commande."""
    def __init__(self, cog: "StaffDashboard"):
        self.cog = cog
        super().__init__(label="Actualiser le bilan", emoji="🔄", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message("Action indisponible.", ephemeral=True)
            return
        if not is_on_service(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message("Prends d'abord ton service.", ephemeral=True)
            return
        level = access_level(interaction.user)
        if not level:
            await interaction.response.send_message("Accès réservé au staff.", ephemeral=True)
            return
        view = DashboardView(self.cog, interaction.user.id, on_service=True, level=level)
        section_select = next(item for item in view.children if isinstance(item, DashboardSelect))
        section_select.options = [discord.SelectOption(label=SECTIONS[k][0], value=k)
                                  for k in SECTIONS if can_view(level, k)]
        await interaction.response.edit_message(
            embed=self.cog.section_embed(interaction.guild, "overview", interaction.user), view=view,
        )


class ShiftButton(discord.ui.Button):
    def __init__(self, cog: "StaffDashboard", start: bool):
        self.cog = cog
        self.start = start
        super().__init__(label="Prendre mon service" if start else "Terminer mon service", emoji="🟢" if start else "🔴", style=discord.ButtonStyle.success if start else discord.ButtonStyle.danger, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message("Action disponible uniquement sur le serveur.", ephemeral=True); return
        now = datetime.now(timezone.utc).isoformat()
        with db() as conn:
            if self.start:
                if is_on_service(interaction.guild_id, interaction.user.id):
                    await interaction.response.send_message("Tu es déjà en service.", ephemeral=True); return
                conn.execute("INSERT INTO staff_shifts(guild_id,user_id,started_at,note) VALUES(?,?,?,?)", (interaction.guild_id,interaction.user.id,now,"Prise de service depuis le dashboard"))
                await self.cog.log_action(interaction.guild, f"🟢 {interaction.user.mention} a pris son service.")
            else:
                cur = conn.execute("UPDATE staff_shifts SET ended_at=? WHERE guild_id=? AND user_id=? AND ended_at IS NULL", (now,interaction.guild_id,interaction.user.id))
                if not cur.rowcount:
                    await interaction.response.send_message("Aucun service actif.", ephemeral=True); return
                await self.cog.log_action(interaction.guild, f"🔴 {interaction.user.mention} a terminé son service.")
        active = self.start
        embed = self.cog.dashboard_embed(interaction.user, active)
        await interaction.response.edit_message(embed=embed, view=DashboardView(self.cog, interaction.user.id, active, access_level(interaction.user)))


class ModerationTargetSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(placeholder="1. Sélectionner le membre à modérer", min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_member_id = self.values[0].id
        await interaction.response.send_message(f"Membre sélectionné : {self.values[0].mention}. Choisis ensuite une action de modération.", ephemeral=True)


class QuickModerationSelect(discord.ui.Select):
    def __init__(self, cog: "StaffDashboard"):
        self.cog = cog
        options = [
            discord.SelectOption(label="Avertissement", value="warn", emoji="⚠️"),
            discord.SelectOption(label="Timeout 10 minutes", value="timeout", emoji="🔇"),
            discord.SelectOption(label="Expulser", value="kick", emoji="👢"),
            discord.SelectOption(label="Bannir", value="ban", emoji="🔨"),
        ]
        super().__init__(placeholder="2. Choisir une action de modération", min_values=1, max_values=1, options=options, row=2)

    async def callback(self, interaction: discord.Interaction):
        target_id = getattr(self.view, "selected_member_id", None)
        if not target_id:
            await interaction.response.send_message("Sélectionne d'abord un membre dans le menu précédent.", ephemeral=True); return
        if not isinstance(interaction.user, discord.Member) or not interaction.guild:
            await interaction.response.send_message("Action indisponible.", ephemeral=True); return
        target = interaction.guild.get_member(target_id)
        if target is None:
            await interaction.response.send_message("Membre introuvable ou ayant quitté le serveur.", ephemeral=True); return
        level = access_level(interaction.user)
        if level not in {"founder", "admin", "moderator"}:
            await interaction.response.send_message("Cette action est réservée aux modérateurs et aux administrateurs.", ephemeral=True); return
        if target == interaction.user or target.id == interaction.guild.owner_id or (interaction.user.id != interaction.guild.owner_id and target.top_role >= interaction.user.top_role):
            await interaction.response.send_message("Tu ne peux pas appliquer cette action à ce membre (hiérarchie des rôles).", ephemeral=True); return
        await interaction.response.send_modal(ModerationReasonModal(self.cog, target, self.values[0]))


class ModerationReasonModal(discord.ui.Modal):
    def __init__(self, cog: "StaffDashboard", target: discord.Member, action: str):
        super().__init__(title="Confirmer l'action de modération")
        self.cog, self.target, self.action = cog, target, action
        self.reason = discord.ui.TextInput(label="Motif (obligatoire)", placeholder="Décris brièvement la raison de l'action", min_length=3, max_length=500)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.guild or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Ton service n'est plus actif. Aucune action effectuée.", ephemeral=True); return
        reason = str(self.reason.value)
        try:
            if self.action == "warn":
                with db() as conn:
                    cur = conn.execute("INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)", (interaction.guild_id,self.target.id,interaction.user.id,reason,datetime.now(timezone.utc).isoformat()))
                    ref = cur.lastrowid
                try: await self.target.send(f"Tu as reçu un avertissement sur **{interaction.guild.name}**.\nMotif : {reason}")
                except discord.Forbidden: pass
                result = f"Avertissement #{ref} enregistré pour {self.target.mention}."
            elif self.action == "timeout":
                await self.target.timeout(discord.utils.utcnow() + timedelta(minutes=10), reason=f"{reason} | par {interaction.user}")
                result = f"{self.target.mention} est en timeout pendant 10 minutes."
            elif self.action == "kick":
                await self.target.kick(reason=f"{reason} | par {interaction.user}")
                result = f"{self.target} a été expulsé."
            else:
                await self.target.ban(reason=f"{reason} | par {interaction.user}", delete_message_seconds=0)
                result = f"{self.target} a été banni."
        except discord.Forbidden:
            await interaction.response.send_message("Discord a refusé l'action : vérifie les permissions et la hiérarchie du bot.", ephemeral=True); return
        except discord.HTTPException as exc:
            await interaction.response.send_message(f"L'action a échoué : {exc}", ephemeral=True); return
        await self.cog.log_action(interaction.guild, f"🛡️ {interaction.user.mention} — {self.action} — {self.target} — Motif : {reason}")
        await interaction.response.send_message(f"✅ {result}\nMotif : {reason}", ephemeral=True)


class DashboardSelect(discord.ui.Select):
    def __init__(self, cog: "StaffDashboard"):
        self.cog = cog
        # Les choix sont filtrés au moment de l'ouverture du dashboard dans callback.
        options = [discord.SelectOption(label="Chargement des rubriques…", value="overview", emoji="📊")]
        super().__init__(placeholder="Ouvrir une rubrique du centre de commandement", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        level = access_level(member) if isinstance(member, discord.Member) else None
        if not interaction.guild_id or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prends d'abord ton service pour accéder aux rubriques du dashboard.", ephemeral=True); return
        available = [key for key in SECTIONS if can_view(level, key)]
        # La sélection est remplacée à chaque affichage afin de respecter les droits actuels.
        if self.values[0] not in available:
            await interaction.response.send_message("Cette rubrique ne t'est pas accessible.", ephemeral=True)
            return
        embed = self.cog.section_embed(interaction.guild, self.values[0], member)
        view = DashboardView(self.cog, interaction.user.id, on_service=True, level=level)
        section_select = next(item for item in view.children if isinstance(item, DashboardSelect))
        section_select.options = [discord.SelectOption(label=SECTIONS[k][0], value=k) for k in available]
        await interaction.response.edit_message(embed=embed, view=view)


class StaffDashboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def dashboard_embed(self, member: discord.Member, active: bool) -> discord.Embed:
        if active:
            with db() as conn:
                row = conn.execute("SELECT started_at FROM staff_shifts WHERE guild_id=? AND user_id=? AND ended_at IS NULL ORDER BY id DESC LIMIT 1", (member.guild.id, member.id)).fetchone()
            started = row["started_at"] if row else "inconnue"
            description = f"Bienvenue {member.mention}.\n\n🟢 **Tu es en service.**\nDébut : `{started}`\n\nUtilise les rubriques pour travailler. Les actions disponibles dépendent de ton rôle."
            return horizons_embed(title="HORIZONS — Poste de travail du staff", description=description, color=discord.Color.green())
        description = f"Bienvenue {member.mention}.\n\n🔴 **Tu es hors service.**\n\nPour accéder aux rubriques, à la modération et aux outils de l'équipe, clique sur **Prendre mon service**. Cette étape enregistre automatiquement l'heure de début."
        return horizons_embed(title="HORIZONS — Poste de travail du staff", description=description, color=discord.Color.orange())

    def section_embed(self, guild: discord.Guild, section: str, member: discord.Member) -> discord.Embed:
        with db() as conn:
            if section == "overview":
                ideas = conn.execute("SELECT COUNT(*) FROM community_ideas WHERE guild_id=? AND status IN ('received','review')", (guild.id,)).fetchone()[0]
                tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE guild_id=? AND status='open'", (guild.id,)).fetchone()[0]
                events = conn.execute("SELECT COUNT(*) FROM events WHERE guild_id=? AND status='open'", (guild.id,)).fetchone()[0]
                tasks = conn.execute("SELECT COUNT(*) FROM staff_tasks WHERE guild_id=? AND status IN ('todo','doing')", (guild.id,)).fetchone()[0]
                alerts = conn.execute("SELECT COUNT(*) FROM staff_alerts WHERE guild_id=? AND status='open'", (guild.id,)).fetchone()[0]
                e = horizons_embed(title="HORIZONS — Centre de commandement", description=f"Bienvenue {member.mention}. Voici les éléments qui nécessitent une attention.\n\n**Membres :** {guild.member_count or 'N/D'}\n**Alertes ouvertes :** {alerts}\n**Idées à examiner :** {ideas}\n**Tickets ouverts :** {tickets}\n**Tâches à suivre :** {tasks}\n**Animations ouvertes :** {events}", color=discord.Color.blurple())
            elif section == "members":
                e = horizons_embed(title="👥 Membres", description=f"Membres connus : **{guild.member_count or 'N/D'}**\nLa recherche et les fiches individuelles seront ajoutées dans une prochaine sous-version. Les commandes membres existantes restent disponibles.", color=discord.Color.blurple())
            elif section == "moderation":
                warns = conn.execute("SELECT COUNT(*) FROM warnings WHERE guild_id=? AND active=1", (guild.id,)).fetchone()[0]
                notes = conn.execute("SELECT COUNT(*) FROM member_notes WHERE guild_id=?", (guild.id,)).fetchone()[0]
                e = horizons_embed(title="🛡️ Modération", description=f"**Avertissements actifs :** {warns}\n**Notes internes :** {notes}\nUtilise les commandes de modération existantes pour intervenir. Chaque action doit rester proportionnée et documentée.", color=discord.Color.orange())
            elif section == "surveillance":
                rows = conn.execute("SELECT id,user_id,reason,created_at FROM staff_alerts WHERE guild_id=? AND status='open' ORDER BY id DESC LIMIT 10", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` • <@{r['user_id']}> • {r['reason'][:120]}" for r in rows) or "Aucune alerte ouverte enregistrée."
                e = horizons_embed(title="👁️ Surveillance et alertes", description=body, color=discord.Color.orange())
            elif section == "tickets":
                rows = conn.execute("SELECT id,opener_id,subject,created_at FROM tickets WHERE guild_id=? AND status='open' ORDER BY id DESC LIMIT 10", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` • <@{r['opener_id']}> • {r['subject'][:100]}" for r in rows) or "Aucun ticket ouvert."
                e = horizons_embed(title="🎫 Assistance et tickets", description=body, color=discord.Color.teal())
            elif section == "team":
                rows = conn.execute("SELECT user_id,started_at,note FROM staff_shifts WHERE guild_id=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 20", (guild.id,)).fetchall()
                body = "\n".join(f"<@{r['user_id']}> • depuis {r['started_at']}" + (f"\n↳ {r['note']}" if r['note'] else "") for r in rows) or "Aucune prise de service active."
                e = horizons_embed(title="🤝 Équipe staff — disponibilité", description=body, color=discord.Color.green())
            elif section == "tasks":
                return task_embed(guild)
            elif section == "events":
                rows = conn.execute("SELECT id,title,starts_at FROM events WHERE guild_id=? AND status='open' ORDER BY starts_at LIMIT 10", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` **{r['title']}** — {r['starts_at']}" for r in rows) or "Aucune animation ouverte."
                e = horizons_embed(title="📅 Animations", description=body, color=discord.Color.green())
            elif section == "ideas":
                rows = conn.execute("SELECT id,status,content FROM community_ideas WHERE guild_id=? ORDER BY id DESC LIMIT 10", (guild.id,)).fetchall()
                body = "\n".join(f"`#{r['id']}` **{r['status']}** — {r['content'][:120]}" for r in rows) or "Aucune idée reçue."
                e = horizons_embed(title="💡 Boîte à idées", description=body, color=discord.Color.gold())
            elif section == "solidarity":
                rows = conn.execute("SELECT target_id,reason,created_at FROM solidarity_thanks WHERE guild_id=? ORDER BY id DESC LIMIT 10", (guild.id,)).fetchall()
                body = "\n".join(f"<@{r['target_id']}> — {r['reason']}" for r in rows) or "Aucun remerciement enregistré."
                e = horizons_embed(title="💜 Solidarité", description=body, color=discord.Color.magenta())
            elif section == "stats":
                warnings = conn.execute("SELECT COUNT(*) FROM warnings WHERE guild_id=?", (guild.id,)).fetchone()[0]
                thanks = conn.execute("SELECT COUNT(*) FROM solidarity_thanks WHERE guild_id=?", (guild.id,)).fetchone()[0]
                e = horizons_embed(title="📈 Statistiques", description=f"**Membres :** {guild.member_count or 'N/D'}\n**Avertissements enregistrés :** {warnings}\n**Remerciements :** {thanks}\nLes indicateurs seront enrichis au fil des modules.", color=discord.Color.blurple())
            else:
                e = horizons_embed(title="⚙️ Configuration", description="Accès fondateur uniquement. Les paramètres sensibles restent dans la configuration locale du bot et ne sont jamais affichés dans Discord.", color=discord.Color.dark_grey())
        e.set_footer(text=f"HORIZONS • Centre staff • {SECTIONS[section][0]}")
        return e

    @app_commands.command(name="dashboard", description="Ouvrir le centre de commandement HORIZONS (staff).")
    async def dashboard(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Commande utilisable sur le serveur HORIZONS.", ephemeral=True); return
        level = access_level(interaction.user)
        if not level:
            await interaction.response.send_message("Accès réservé au staff autorisé.", ephemeral=True); return
        active = is_on_service(interaction.guild_id, interaction.user.id)
        view = DashboardView(self, interaction.user.id, active, level)
        if active:
            select = next(item for item in view.children if isinstance(item, DashboardSelect))
            available = [key for key in SECTIONS if can_view(level, key)]
            select.options = [discord.SelectOption(label=SECTIONS[k][0], value=k) for k in available]
        await interaction.response.send_message(embed=self.dashboard_embed(interaction.user, active), view=view, ephemeral=True)

    @app_commands.command(name="tache_creer", description="Créer une tâche pour un membre du staff.")
    @app_commands.describe(titre="Titre court", responsable="Membre chargé de la tâche", description="Détails utiles", priorite="Niveau de priorité", echeance="Échéance facultative au format JJ/MM/AAAA")
    @app_commands.choices(priorite=[app_commands.Choice(name="Basse",value="low"),app_commands.Choice(name="Normale",value="normal"),app_commands.Choice(name="Haute",value="high"),app_commands.Choice(name="Urgente",value="urgent")])
    async def tache_creer(self, interaction: discord.Interaction, titre: app_commands.Range[str,3,100], responsable: discord.Member, description: app_commands.Range[str,3,1000], priorite: app_commands.Choice[str], echeance: str = None):
        if not isinstance(interaction.user, discord.Member) or access_level(interaction.user) not in {"founder","admin","moderator"} or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prise de service obligatoire. Seuls le fondateur, les administrateurs et les modérateurs en service peuvent créer des tâches.", ephemeral=True); return
        if access_level(responsable) not in {"founder","admin","moderator"}:
            await interaction.response.send_message("Le responsable doit être fondateur, administrateur ou modérateur. Les animateurs disposent de leur rubrique dédiée.", ephemeral=True); return
        if echeance:
            try: datetime.strptime(echeance, "%d/%m/%Y")
            except ValueError:
                await interaction.response.send_message("Format d'échéance invalide. Utilise JJ/MM/AAAA.", ephemeral=True); return
        p = priorite.value if priorite else "normal"
        with db() as conn:
            cur = conn.execute("INSERT INTO staff_tasks(guild_id,title,description,assignee_id,creator_id,priority,status,due_at,created_at) VALUES(?,?,?,?,?,?,'todo',?,?)", (interaction.guild_id,titre,description,responsable.id,interaction.user.id,p,echeance,datetime.now(timezone.utc).isoformat()))
            task_id = cur.lastrowid
        await interaction.response.send_message(f"✅ Tâche **#{task_id}** créée et attribuée à {responsable.mention}.", ephemeral=True)
        try: await responsable.send(f"📋 Une tâche HORIZONS t'a été attribuée : **{titre}**\n{description}\nPriorité : **{p}**" + (f"\nÉchéance : {echeance}" if echeance else ""))
        except discord.Forbidden: pass
        await self.log_action(interaction.guild, f"Tâche #{task_id} créée par {interaction.user.mention} pour {responsable.mention} : {titre}")

    @app_commands.command(name="taches", description="Consulter les tâches de l'équipe staff.")
    @app_commands.choices(statut=[app_commands.Choice(name="Toutes",value="all"),app_commands.Choice(name="À faire",value="todo"),app_commands.Choice(name="En cours",value="doing"),app_commands.Choice(name="Terminées",value="done")])
    async def taches(self, interaction: discord.Interaction, statut: app_commands.Choice[str] = None):
        if not isinstance(interaction.user, discord.Member) or access_level(interaction.user) not in {"founder","admin","moderator"} or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prise de service obligatoire. Accès réservé au staff habilité en service.", ephemeral=True); return
        await interaction.response.send_message(embed=task_embed(interaction.guild, statut.value if statut else "all"), ephemeral=True)

    @app_commands.command(name="tache_statut", description="Mettre à jour une tâche qui t'est attribuée (ou tâche staff si admin).")
    @app_commands.choices(statut=[app_commands.Choice(name="À faire",value="todo"),app_commands.Choice(name="En cours",value="doing"),app_commands.Choice(name="Terminée",value="done"),app_commands.Choice(name="Annulée",value="cancelled")])
    async def tache_statut(self, interaction: discord.Interaction, identifiant: app_commands.Range[int,1,1000000], statut: app_commands.Choice[str]):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user) or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prise de service obligatoire pour gérer les tâches.", ephemeral=True); return
        with db() as conn:
            row = conn.execute("SELECT assignee_id,title FROM staff_tasks WHERE id=? AND guild_id=?", (identifiant,interaction.guild_id)).fetchone()
            if not row:
                await interaction.response.send_message("Tâche introuvable.", ephemeral=True); return
            level = access_level(interaction.user)
            if row["assignee_id"] != interaction.user.id and level not in {"founder","admin"}:
                await interaction.response.send_message("Tu peux uniquement modifier les tâches qui te sont attribuées.", ephemeral=True); return
            conn.execute("UPDATE staff_tasks SET status=?,updated_at=? WHERE id=?", (statut.value,datetime.now(timezone.utc).isoformat(),identifiant))
            conn.execute("INSERT INTO staff_task_history(task_id,actor_id,action,created_at) VALUES(?,?,?,?)", (identifiant,interaction.user.id,f"Statut : {statut.value}",datetime.now(timezone.utc).isoformat()))
        await interaction.response.send_message(f"Tâche **#{identifiant}** mise à jour : **{statut.name}**.", ephemeral=True)
        await self.log_action(interaction.guild, f"{interaction.user.mention} a modifié la tâche #{identifiant} ({row['title']}) : {statut.name}")

    @app_commands.command(name="service", description="Déclarer le début ou la fin de ton service staff.")
    @app_commands.choices(action=[app_commands.Choice(name="Prendre mon service",value="start"),app_commands.Choice(name="Terminer mon service",value="end")])
    async def service(self, interaction: discord.Interaction, action: app_commands.Choice[str], note: str = ""):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Commande réservée au staff.", ephemeral=True); return
        note = note[:300]
        now = datetime.now(timezone.utc).isoformat()
        with db() as conn:
            if action.value == "start":
                if is_on_service(interaction.guild_id, interaction.user.id):
                    await interaction.response.send_message("Tu es déjà en service.", ephemeral=True); return
                conn.execute("INSERT INTO staff_shifts(guild_id,user_id,started_at,note) VALUES(?,?,?,?)", (interaction.guild_id,interaction.user.id,now,note))
                message = "🟢 Ton service est enregistré. Merci pour ton aide !"
            else:
                cur = conn.execute("UPDATE staff_shifts SET ended_at=? WHERE guild_id=? AND user_id=? AND ended_at IS NULL", (now,interaction.guild_id,interaction.user.id))
                message = "🔴 Ton service est terminé." if cur.rowcount else "Aucun service actif n'était enregistré."
        await interaction.response.send_message(message, ephemeral=True)
        await self.log_action(interaction.guild, f"{interaction.user.mention} : {action.name.lower()}")

    async def log_action(self, guild: discord.Guild, content: str):
        channel = guild.get_channel(ALERT_LOG_CHANNEL_ID) if ALERT_LOG_CHANNEL_ID else None
        if isinstance(channel, discord.TextChannel):
            try: await channel.send(content, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException: pass


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffDashboard(bot))

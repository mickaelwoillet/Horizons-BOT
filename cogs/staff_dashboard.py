"""Centre de commandement staff HORIZONS — interface 100 % Discord."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
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
        e.add_field(name="Aucune tâche", value="Utilise `/equipe tache_creer` pour créer une tâche.", inline=False)
    for r in rows:
        due = f" • Échéance : {r['due_at']}" if r["due_at"] else ""
        e.add_field(name=f"#{r['id']} — {r['title'][:220]}", value=f"{priorities.get(r['priority'], '🔵 Normale')} • {labels.get(r['status'], r['status'])}\nResponsable : <@{r['assignee_id']}>\n{r['description'][:350]}{due}", inline=False)
    e.set_footer(text="HORIZONS • Les tâches servent à s'entraider, pas à classer les bénévoles")
    return e



class SectionsButton(discord.ui.Button):
    """Ouvre une grille de boutons plutôt qu'une liste déroulante."""
    def __init__(self, cog):
        self.cog = cog
        super().__init__(label="Rubriques du staff", emoji="🗂️", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        level = access_level(interaction.user) if isinstance(interaction.user, discord.Member) else None
        if not interaction.guild or not level or not is_on_service(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message("Prends ton service pour ouvrir les rubriques.", ephemeral=True)
            return
        await interaction.response.send_message(
            "**Rubriques HORIZONS** — choisis directement un bouton :",
            view=SectionsGridView(self.cog, interaction.user.id, level), ephemeral=True)


class SectionNavButton(discord.ui.Button):
    def __init__(self, cog, section, index):
        self.cog, self.section = cog, section
        super().__init__(label=SECTIONS[section][0], style=discord.ButtonStyle.secondary,
                         row=index // 5)

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        level = access_level(member) if isinstance(member, discord.Member) else None
        if not interaction.guild or not can_view(level, self.section) or not is_on_service(interaction.guild.id, member.id):
            await interaction.response.send_message("Accès non autorisé ou service terminé.", ephemeral=True)
            return
        if self.section == "events":
            await interaction.response.send_message(embed=self.cog.section_embed(interaction.guild, self.section, member),
                                                    view=EventsStaffView(member.id), ephemeral=True)
            return
        if self.section == "tasks":
            await interaction.response.send_message(embed=task_embed(interaction.guild),
                                                    view=TaskFilterView(member.id), ephemeral=True)
            return
        await interaction.response.send_message(embed=self.cog.section_embed(interaction.guild, self.section, member),
                                                ephemeral=True)


class EventCloseModal(discord.ui.Modal, title="Fermer les inscriptions"):
    numero = discord.ui.TextInput(label="Numéro de l’événement", placeholder="Ex. 12", max_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        from .events import Events
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user) in {"founder", "admin", "animator"} or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Accès non autorisé ou service terminé.", ephemeral=True)
            return
        try:
            numero = int(str(self.numero.value).strip())
            if not 1 <= numero <= 999999:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Indique un numéro d'événement valide.", ephemeral=True)
            return
        cog = interaction.client.get_cog("Events")
        if cog is None:
            await interaction.response.send_message("Le module Événements n'est pas chargé.", ephemeral=True)
            return
        await cog.evenement_fermer(interaction, numero)


class EventsStaffView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if (interaction.user.id != self.user_id or not isinstance(interaction.user, discord.Member)
                or access_level(interaction.user) not in {"founder", "admin", "animator"}
                or not is_on_service(interaction.guild_id, interaction.user.id)):
            await interaction.response.send_message("Accès non autorisé ou service terminé.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Voir les événements", emoji="📅", style=discord.ButtonStyle.primary)
    async def list_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        from .events import Events
        cog = interaction.client.get_cog("Events")
        if cog is None:
            await interaction.response.send_message("Le module Événements n'est pas chargé.", ephemeral=True)
            return
        await cog.evenements.callback(cog, interaction)

    @discord.ui.button(label="Fermer les inscriptions", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def close_event(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EventCloseModal())


class SectionsGridView(discord.ui.View):
    def __init__(self, cog, user_id, level):
        super().__init__(timeout=600)
        self.user_id = user_id
        for index, section in enumerate(k for k in SECTIONS if can_view(level, k)):
            self.add_item(SectionNavButton(cog, section, index))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce panneau appartient à un autre membre du staff.", ephemeral=True)
            return False
        return True

class RegardValidateModal(discord.ui.Modal, title="Regard — décision de modération"):
    numero = discord.ui.TextInput(label="Identifiant numérique", placeholder="Ex. 42", max_length=12)
    decision = discord.ui.TextInput(label="Décision", placeholder="approuver ou refuser", max_length=12)

    def __init__(self, bot, action):
        super().__init__()
        self.bot, self.action = bot, action

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user) or not is_on_service(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("Staff en service uniquement.", ephemeral=True)
        if not str(self.numero.value).isdigit():
            return await interaction.response.send_message("Identifiant invalide.", ephemeral=True)
        choice = str(self.decision.value).strip().lower()
        mapping = {"approuver": ("approved", "Approuver"), "refuser": ("rejected", "Refuser")}
        if choice not in mapping:
            return await interaction.response.send_message("Indique approuver ou refuser.", ephemeral=True)
        from discord import app_commands
        cog = self.bot.get_cog("RegardDuJour")
        if cog is None:
            return await interaction.response.send_message("Module Regard indisponible.", ephemeral=True)
        value, label = mapping[choice]
        decision = app_commands.Choice(name=label, value=value)
        if self.action == "valider":
            await type(cog).valider.callback(cog, interaction, int(self.numero.value), decision)
        else:
            await type(cog).proposition_valider.callback(cog, interaction, int(self.numero.value), decision)


class RegardAddModal(discord.ui.Modal, title="Ajouter au Regard du Jour"):
    titre = discord.ui.TextInput(label="Titre", max_length=200)
    lien = discord.ui.TextInput(label="Lien HTTPS", max_length=1000)
    musique = discord.ui.TextInput(label="Musique ? (oui/non)", default="non", max_length=3)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction):
        cog = self.bot.get_cog("RegardDuJour")
        if cog is None:
            return await interaction.response.send_message("Module Regard indisponible.", ephemeral=True)
        value = self.musique.value.strip().lower()
        if value not in ("oui", "non"):
            return await interaction.response.send_message("Indique oui ou non pour la musique.", ephemeral=True)
        await type(cog).ajouter(cog, interaction, self.titre.value, self.lien.value, value == "oui")


class RegardboardView(discord.ui.View):
    """Actions de lecture du Regard, sans nouvelle commande slash."""
    def __init__(self, bot, user_id):
        super().__init__(timeout=600)
        self.bot, self.user_id = bot, user_id

    async def interaction_check(self, interaction):
        if interaction.user.id != self.user_id or not isinstance(interaction.user, discord.Member) or not access_level(interaction.user) or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Accès réservé au staff en service et au propriétaire de ce panneau.", ephemeral=True)
            return False
        return True

    async def _call(self, interaction, name):
        cog = self.bot.get_cog("RegardDuJour")
        if cog is None:
            await interaction.response.send_message("Le module Regard du Jour n'est pas chargé.", ephemeral=True)
            return
        await getattr(type(cog), name).callback(cog, interaction)

    @discord.ui.button(label="Diagnostic", emoji="🩺", style=discord.ButtonStyle.secondary)
    async def diagnostic_button(self, interaction, button):
        await self._call(interaction, "diagnostic")

    @discord.ui.button(label="Propositions membres", emoji="📬", style=discord.ButtonStyle.secondary)
    async def proposals_button(self, interaction, button):
        await self._call(interaction, "propositions")

    @discord.ui.button(label="Valider un article", emoji="✅", style=discord.ButtonStyle.primary)
    async def validate_article_button(self, interaction, button):
        await interaction.response.send_modal(RegardValidateModal(self.bot, "valider"))

    @discord.ui.button(label="Traiter une proposition", emoji="📝", style=discord.ButtonStyle.secondary)
    async def validate_proposal_button(self, interaction, button):
        await interaction.response.send_modal(RegardValidateModal(self.bot, "proposition_valider"))

    @discord.ui.button(label="Articles à valider", emoji="📰", style=discord.ButtonStyle.primary)
    async def selection_button(self, interaction, button):
        await self._call(interaction, "selection")

    @discord.ui.button(label="Collecter les liens", emoji="🔎", style=discord.ButtonStyle.secondary, row=1)
    async def collect_button(self, interaction, button):
        await self._call(interaction, "collecter")

    @discord.ui.button(label="Ajouter un article", emoji="➕", style=discord.ButtonStyle.primary, row=1)
    async def add_button(self, interaction, button):
        await interaction.response.send_modal(RegardAddModal(self.bot))


class RegardboardButton(discord.ui.Button):
    def __init__(self, bot):
        super().__init__(label="Regardboard", emoji="📰", style=discord.ButtonStyle.secondary, row=3)
        self.bot = bot

    async def callback(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user) or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prise de service staff obligatoire.", ephemeral=True)
            return
        await interaction.response.send_message("**Regardboard** — suivi et sélection des articles. Les actions de validation sont accessibles ici ; les autres opérations restent protégées.", view=RegardboardView(self.bot, interaction.user.id), ephemeral=True)



class EventQuizModal(discord.ui.Modal, title="Lancer un quiz culturel"):
    manches = discord.ui.TextInput(label="Nombre de manches (1 à 10)", default="5", max_length=2)
    async def on_submit(self, interaction):
        if not str(self.manches.value).isdigit() or not 1 <= int(self.manches.value) <= 10:
            return await interaction.response.send_message("Choisis entre 1 et 10 manches.", ephemeral=True)
        cog = interaction.client.get_cog("Quizzes")
        if cog is None:
            return await interaction.response.send_message("Module Quiz indisponible.", ephemeral=True)
        await cog.quiz_lancer(interaction, int(self.manches.value))

class EventCreateModal(discord.ui.Modal, title="Créer un événement HORIZONS"):
    titre = discord.ui.TextInput(label="Titre", min_length=3, max_length=100)
    date_heure = discord.ui.TextInput(label="Date et heure (JJ/MM/AAAA HH:MM)", max_length=16, placeholder="25/11/2026 18:30")
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, min_length=5, max_length=1800)
    lieu = discord.ui.TextInput(label="Lieu", default="En ligne / à préciser", max_length=100)
    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("Events")
        if cog is None:
            return await interaction.response.send_message("Module Événements indisponible.", ephemeral=True)
        await cog.evenement_creer(interaction, self.titre.value, self.date_heure.value, self.description.value, self.lieu.value, None)

class GiveawayNumberModal(discord.ui.Modal):
    numero = discord.ui.TextInput(label="Numéro du concours", max_length=8)
    def __init__(self, action):
        super().__init__(title="Concours — " + ("Annuler" if action == "annuler" else "Nouveau tirage"))
        self.action = action
    async def on_submit(self, interaction):
        if not self.numero.value.isdecimal() or not 1 <= int(self.numero.value) <= 999999:
            return await interaction.response.send_message("Numéro invalide.", ephemeral=True)
        cog = interaction.client.get_cog("Giveaways")
        if cog is None:
            return await interaction.response.send_message("Module Concours indisponible.", ephemeral=True)
        await getattr(cog, self.action)(interaction, int(self.numero.value))

class EventBoardView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id
    async def interaction_check(self, interaction):
        if (interaction.user.id != self.user_id or not isinstance(interaction.user, discord.Member)
                or access_level(interaction.user) not in {"founder", "admin", "animator"}
                or not is_on_service(interaction.guild_id, interaction.user.id)):
            await interaction.response.send_message("Réservé au staff autorisé en service.", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Créer événement", emoji="➕", style=discord.ButtonStyle.success, row=1)
    async def create_event(self, interaction, button):
        await interaction.response.send_modal(EventCreateModal())
    @discord.ui.button(label="Annuler concours", emoji="🚫", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_giveaway(self, interaction, button):
        await interaction.response.send_modal(GiveawayNumberModal("annuler"))
    @discord.ui.button(label="Nouveau tirage", emoji="🎲", style=discord.ButtonStyle.secondary, row=1)
    async def reroll_giveaway(self, interaction, button):
        await interaction.response.send_modal(GiveawayNumberModal("reroll"))
    @discord.ui.button(label="Agenda", emoji="📅", style=discord.ButtonStyle.primary)
    async def agenda(self, interaction, button):
        cog = interaction.client.get_cog("Events")
        if cog is None:
            return await interaction.response.send_message("Module Événements indisponible.", ephemeral=True)
        await type(cog).evenements.callback(cog, interaction)
    @discord.ui.button(label="Fermer inscriptions", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def close(self, interaction, button):
        await interaction.response.send_modal(EventCloseModal())
    @discord.ui.button(label="Lancer quiz", emoji="🧠", style=discord.ButtonStyle.success)
    async def quiz_start(self, interaction, button):
        await interaction.response.send_modal(EventQuizModal())
    @discord.ui.button(label="Arrêter quiz", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def quiz_stop(self, interaction, button):
        cog = interaction.client.get_cog("Quizzes")
        if cog is None:
            return await interaction.response.send_message("Module Quiz indisponible.", ephemeral=True)
        await cog.quiz_arreter(interaction)

class EventBoardButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Event", emoji="🎉", style=discord.ButtonStyle.secondary, row=3)
    async def callback(self, interaction):
        if not isinstance(interaction.user, discord.Member) or access_level(interaction.user) not in {"founder", "admin", "animator"} or not is_on_service(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("Staff autorisé en service uniquement.", ephemeral=True)
        await interaction.response.send_message("**Event** — événements, concours et quiz. Création de concours : commande conservée en attendant le formulaire complet.", view=EventBoardView(interaction.user.id), ephemeral=True)

class CapsuleQuestionModal(discord.ui.Modal, title="Capsules — question du mois"):
    question = discord.ui.TextInput(label="Question collective", style=discord.TextStyle.paragraph, max_length=500)
    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("CentreHorizons")
        if cog is None:
            return await interaction.response.send_message("Module Capsules indisponible.", ephemeral=True)
        await cog.capsule_question(interaction, str(self.question.value))

class CapsuleModerationModal(discord.ui.Modal, title="Capsules — modérer une contribution"):
    numero = discord.ui.TextInput(label="Numéro de contribution", placeholder="Ex. 42", max_length=12)
    decision = discord.ui.TextInput(label="Décision : approuver ou refuser", placeholder="approuver", max_length=12)

    async def on_submit(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild or not is_on_service(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("Gestion du serveur et prise de service requises.", ephemeral=True)
        if not str(self.numero.value).strip().isdigit():
            return await interaction.response.send_message("Le numéro doit être un entier positif.", ephemeral=True)
        decision = str(self.decision.value).strip().lower()
        choices = {"approuver": "approve", "refuser": "reject"}
        if decision not in choices:
            return await interaction.response.send_message("Saisir exactement approuver ou refuser.", ephemeral=True)
        cog = interaction.client.get_cog("CentreHorizons")
        if cog is None:
            return await interaction.response.send_message("Module Capsules indisponible.", ephemeral=True)
        await cog.capsule_moderer(interaction, int(self.numero.value), choices[decision])


class CapsuleStaffView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=600)
        self.user_id = user_id
    async def interaction_check(self, interaction):
        if (interaction.user.id != self.user_id or not isinstance(interaction.user, discord.Member)
                or not interaction.user.guild_permissions.manage_guild or not is_on_service(interaction.guild_id, interaction.user.id)):
            await interaction.response.send_message("Gestion du serveur et prise de service requises.", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Contributions en attente", emoji="📬", style=discord.ButtonStyle.primary)
    async def pending(self, interaction, button):
        cog = interaction.client.get_cog("CentreHorizons")
        if cog is None:
            return await interaction.response.send_message("Module Capsules indisponible.", ephemeral=True)
        await cog.capsule_attente(interaction)
    @discord.ui.button(label="Question du mois", emoji="✍️", style=discord.ButtonStyle.secondary)
    async def question_button(self, interaction, button):
        await interaction.response.send_modal(CapsuleQuestionModal())

    @discord.ui.button(label="Modérer une contribution", emoji="⚖️", style=discord.ButtonStyle.secondary)
    async def moderate_button(self, interaction, button):
        await interaction.response.send_modal(CapsuleModerationModal())

class CapsuleStaffButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Capsules staff", emoji="⏳", style=discord.ButtonStyle.secondary, row=3)
    async def callback(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild or not is_on_service(interaction.guild_id, interaction.user.id):
            return await interaction.response.send_message("Gestion du serveur et prise de service requises.", ephemeral=True)
        await interaction.response.send_message("**Capsules staff** — suivi des contributions et question collective.", view=CapsuleStaffView(interaction.user.id), ephemeral=True)

class DashboardView(discord.ui.View):
    def __init__(self, cog: "StaffDashboard", user_id: int, on_service: bool = False, level: str | None = None):
        super().__init__(timeout=900)
        self.cog = cog
        self.user_id = user_id
        self.on_service = on_service
        self.level = level
        self.selected_member_id = None
        if on_service:
            self.add_item(SectionsButton(cog))
            if level in {"founder", "admin", "moderator"}:
                self.add_item(ModerationTargetSelect())
                self.add_item(QuickModerationSelect(cog))
        if on_service:
            self.add_item(RefreshDashboardButton(cog))
        self.add_item(ShiftButton(cog, start=not on_service))
        self.add_item(CollectiveStatsButton())
        if on_service:
            self.add_item(PublicationsPanelButton())
            self.add_item(AnimationsPanelButton())
            self.add_item(CommunityHubButton())
            self.add_item(RegardboardButton(cog.bot))
            if level in {"founder", "admin", "animator"}:
                self.add_item(EventBoardButton())
            if level in {"founder", "admin"}:
                self.add_item(CapsuleStaffButton())
            if level in {"founder", "admin"}:
                self.add_item(NoxTVStaffButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce dashboard appartient à une autre personne du staff. Lance `/dashboard` pour ouvrir le tien.", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Tu n'as plus accès à ce dashboard.", ephemeral=True)
            return False
        # Un panneau ouvert avant la fin du service ne doit pas rester utilisable.
        if self.on_service and not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Ton service est terminé. Rouvre `/dashboard`.", ephemeral=True)
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
        if not access_level(interaction.user):
            await interaction.response.send_message("Accès réservé au staff autorisé.", ephemeral=True); return
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
        if access_level(interaction.user) not in {"founder", "admin", "moderator"}:
            await interaction.response.send_message("Tu n'as plus les permissions de modération.", ephemeral=True); return
        if (self.target.id == interaction.user.id or self.target.id == interaction.guild.owner_id
                or (interaction.user.id != interaction.guild.owner_id and self.target.top_role >= interaction.user.top_role)):
            await interaction.response.send_message("Action refusée : hiérarchie des rôles modifiée.", ephemeral=True); return
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


class CollectiveStatsButton(discord.ui.Button):
    """Accès aux statistiques collectives depuis /dashboard, sans commande slash supplémentaire."""
    def __init__(self):
        super().__init__(label="Statistiques collectives", emoji="📈", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Accès réservé au staff autorisé.", ephemeral=True)
            return
        if interaction.guild is None:
            await interaction.response.send_message("Utilise ce panneau sur HORIZONS.", ephemeral=True)
            return
        cog = interaction.client.get_cog("HorizonsDashboard")
        if cog is None:
            await interaction.response.send_message("Le module des statistiques est indisponible.", ephemeral=True)
            return
        from .horizons_dashboard import DashboardView as CollectiveDashboardView
        embed = cog.build_embed(interaction.guild, "overview", "compare")
        await interaction.response.send_message(
            embed=embed,
            view=CollectiveDashboardView(cog, interaction.user.id),
            ephemeral=True,
        )


class CommunityHubButton(discord.ui.Button):
    """Navigation vers le tableau de bord communautaire existant."""
    def __init__(self):
        super().__init__(label="Communauté", emoji="🤝", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not access_level(interaction.user):
            await interaction.response.send_message("Accès réservé au staff.", ephemeral=True)
            return
        if not interaction.guild_id or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prends d'abord ton service.", ephemeral=True)
            return
        cog = interaction.client.get_cog("CommunityHub")
        if cog is None or interaction.guild is None:
            await interaction.response.send_message("Le tableau communautaire est indisponible.", ephemeral=True)
            return
        from .community_hub import DashboardView as CommunityDashboardView
        await interaction.response.send_message(embed=cog.dashboard_embed(interaction.guild, "overview"), view=CommunityDashboardView(cog), ephemeral=True)


class NoxTVStaffButton(discord.ui.Button):
    """Navigation vers les outils NOX TV sans nouvelle commande globale."""
    def __init__(self):
        super().__init__(label="NOX TV", emoji="🎬", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Accès réservé aux responsables du serveur.", ephemeral=True)
            return
        if not interaction.guild_id or not is_on_service(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message("Prends d'abord ton service.", ephemeral=True)
            return
        cog = interaction.client.get_cog("NoxTV")
        if cog is None:
            await interaction.response.send_message("NOX TV est indisponible.", ephemeral=True)
            return
        from .nox_tv import NoxTVDashboard
        embed = horizons_embed(title="🎬 NOX TV — Tableau de bord", description="Statut, diagnostic, audit, simulation et catalogue. Aucune publication déclenchée à l'ouverture.", color=0x7764ff)
        await interaction.response.send_message(embed=embed, view=NoxTVDashboard(), ephemeral=True)


class ThematicStaffView(discord.ui.View):
    """Panneau privé en lecture seule : aucune publication ni changement d'horaire."""
    def __init__(self, owner_id: int, theme: str):
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.theme = theme
        self.choice = "overview"
        self.add_item(ThematicStaffSelect(theme))
        self.add_item(ThematicStatusButton())
        self.add_item(ThematicContentButton())
        self.add_item(ThematicChannelsButton())
        self.add_item(ThematicScheduleButton())
        self.add_item(ThematicRefreshButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if (member.id != self.owner_id or not isinstance(member, discord.Member)
                or not access_level(member) or not interaction.guild_id
                or not is_on_service(interaction.guild_id, member.id)):
            await interaction.response.send_message("Accès réservé au membre du staff en service ayant ouvert ce panneau.", ephemeral=True)
            return False
        return True


def thematic_staff_embed(guild: discord.Guild, theme: str, choice: str = "overview") -> discord.Embed:
    if theme == "publications":
        sections = {
            "overview": ("📰 Publications et routines", "Vue d'ensemble des publications. Les horaires automatiques restent inchangés."),
            "regard": ("🗞️ Le Regard du Jour", "Articles, musique, votes et bilan hebdomadaire. Consulte le forum du Regard du Jour pour les contenus publiés."),
            "routines": ("☀️ Routines HORIZONS", "Question du jour, blague, devinette, Horizon du jour et inspiration quotidienne."),
            "calendrier": ("📅 Calendrier éditorial", "Les publications programmées sont assurées par les modules existants. Ce panneau n'exécute aucun test ni envoi."),
        }
    else:
        sections = {
            "overview": ("🎉 Animations et événements", "Retrouve les animations de la communauté depuis un seul panneau."),
            "quiz": ("🧠 Quiz culturels", "Les quiz conservent leur fonctionnement et leurs commandes actuelles."),
            "defis": ("🎯 Défis collectifs", "L'animation hebdomadaire est programmée le vendredi à 19 h 30, heure de Paris."),
            "evenements": ("📆 Événements", "Consulte l'agenda, les événements et les animations du serveur."),
        }
    title, description = sections.get(choice, sections["overview"])
    embed = horizons_embed(title=title, description=description, color=discord.Color.blurple())
    import config
    channel_keys = ({"regard": ["REGARD_FORUM_CHANNEL_ID", "REGARD_ARCHIVE_CHANNEL_ID"],
                     "routines": ["DAILY_QUESTION_CHANNEL_ID", "HORIZON_DAILY_CHANNEL_ID", "JOKE_DAILY_CHANNEL_ID", "RIDDLE_DAILY_CHANNEL_ID"],
                     "calendrier": ["AGENDA_CHANNEL_ID"]} if theme == "publications" else
                    {"quiz": ["QUIZ_CHANNEL_ID"], "defis": ["COLLECTIVE_CHALLENGES_CHANNEL_ID", "MISSIONS_CHANNEL_ID"],
                     "evenements": ["AGENDA_CHANNEL_ID"]})
    ids = [getattr(config, key, None) for key in channel_keys.get(choice, [])]
    links = [f"<#{channel_id}>" for channel_id in ids if isinstance(channel_id, int) and guild.get_channel(channel_id)]
    if links:
        embed.add_field(name="Salons associés", value=" • ".join(links), inline=False)
    embed.set_footer(text="HORIZONS • Navigation staff • Aucun envoi automatique déclenché")
    return embed


class ThematicStaffSelect(discord.ui.Select):
    def __init__(self, theme: str):
        self.theme = theme
        entries = ([('overview', 'Vue générale'), ('regard', 'Regard du Jour'),
                    ('routines', 'Routines quotidiennes'), ('calendrier', 'Calendrier')]
                   if theme == 'publications' else
                   [('overview', 'Vue générale'), ('quiz', 'Quiz culturels'),
                    ('defis', 'Défis et missions'), ('evenements', 'Événements')])
        super().__init__(placeholder="Choisir une rubrique", row=0,
                         options=[discord.SelectOption(label=label, value=key) for key, label in entries])

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Panneau disponible uniquement sur HORIZONS.", ephemeral=True)
            return
        self.view.choice = self.values[0]
        await interaction.response.edit_message(embed=thematic_staff_embed(interaction.guild, self.theme, self.values[0]), view=self.view)


def thematic_status_embed(bot: commands.Bot, theme: str) -> discord.Embed:
    """Diagnostic en lecture seule des modules réellement chargés."""
    # Utiliser les noms des extensions, plus fiables que les noms de classes Cog.
    extensions = ({
        "Regard du Jour": "cogs.regard_du_jour",
        "Routines quotidiennes": "cogs.horizons_daily",
        "Calendrier éditorial": "cogs.publication_calendar",
        "Blagues": "cogs.jokes",
        "Devinettes": "cogs.riddles",
    } if theme == "publications" else {
        "Quiz": "cogs.quizzes",
        "Animations hebdomadaires": "cogs.weekly_animations",
        "Événements": "cogs.events",
        "Missions": "cogs.mission_hub",
    })
    lines = [f"{'🟢' if extension in bot.extensions else '🔴'} **{label}** — {'chargé' if extension in bot.extensions else 'non chargé'}"
             for label, extension in extensions.items()]
    embed = horizons_embed(title="🔎 État des modules — " + ("Publications" if theme == "publications" else "Animations"),
                          description="\n".join(lines), color=discord.Color.blurple())
    embed.set_footer(text="Diagnostic local • Aucune publication ou animation déclenchée")
    return embed


class ThematicStatusButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="État des modules", emoji="🔎", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=thematic_status_embed(interaction.client, self.view.theme), view=self.view)


def thematic_content_embed(theme: str) -> discord.Embed:
    """Contrôle non destructif des fichiers de contenu, sans les modifier."""
    root = Path(__file__).resolve().parent.parent / "data"
    files = ({
        "Blagues": "blagues", "Devinettes": "devinettes.json",
        "Questions": "questions_du_jour.json", "Citations": "citations.json",
        "Proverbes": "proverbes.json",
    } if theme == "publications" else {
        "Quiz culturel": "quiz_culturel.json", "Événements": "evenements.json",
        "Animations hebdomadaires": "weekly_animations.json",
    })
    lines = []
    for label, relative in files.items():
        path = root / relative
        if not path.exists():
            lines.append(f"🔴 **{label}** — introuvable (`{relative}`)")
            continue
        try:
            candidates = sorted(path.glob("*.json")) if path.is_dir() else [path]
            if not candidates:
                lines.append(f"🔴 **{label}** — aucun fichier JSON")
                continue
            valid, empty, invalid = 0, 0, []
            for candidate in candidates:
                try:
                    with candidate.open("r", encoding="utf-8-sig") as stream:
                        value = json.load(stream)
                    valid += 1
                    if not value:
                        empty += 1
                except (OSError, ValueError, UnicodeError) as exc:
                    invalid.append(f"{candidate.name} ({type(exc).__name__})")
            icon = "🔴" if invalid else "🟠" if empty else "🟢"
            summary = f"{icon} **{label}** — {valid}/{len(candidates)} JSON lisibles"
            if empty:
                summary += f", {empty} vide(s)"
            if invalid:
                summary += f"; erreurs : {', '.join(invalid[:2])}"
                if len(invalid) > 2:
                    summary += f" (+{len(invalid) - 2})"
            lines.append(summary)
        except OSError as exc:
            lines.append(f"🔴 **{label}** — accès impossible ({type(exc).__name__})")
    embed = horizons_embed(title="📂 Contrôle des contenus — " +
                          ("Publications" if theme == "publications" else "Animations"),
                          description="\n".join(lines), color=discord.Color.blurple())
    embed.set_footer(text="Lecture seule • JSON valides ≠ contenus métier vérifiés • Aucun horaire modifié")
    return embed


class ThematicContentButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Contenus JSON", emoji="📂", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=thematic_content_embed(self.view.theme), view=self.view)


def thematic_channels_embed(guild: discord.Guild, theme: str) -> discord.Embed:
    """Vérifie les salons configurés sans publier ni modifier les permissions."""
    import config
    groups = ({
        "Regard du Jour": ("REGARD_FORUM_CHANNEL_ID", "REGARD_ARCHIVE_CHANNEL_ID"),
        "Routines": ("DAILY_QUESTION_CHANNEL_ID", "HORIZON_DAILY_CHANNEL_ID", "JOKE_DAILY_CHANNEL_ID", "RIDDLE_DAILY_CHANNEL_ID"),
        "Agenda": ("AGENDA_CHANNEL_ID",),
    } if theme == "publications" else {
        "Quiz": ("QUIZ_CHANNEL_ID",),
        "Défis et missions": ("COLLECTIVE_CHALLENGES_CHANNEL_ID", "MISSIONS_CHANNEL_ID"),
        "Événements": ("AGENDA_CHANNEL_ID",),
    })
    lines = []
    for group, keys in groups.items():
        lines.append(f"**{group}**")
        for key in keys:
            raw = getattr(config, key, None)
            try:
                channel_id = int(raw) if raw else None
            except (ValueError, TypeError):
                channel_id = None
            channel = guild.get_channel(channel_id) if channel_id else None
            if channel:
                lines.append(f"🟢 `{key}` — {channel.mention}")
            elif channel_id:
                lines.append(f"🟠 `{key}` — ID {channel_id} introuvable dans le cache du serveur")
            else:
                lines.append(f"⚪ `{key}` — non configuré")
    embed = horizons_embed(
        title="📍 Salons associés — " + ("Publications" if theme == "publications" else "Animations"),
        description="\n".join(lines)[:4000], color=discord.Color.blurple(),
    )
    embed.set_footer(text="Lecture seule • Cache Discord • Aucune permission ou publication modifiée")
    return embed


class ThematicChannelsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Salons associés", emoji="📍", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Disponible uniquement sur HORIZONS.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=thematic_channels_embed(interaction.guild, self.view.theme), view=self.view,
        )


def thematic_schedule_embed(bot: commands.Bot, theme: str) -> discord.Embed:
    """Expose les prochaines exécutions connues, sans simuler une publication."""
    from config import LOCAL_TIMEZONE, DATA_DIR
    now = datetime.now(LOCAL_TIMEZONE)
    entries = ({
        "Quiz éditorial (lun/mer/sam)": ("PublicationCalendar", "daily_quiz", "quiz"),
        "Inspiration": ("PublicationCalendar", "daily_inspiration", "inspiration"),
        "Message bienveillant (mar/jeu/dim)": ("PublicationCalendar", "daily_positive_message", "messages"),
        "Événement thématique (si date correspondante)": ("PublicationCalendar", "daily_thematic_event", "evenement"),
    } if theme == "publications" else {
        "Quiz éditorial (lun/mer/sam)": ("PublicationCalendar", "daily_quiz", "quiz"),
        "Événement thématique (si date correspondante)": ("PublicationCalendar", "daily_thematic_event", "evenement"),
    })
    state = {}
    try:
        raw = json.loads((DATA_DIR / "publication_calendar_history.json").read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            state = raw.get("published_dates", {})
            if not isinstance(state, dict):
                state = {}
    except (OSError, ValueError, UnicodeError):
        pass
    # Routines additionnelles : statut en temps réel uniquement, sans historique supposé.
    extra = ({
        "Question du jour": ("Community", "daily_question", None),
        "Blague du jour": ("Jokes", "daily_joke", None),
        "Devinette du jour": ("Riddles", "daily_riddle", None),
        "Horizon du jour": ("HorizonsDaily", "horizon_of_day", None),
        "Débat hebdomadaire": ("HorizonsDaily", "weekly_debate", None),
        "Regard du Jour (vérification)": ("RegardDuJour", "scheduler", None),
    } if theme == "publications" else {
        "Animation hebdomadaire": ("WeeklyAnimations", "friday_animation", None),
        "Anniversaires": ("Birthdays", "daily_birthdays", None),
        "NOX TV (vérification horaire)": ("NoxTV", "clock", None),
    })
    entries.update(extra)
    lines = []
    for label, (cog_name, loop_name, state_key) in entries.items():
        cog = bot.get_cog(cog_name)
        loop = getattr(cog, loop_name, None) if cog else None
        if loop is None:
            status = "🔴 Module non chargé"
        elif not loop.is_running():
            status = "🟠 Boucle arrêtée"
        else:
            next_at = loop.next_iteration
            if next_at is None:
                status = "🟠 Prochaine exécution non disponible"
            else:
                local = next_at.astimezone(LOCAL_TIMEZONE)
                status = f"🟢 Prochaine exécution technique : {local:%d/%m/%Y à %H:%M}"
        last_date = state.get(state_key) if state_key else None
        last = (f"Dernière date enregistrée : {last_date}" if isinstance(last_date, str) else "Aucune date de publication enregistrée") if state_key else "Historique non exposé par ce module"
        lines.append(f"**{label}**\n{status}\n{last}")
    embed = horizons_embed(
        title="🕒 Programmation — " + ("Publications" if theme == "publications" else "Animations"),
        description="\n\n".join(lines)[:4000], color=discord.Color.blurple(),
    )
    embed.set_footer(text="Lecture seule • Exécution prévue ≠ publication garantie • Les jours sans contenu peuvent être ignorés")
    return embed


class ThematicScheduleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Programmation", emoji="🕒", style=discord.ButtonStyle.secondary, row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=thematic_schedule_embed(interaction.client, self.view.theme), view=self.view,
        )


class ThematicRefreshButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Retour à la rubrique", emoji="🔄", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Disponible uniquement sur HORIZONS.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=thematic_staff_embed(interaction.guild, self.view.theme, self.view.choice), view=self.view)


class PublicationsPanelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Publications", emoji="📰", style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Disponible sur HORIZONS uniquement.", ephemeral=True)
            return
        await interaction.response.send_message(embed=thematic_staff_embed(interaction.guild, 'publications'),
                                                view=ThematicStaffView(interaction.user.id, 'publications'), ephemeral=True)


class AnimationsPanelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Animations", emoji="🎉", style=discord.ButtonStyle.secondary, row=3)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Disponible sur HORIZONS uniquement.", ephemeral=True)
            return
        await interaction.response.send_message(embed=thematic_staff_embed(interaction.guild, 'animations'),
                                                view=ThematicStaffView(interaction.user.id, 'animations'), ephemeral=True)


class TaskFilterSelect(discord.ui.Select):
    """Filtrage privé des tâches sans commande slash supplémentaire."""
    def __init__(self):
        super().__init__(placeholder="Filtrer les tâches", options=[
            discord.SelectOption(label="Toutes", value="all"),
            discord.SelectOption(label="À faire", value="todo"),
            discord.SelectOption(label="En cours", value="doing"),
            discord.SelectOption(label="Terminées", value="done"),
        ])

    async def callback(self, interaction: discord.Interaction):
        if (not isinstance(interaction.user, discord.Member)
                or access_level(interaction.user) not in {"founder", "admin", "moderator"}
                or not interaction.guild_id
                or not is_on_service(interaction.guild_id, interaction.user.id)):
            await interaction.response.send_message("Accès réservé au staff habilité en service.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=task_embed(interaction.guild, self.values[0]), view=self.view)


class TaskFilterView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.add_item(TaskFilterSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Ce panneau appartient à un autre membre du staff.", ephemeral=True)
            return False
        return True


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
        if self.values[0] == "tasks":
            await interaction.response.send_message(embed=task_embed(interaction.guild),
                                                    view=TaskFilterView(interaction.user.id), ephemeral=True)
            return
        embed = self.cog.section_embed(interaction.guild, self.values[0], member)
        view = DashboardView(self.cog, interaction.user.id, on_service=True, level=level)
        section_select = next(item for item in view.children if isinstance(item, DashboardSelect))
        section_select.options = [discord.SelectOption(label=SECTIONS[k][0], value=k) for k in available]
        await interaction.response.edit_message(embed=embed, view=view)


class StaffDashboard(commands.Cog):
    equipe = app_commands.Group(name="equipe", description="Gestion des tâches et services de l’équipe")
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
        await interaction.response.send_message(embed=self.dashboard_embed(interaction.user, active), view=view, ephemeral=True)

    @equipe.command(name="tache_creer", description="Créer une tâche pour un membre du staff.")
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

    @equipe.command(name="tache_statut", description="Mettre à jour une tâche qui t'est attribuée (ou tâche staff si admin).")
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

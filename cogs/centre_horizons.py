"""HORIZONS V8.0 : centre personnel éphémère et navigation sans nouveaux salons."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import discord
from discord import app_commands
from discord.ext import commands
from config import LOCAL_TIMEZONE
from .embed_theme import horizons_embed
from .storage import db
from .sky_map import progress, unlocked, ORIGINS
from . import future_letters, time_capsules, collective_capsules, sky_bridges
from .coffre_horizons import snapshot as coffre_snapshot
from .centre_v86 import community_snapshot, compatible_activities, mood_summary, mood_enable, mood_clear

log = logging.getLogger(__name__)

SECTIONS = {
    "carte": ("✦ Ma Carte du Ciel", "Découvre tes 12 étoiles des Origines, puis cinq constellations thématiques. Les étoiles s’obtiennent par des actions vérifiées, progressivement intégrées aux activités."),
    "lettres": ("💌 Mes Lettres du Futur", "Écris à ton futur toi et retrouve tes lettres à leur échéance, en toute confidentialité."),
    "passerelles": ("🌉 Mes Passerelles", "Choisis volontairement tes centres d’intérêt. Découvre des affinités anonymes, sans révéler les identités ni envoyer de messages privés."),
    "coffre": ("🎁 Mon Coffre des Horizons", "Retrouve tes cartes célestes, tes étoiles, tes constellations et tes souvenirs. Ton Coffre utilise les Trésors du Ciel existants : aucune collection concurrente."),
    "capsules": ("⏳ Mes Capsules du Temps", "Confie un souvenir à ton futur toi pour 30, 90 ou 180 jours. Une question collective mensuelle est proposée si le staff l’active. Participation volontaire et modérée."),
    "activites": ("🧭 Mes activités", "Retrouve tes inscriptions, tes présences confirmées et les activités à venir, ainsi que tes saisons, ton passeport, tes jeux et tes idées."),
    "suivi": ("🌠 Ma vie HORIZONS", "Tes Cercles, tes propositions, tes missions et tes jeux, réunis dans ton Centre personnel."),
    "regard": ("📰 Le Regard du Jour", "Propose un article au staff et consulte tes points du Regard du Jour."),
    "meteo": ("💙 Ma météo privée", "Historique facultatif des sept derniers jours. Tu décides de son activation et tu peux supprimer tes données."),
}


def visit(guild_id: int, user_id: int) -> tuple[int, str | None]:
    """Enregistre une visite de manière transactionnelle, sans stocker le pseudo."""
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        row = conn.execute(
            "SELECT visits,last_visit_at FROM centre_visits WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()
        if row:
            conn.execute("UPDATE centre_visits SET visits=visits+1,last_visit_at=? WHERE guild_id=? AND user_id=?", (now, guild_id, user_id))
            return int(row["visits"]) + 1, row["last_visit_at"]
        conn.execute("INSERT INTO centre_visits(guild_id,user_id,visits,first_visit_at,last_visit_at) VALUES(?,?,1,?,?)", (guild_id,user_id,now,now))
        return 1, None


def greeting(name: str, visits: int, last_visit: str | None) -> str:
    hour = datetime.now(LOCAL_TIMEZONE).hour
    hello = "Bonjour" if 5 <= hour < 12 else "Bon après-midi" if 12 <= hour < 18 else "Bonsoir" if 18 <= hour < 23 else "Belle nuit"
    if visits == 1:
        return f"{hello}, {name} ! ✨ Bienvenue dans ton univers. Chaque aventure commence par une première étoile."
    if last_visit:
        try:
            previous = datetime.fromisoformat(last_visit)
            if (datetime.now(timezone.utc) - previous).days >= 14:
                return f"{hello}, {name} ! 🌌 Heureux de te retrouver. Reprends ton aventure à ton rythme."
        except ValueError:
            pass
    return f"{hello}, {name} ! 🌙 Ton univers HORIZONS t'attend."


def home_embed(member: discord.abc.User, visits: int, last_visit: str | None, guild_id: int) -> discord.Embed:
    # Le pseudo est limité à une taille raisonnable et n'est jamais interpolé dans du Markdown contrôlable.
    name = discord.utils.escape_markdown(member.display_name[:64])
    embed = horizons_embed(title="🌌 MON CENTRE HORIZONS", description=greeting(name, visits, last_visit))
    embed.add_field(name="✦ Ton univers", value="Un espace personnel pour explorer HORIZONS, à ton rythme.", inline=False)
    sky = progress(guild_id, member.id)
    embed.add_field(name="🌠 Ta Carte du Ciel", value=f"**{sky['origins']} / 12** étoiles des Origines découvertes. " + ("Tes cinq constellations thématiques sont ouvertes." if sky["themes_open"] else "De nouvelles étoiles seront disponibles au fil des activités."), inline=False)
    embed.add_field(name="🧭 Où commencer ?", value="Choisis une rubrique dans le menu ci-dessous. Les fonctions en préparation sont clairement signalées.", inline=False)
    embed.set_footer(text="HORIZONS • Ton espace privé • Nos différences nous rapprochent")
    return embed


def section_embed(key: str, member: discord.abc.User, guild_id: int) -> discord.Embed:
    title, description = SECTIONS[key]
    embed = horizons_embed(title=title, description=description)
    if key == "carte":
        sky = progress(guild_id, member.id)
        embed.add_field(name="✦ Constellation des Origines", value=f"**{sky['origins']} / 12** étoiles découvertes", inline=False)
        earned = unlocked(guild_id, member.id)
        discovered = [f"✦ {label}" for key, label in ORIGINS.items() if key in earned]
        waiting = [f"☆ {label}" for key, label in ORIGINS.items() if key not in earned]
        embed.add_field(name="Étoiles obtenues", value="\n".join(discovered) or "Aucune pour le moment.", inline=False)
        if waiting:
            embed.add_field(name="À découvrir", value="\n".join(waiting), inline=False)
        if sky["themes_open"]:
            for theme, count in sky["themes"].items():
                embed.add_field(name=f"✧ {theme.capitalize()}", value=f"{count} / 5 étoiles", inline=True)
        else:
            embed.add_field(name="✧ À venir", value="Exploration · Bienveillance · Créativité · Rencontres · Aventure", inline=False)
    if key == "passerelles":
        info = sky_bridges.profile(guild_id,member.id)
        if not info['enabled']:
            embed.add_field(name="🌉 Passerelles désactivées",value="Aucun profil d'affinité n'est enregistré. Choisis jusqu'à cinq centres d'intérêt pour participer librement.",inline=False)
        else:
            labels = [sky_bridges.INTERESTS[k] for k in info['interests']]
            embed.add_field(name="Tes centres d'intérêt",value=" · ".join(labels),inline=False)
            matches = sky_bridges.suggestions(guild_id,member.id)
            embed.add_field(name="Intérêts partagés dans HORIZONS",value="\n".join(f"{sky_bridges.INTERESTS[k]} : {n} autre(s) membre(s) volontaire(s)" for k,n in matches) or "Pas encore de centres d'intérêt partagés. Reviens plus tard !",inline=False)
            pending = sky_bridges.inbox(guild_id,member.id)
            links = sky_bridges.connections(guild_id,member.id)
            embed.add_field(name="Invitations reçues",value=f"{len(pending)} invitation(s) anonyme(s) en attente. Réponds avec le menu ci-dessous." if pending else "Aucune invitation en attente.",inline=False)
            embed.add_field(name="Connexions acceptées",value="\n".join(f"<@{uid}>" for uid in links) or "Aucune connexion pour le moment.",inline=False)
            embed.add_field(name="Fonctionnement",value="Une invitation reste anonyme jusqu'à ton acceptation. Aucun MP automatique. Les deux personnes peuvent quitter les Passerelles à tout moment.",inline=False)
            embed.add_field(name="Confidentialité",value="Aucune identité révélée avant acceptation réciproque. Aucun MP automatique. Tu peux effacer ton profil à tout moment.",inline=False)
    if key == "coffre":
        box = coffre_snapshot(guild_id, member.id)
        daily = "🌟 Ta carte quotidienne est disponible" if box["daily_available"] else "🌙 Ta carte quotidienne a déjà été utilisée"
        if box["gift_cards"]:
            daily += f"\n🎟️ {box['gift_cards']} carte(s) offerte(s) disponible(s)"
        embed.add_field(name="🎟️ Tes cartes", value=daily, inline=False)
        embed.add_field(name="✨ Ta collection", value=(
            f"**{box['stars']} / {box['total_stars']}** étoiles célestes\n"
            f"**{box['dust']}** poussières · **{box['fragments']}** fragments\n"
            f"**{len(box['constellations'])} / 5** constellations réunies"
        ), inline=False)
        embed.add_field(name="🌌 Tes constellations", value="\n".join(box["constellations"]) or "Ton ciel se construit à ton rythme.", inline=False)
        embed.add_field(name="🎁 Tes souvenirs", value=f"**{box['memories']}** souvenir(s) céleste(s) débloqué(s).", inline=False)
        embed.add_field(name="Pour découvrir une carte", value="Rends-toi dans **🌌・trésors-du-ciel** et utilise le panneau interactif ou `/gratter`. Les cartes restent dans leur salon d'origine.", inline=False)
    if key == "activites":
        with db() as conn:
            rows = conn.execute("""SELECT e.id,e.title,e.starts_at,r.response,
                CASE WHEN a.user_id IS NULL THEN 0 ELSE 1 END AS attended
                FROM event_rsvps r JOIN events e ON e.id=r.event_id
                LEFT JOIN event_attendance a ON a.event_id=e.id AND a.user_id=r.user_id
                WHERE e.guild_id=? AND r.user_id=?
                ORDER BY e.starts_at DESC LIMIT 8""", (guild_id,member.id)).fetchall()
            confirmed = conn.execute("""SELECT COUNT(*) FROM event_attendance a
                JOIN events e ON e.id=a.event_id WHERE e.guild_id=? AND a.user_id=?""",
                (guild_id,member.id)).fetchone()[0]
        labels = {"yes":"Inscrit·e", "maybe":"Peut-être", "no":"Désinscrit·e"}
        lines = [f"#{r['id']} · {discord.utils.escape_markdown(r['title'][:55])} · "
                 + ("✓ Présence confirmée" if r['attended'] else labels.get(r['response'],"Réponse enregistrée"))
                 for r in rows]
        embed.add_field(name="Tes derniers événements", value="\n".join(lines) or "Aucune inscription pour le moment.", inline=False)
        embed.add_field(name="Participations confirmées", value=f"**{confirmed}** présence(s) confirmée(s) par un organisateur ou le staff.", inline=False)
        embed.add_field(name="À découvrir", value="Utilise `/evenements` pour les prochains rendez-vous, `/mon_passeport` pour les missions et `/mes_idees` pour tes propositions.", inline=False)
    if key == "suivi":
        info = community_snapshot(guild_id, member.id)
        embed.add_field(name="🌙 Tes Cercles", value="\n".join(info['circles']) or "Aucun Cercle suivi pour le moment.", inline=False)
        embed.add_field(name="💡 Tes idées", value="\n".join(info['ideas']) or "Aucune proposition pour le moment.", inline=False)
        embed.add_field(name="🧭 Ton passeport", value=info['missions'], inline=False)
        embed.add_field(name="🎮 Ton Arcade", value=info['arcade'], inline=False)
        embed.add_field(name="Pour aller plus loin", value="Utilise le menu « Ma progression » ci-dessous pour ton rang, ton parcours et tes badges. `/mon_passeport`, `/jeux` et `/mes_idees` restent disponibles.", inline=False)
    if key == "meteo":
        info = mood_summary(guild_id, member.id)
        if info['enabled']:
            embed.add_field(name="Tes sept derniers jours", value="\n".join(info['entries']) or "Aucune météo enregistrée sur cette période.", inline=False)
            embed.add_field(name="Confidentialité", value="Cet historique est facultatif et visible uniquement dans ton Centre. Tu peux l'effacer ci-dessous.", inline=False)
        else:
            embed.add_field(name="Historique désactivé", value="Tu peux activer la consultation privée de ta météo. Rien ne sera utilisé pour les étoiles, les affinités ou les classements.", inline=False)
    if key == "passerelles":
        ideas = compatible_activities(guild_id, member.id)
        if ideas:
            embed.add_field(name="🧭 À découvrir selon tes intérêts", value="\n".join(ideas), inline=False)
    if key == "lettres":
        letters = future_letters.list_letters(guild_id, member.id)
        now = future_letters.now_utc().isoformat()
        lines = [f"Lettre n°{r['id']} · " + ("💌 Prête à ouvrir" if r['due_at'] <= now else "🔒 À retrouver le " + r['due_at'][:10]) for r in letters]
        embed.add_field(name="Tes lettres", value="\n".join(lines[:15]) or "Aucune lettre pour le moment.", inline=False)
        embed.add_field(name="Confidentialité", value="Tes lettres sont visibles uniquement par toi. Tu peux les supprimer à tout moment.", inline=False)
    if key == "capsules":
        capsules = time_capsules.list_capsules(guild_id, member.id)
        now = time_capsules.now_utc().isoformat()
        lines = [f"Capsule n°{r['id']} · " + ("⏳ Prête à ouvrir" if r['due_at'] <= now else "🔒 À retrouver le " + r['due_at'][:10]) for r in capsules]
        embed.add_field(name="Tes capsules personnelles", value="\n".join(lines[:15]) or "Aucune capsule pour le moment.", inline=False)
        embed.add_field(name="Ton souvenir, ton choix", value="Cinq capsules non ouvertes maximum. Tu peux les supprimer quand tu le souhaites. Aucune publication publique ni envoi automatique.", inline=False)
        q = collective_capsules.current_question(guild_id)
        embed.add_field(name="🌌 Question collective du mois", value=q['question'] if q else "Aucune question ouverte ce mois-ci.", inline=False)
        answers = collective_capsules.my_answers(guild_id, member.id)
        if answers:
            embed.add_field(name="Tes contributions collectives", value="\n".join(f"N°{a['id']} · {a['month_key']} · {a['status']}" for a in answers[:8]), inline=False)
    embed.add_field(name="Ton Centre", value="Utilise le bouton « Retour au Centre » pour revenir à l'accueil.", inline=False)
    return embed


class CentreSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=title.replace("✦ ", "").replace("💌 ", "").replace("🌉 ", "").replace("🎁 ", "").replace("⏳ ", "").replace("🧭 ", ""), value=key, description="Découvrir cette rubrique") for key, (title, _) in SECTIONS.items()]
        super().__init__(placeholder="Explorer mon univers…", options=options, custom_id="horizons_v8_centre_select")

    async def callback(self, interaction: discord.Interaction):
        view: CentreView = self.view
        view.selected = self.values[0]
        view.update_section_controls(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(embed=section_embed(view.selected, interaction.user, interaction.guild_id), view=view)


class LetterModal(discord.ui.Modal, title="💌 Lettre à mon futur moi"):
    message = discord.ui.TextInput(label="Ton message personnel", style=discord.TextStyle.paragraph, min_length=1, max_length=1000, placeholder="Cher moi du futur…")
    def __init__(self, days: int):
        super().__init__()
        self.days = days

    async def on_submit(self, interaction: discord.Interaction):
        try:
            future_letters.create(interaction.guild_id, interaction.user.id, str(self.message), self.days)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception:
            log.exception("Impossible d'enregistrer une lettre du Futur")
            await interaction.response.send_message("Impossible d'enregistrer ta lettre pour le moment.", ephemeral=True)
            return
        await interaction.response.send_message(f"💌 Ta lettre est conservée. Retrouve-la dans {self.days} jours via `/centre` → Mes Lettres du Futur.", ephemeral=True)


class LetterDurationSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Écrire une lettre pour…", options=[discord.SelectOption(label=f"Dans {d} jours", value=str(d)) for d in future_letters.DURATIONS], row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(LetterModal(int(self.values[0])))


class LetterManageSelect(discord.ui.Select):
    def __init__(self, letters, *, action: str):
        self.action = action
        options = [discord.SelectOption(label=f"Lettre n°{r['id']}", value=str(r['id'])) for r in letters[:25]]
        super().__init__(placeholder="Ouvrir une lettre" if action == "open" else "Supprimer une lettre", options=options, row=3 if action == "open" else 4)

    async def callback(self, interaction: discord.Interaction):
        letter_id = int(self.values[0])
        if self.action == "open":
            content = future_letters.open_letter(interaction.guild_id, interaction.user.id, letter_id)
            if content is None:
                await interaction.response.send_message("Cette lettre n'est pas encore disponible ou n'existe plus.", ephemeral=True)
            else:
                await interaction.response.send_message("💌 **Ta lettre du Futur**\n" + discord.utils.escape_mentions(content), ephemeral=True)
        else:
            deleted = future_letters.delete_letter(interaction.guild_id, interaction.user.id, letter_id)
            await interaction.response.send_message("🗑️ Lettre supprimée." if deleted else "Cette lettre n'existe plus.", ephemeral=True)


class CapsuleModal(discord.ui.Modal, title="⏳ Capsule à mon futur moi"):
    message = discord.ui.TextInput(label="Ton souvenir personnel", style=discord.TextStyle.paragraph, min_length=1, max_length=1000, placeholder="Un souvenir, un souhait, une découverte…")

    def __init__(self, days: int):
        super().__init__()
        self.days = days

    async def on_submit(self, interaction: discord.Interaction):
        try:
            time_capsules.create(interaction.guild_id, interaction.user.id, str(self.message), self.days)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception:
            log.exception("Impossible de créer une capsule personnelle")
            await interaction.response.send_message("Impossible d'enregistrer ta capsule pour le moment.", ephemeral=True)
            return
        await interaction.response.send_message(f"⏳ Ton souvenir est conservé. Retrouve-le dans {self.days} jours depuis `/centre` → Mes Capsules du Temps.", ephemeral=True)


class CapsuleDurationSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Créer une capsule pour…", options=[discord.SelectOption(label=f"Dans {d} jours", value=str(d)) for d in time_capsules.DURATIONS], row=2)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CapsuleModal(int(self.values[0])))


class CapsuleManageSelect(discord.ui.Select):
    def __init__(self, capsules, *, action: str):
        self.action = action
        super().__init__(placeholder="Ouvrir une capsule" if action == "open" else "Supprimer une capsule", options=[discord.SelectOption(label=f"Capsule n°{r['id']}", value=str(r['id'])) for r in capsules[:25]], row=3 if action == "open" else 4)

    async def callback(self, interaction: discord.Interaction):
        capsule_id = int(self.values[0])
        if self.action == "open":
            content = time_capsules.open_capsule(interaction.guild_id, interaction.user.id, capsule_id)
            await interaction.response.send_message("⏳ **Ta Capsule du Temps**\n" + discord.utils.escape_mentions(content) if content is not None else "Cette capsule n'est pas encore disponible ou n'existe plus.", ephemeral=True)
        else:
            deleted = time_capsules.delete_capsule(interaction.guild_id, interaction.user.id, capsule_id)
            await interaction.response.send_message("🗑️ Capsule supprimée." if deleted else "Cette capsule n'existe plus.", ephemeral=True)


class CollectiveCapsuleModal(discord.ui.Modal, title="🌌 Capsule collective du mois"):
    message = discord.ui.TextInput(label="Ta réponse volontaire", style=discord.TextStyle.paragraph, min_length=1, max_length=700)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            collective_capsules.submit(interaction.guild_id, interaction.user.id, str(self.message))
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception:
            log.exception("Échec de création d'une capsule collective")
            await interaction.response.send_message("Impossible d'enregistrer ta réponse pour le moment.", ephemeral=True)
            return
        await interaction.response.send_message("🌌 Ta contribution est en attente de modération. Elle ne sera visible collectivement qu'après validation et ouverture de la capsule, dans au moins 90 jours. Tu peux la retirer à tout moment.", ephemeral=True)


class CollectiveCapsuleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Répondre à la question", emoji="🌌", style=discord.ButtonStyle.primary, row=1)

    async def callback(self, interaction: discord.Interaction):
        if not collective_capsules.current_question(interaction.guild_id):
            await interaction.response.send_message("Aucune question collective ouverte ce mois-ci.", ephemeral=True)
            return
        await interaction.response.send_modal(CollectiveCapsuleModal())


class CollectiveWithdrawSelect(discord.ui.Select):
    def __init__(self, answers):
        super().__init__(placeholder="Retirer une contribution collective", options=[discord.SelectOption(label=f"Contribution n°{a['id']} ({a['month_key']})",value=str(a['id'])) for a in answers[:25]],row=1)

    async def callback(self, interaction: discord.Interaction):
        removed = collective_capsules.withdraw(interaction.guild_id,interaction.user.id,int(self.values[0]))
        await interaction.response.send_message("Contribution retirée définitivement." if removed else "Contribution introuvable.",ephemeral=True)


class CollectiveWithdrawButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Retirer une contribution", emoji="🗑️", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        answers = collective_capsules.my_answers(interaction.guild_id, interaction.user.id)
        if not answers:
            await interaction.response.send_message("Tu n’as aucune contribution à retirer.", ephemeral=True)
            return
        view = discord.ui.View(timeout=180)
        view.add_item(CollectiveWithdrawSelect(answers))
        await interaction.response.send_message("Choisis la contribution à retirer définitivement :", view=view, ephemeral=True)


class BridgeInterestsSelect(discord.ui.Select):
    def __init__(self, chosen):
        super().__init__(placeholder="Choisir mes centres d'intérêt (1 à 5)",min_values=1,max_values=5,row=2,
            options=[discord.SelectOption(label=label,value=key,default=key in chosen) for key,label in sky_bridges.INTERESTS.items()])

    async def callback(self, interaction: discord.Interaction):
        try:
            sky_bridges.save(interaction.guild_id,interaction.user.id,self.values)
        except ValueError as exc:
            await interaction.response.send_message(str(exc),ephemeral=True)
            return
        view = self.view
        view.update_section_controls(interaction.guild_id,interaction.user.id)
        await interaction.response.edit_message(embed=section_embed('passerelles',interaction.user,interaction.guild_id),view=view)

class BridgeLeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Quitter les Passerelles",emoji="🔒",style=discord.ButtonStyle.danger,row=3)

    async def callback(self, interaction: discord.Interaction):
        sky_bridges.disable(interaction.guild_id,interaction.user.id)
        view=self.view
        view.update_section_controls(interaction.guild_id,interaction.user.id)
        await interaction.response.edit_message(embed=section_embed('passerelles',interaction.user,interaction.guild_id),view=view)


class BridgeInviteButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Proposer une Passerelle",emoji="🌉",style=discord.ButtonStyle.primary,row=3)
    async def callback(self, interaction: discord.Interaction):
        try:
            sent=sky_bridges.request_connection(interaction.guild_id,interaction.user.id)
            message="Invitation anonyme déposée. La personne pourra la consulter depuis son Centre." if sent else "Aucun profil compatible disponible pour le moment."
        except ValueError as exc:
            message=str(exc)
        await interaction.response.send_message(message,ephemeral=True)

class BridgeCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Annuler mon invitation",style=discord.ButtonStyle.secondary,row=3)
    async def callback(self, interaction: discord.Interaction):
        count=sky_bridges.cancel_pending(interaction.guild_id,interaction.user.id)
        await interaction.response.send_message("Invitation annulée." if count else "Aucune invitation à annuler.",ephemeral=True)

class BridgeInboxSelect(discord.ui.Select):
    def __init__(self, requests):
        opts=[]
        for r in requests[:10]:
            opts.append(discord.SelectOption(label=f"Accepter l'invitation n°{r['id']}",value=f"yes:{r['id']}"))
            opts.append(discord.SelectOption(label=f"Refuser l'invitation n°{r['id']}",value=f"no:{r['id']}"))
        super().__init__(placeholder="Répondre à une invitation anonyme",options=opts[:25],row=4)
    async def callback(self, interaction: discord.Interaction):
        answer,number=self.values[0].split(':')
        try:
            ok=sky_bridges.decide(interaction.guild_id,interaction.user.id,int(number),answer=='yes')
        except ValueError as exc:
            await interaction.response.send_message(str(exc),ephemeral=True)
            return
        view=self.view
        view.update_section_controls(interaction.guild_id,interaction.user.id)
        await interaction.response.edit_message(embed=section_embed('passerelles',interaction.user,interaction.guild_id),view=view)
        if not ok:
            await interaction.followup.send("Cette invitation n'est plus disponible.",ephemeral=True)


class MoodActivateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Activer mon historique", style=discord.ButtonStyle.secondary, emoji="💙", row=2)
    async def callback(self, interaction: discord.Interaction):
        mood_enable(interaction.guild_id, interaction.user.id)
        view = self.view
        view.update_section_controls(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(embed=section_embed("meteo", interaction.user, interaction.guild_id), view=view)


class MoodEraseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Effacer mes météos", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def callback(self, interaction: discord.Interaction):
        # Confirmation explicite : un clic accidentel ne supprime aucune donnée.
        await interaction.response.send_message(
            "Cette action supprimera toutes tes météos enregistrées sur ce serveur. Confirmer ?",
            view=MoodEraseConfirm(interaction.user.id), ephemeral=True)


class MoodEraseConfirm(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=90)
        self.owner_id = owner_id
    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Action personnelle uniquement.", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Oui, supprimer définitivement", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        mood_clear(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(content="Tes météos et ton choix d'activation ont été effacés.", view=None)
    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(content="Suppression annulée.", view=None)


class SeasonActionSelect(discord.ui.Select):
    """Les actions de saison réunies dans le Centre, sans commande slash supplémentaire."""
    def __init__(self):
        super().__init__(placeholder="🌅 Saison : choisir une action…", row=2, options=[
            discord.SelectOption(label="Découvrir la saison", value="saison", emoji="🌅"),
            discord.SelectOption(label="Rejoindre la saison", value="rejoindre_saison", emoji="🤝"),
            discord.SelectOption(label="Voir mes étapes", value="missions_saison", emoji="🧭"),
            discord.SelectOption(label="Valider une étape", value="valider", emoji="✅"),
            discord.SelectOption(label="Mes distinctions", value="mes_recompenses_saison", emoji="🏅"),
        ])

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Seasons")
        if cog is None:
            await interaction.response.send_message("Les saisons sont temporairement indisponibles.", ephemeral=True)
            return
        action = self.values[0]
        if action == "valider":
            from .mission_hub import MissionSteps
            await interaction.response.send_message("Quelle étape as-tu accomplie ?", view=MissionSteps("Seasons", "valider_etape_saison", "etape"), ephemeral=True)
        elif action == "saison":
            await cog.saison.callback(cog, interaction)
        else:
            await getattr(cog, action)(interaction)


class ActivityFunSelect(discord.ui.Select):
    """Jeux rapides accessibles depuis /centre → Activités."""
    def __init__(self):
        super().__init__(placeholder="🎲 Jeux rapides : choisir…", row=3, options=[
            discord.SelectOption(label="Une blague", value="blague", emoji="😄"),
            discord.SelectOption(label="Une devinette", value="devinette", emoji="🧩"),
        ])

    async def callback(self, interaction: discord.Interaction):
        name = "Jokes" if self.values[0] == "blague" else "Riddles"
        cog = interaction.client.get_cog(name)
        if cog is None:
            await interaction.response.send_message("Cette activité est momentanément indisponible.", ephemeral=True)
            return
        await getattr(cog, self.values[0])(interaction)


class ProgressionSelect(discord.ui.Select):
    """Trois consultations de progression réunies dans /centre → Ma vie."""
    def __init__(self):
        super().__init__(placeholder="🌱 Ma progression : consulter…", row=2, options=[
            discord.SelectOption(label="Mon rang honorifique", value="rang", emoji="🌱"),
            discord.SelectOption(label="Parcours des horizons", value="parcours", emoji="🧭"),
            discord.SelectOption(label="Mes badges du parcours", value="badges", emoji="🏅"),
        ])

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        cog_name = "CommunityRanks" if action == "rang" else "HorizonsPath"
        method = {"rang": "mon_parcours", "parcours": "parcours", "badges": "parcours_badges"}[action]
        cog = interaction.client.get_cog(cog_name)
        if cog is None:
            await interaction.response.send_message("Le suivi de progression est momentanément indisponible.", ephemeral=True)
            return
        handler = getattr(cog, method)
        if isinstance(handler, app_commands.Command):
            await handler.callback(cog, interaction)
        else:
            await handler(interaction)



class RegardMemberModal(discord.ui.Modal, title="Proposer au Regard du Jour"):
    titre = discord.ui.TextInput(label="Titre (12 à 170 caractères)", min_length=12, max_length=170)
    lien = discord.ui.TextInput(label="Lien HTTPS", max_length=900)
    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("RegardDuJour")
        if cog is None:
            return await interaction.response.send_message("Le Regard du Jour est indisponible.", ephemeral=True)
        await type(cog).proposer.callback(cog, interaction, str(self.titre.value), str(self.lien.value), False)

class RegardMemberButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Proposer un article", emoji="📰", style=discord.ButtonStyle.primary, row=2)
    async def callback(self, interaction):
        await interaction.response.send_modal(RegardMemberModal())

class RegardPointsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Mes points Regard", emoji="🌟", style=discord.ButtonStyle.secondary, row=2)
    async def callback(self, interaction):
        cog = interaction.client.get_cog("RegardDuJour")
        if cog is None:
            return await interaction.response.send_message("Le Regard du Jour est indisponible.", ephemeral=True)
        await type(cog).points.callback(cog, interaction)

class CentreView(discord.ui.View):
    def __init__(self, owner_id: int, visits: int, last_visit: str | None):
        super().__init__(timeout=600)
        self.owner_id = owner_id
        self.visits = visits
        self.last_visit = last_visit
        self.selected: str | None = None
        self.add_item(CentreSelect())
        self.update_section_controls(None, None)

    def update_section_controls(self, guild_id: int | None, user_id: int | None):
        for item in list(self.children):
            if isinstance(item, (LetterDurationSelect, LetterManageSelect, CapsuleDurationSelect, CapsuleManageSelect, CollectiveCapsuleButton, CollectiveWithdrawButton, BridgeInterestsSelect, BridgeLeaveButton, BridgeInviteButton, BridgeCancelButton, BridgeInboxSelect, MoodActivateButton, MoodEraseButton, RegardMemberButton, RegardPointsButton, SeasonActionSelect, ActivityFunSelect, ProgressionSelect)):
                self.remove_item(item)
        if guild_id is None:
            return
        if self.selected == "activites":
            self.add_item(SeasonActionSelect())
            self.add_item(ActivityFunSelect())
            return
        if self.selected == "suivi":
            self.add_item(ProgressionSelect())
            return
        if self.selected == "regard":
            self.add_item(RegardMemberButton())
            self.add_item(RegardPointsButton())
            return
        if self.selected == "meteo":
            self.add_item(MoodActivateButton())
            self.add_item(MoodEraseButton())
            return
        if self.selected == "passerelles":
            current = sky_bridges.profile(guild_id,user_id)
            self.add_item(BridgeInterestsSelect(current['interests']))
            if current['enabled']:
                self.add_item(BridgeLeaveButton())
                self.add_item(BridgeInviteButton())
                self.add_item(BridgeCancelButton())
                requests=sky_bridges.inbox(guild_id,user_id)
                if requests:
                    self.add_item(BridgeInboxSelect(requests))
            return
        if self.selected == "capsules":
            if collective_capsules.current_question(guild_id):
                self.add_item(CollectiveCapsuleButton())
            answers = collective_capsules.my_answers(guild_id,user_id)
            if answers:
                self.add_item(CollectiveWithdrawButton())
            self.add_item(CapsuleDurationSelect())
            capsules = time_capsules.list_capsules(guild_id, user_id)
            ready = [r for r in capsules if r['due_at'] <= time_capsules.now_utc().isoformat()]
            if ready:
                self.add_item(CapsuleManageSelect(ready, action="open"))
            if capsules:
                self.add_item(CapsuleManageSelect(capsules, action="delete"))
            return
        if self.selected != "lettres":
            return
        self.add_item(LetterDurationSelect())
        letters = future_letters.list_letters(guild_id, user_id)
        ready = [r for r in letters if r['due_at'] <= future_letters.now_utc().isoformat()]
        if ready:
            self.add_item(LetterManageSelect(ready, action="open"))
        if letters:
            self.add_item(LetterManageSelect(letters, action="delete"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 Ce Centre appartient à un autre membre. Ouvre le tien avec `/centre`.", ephemeral=True)
            return False
        return True

    # Accès directs pour les membres : aucune nouvelle commande slash.
    async def open_shortcut(self, interaction: discord.Interaction, key: str):
        self.selected = key
        self.update_section_controls(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(
            embed=section_embed(key, interaction.user, interaction.guild_id), view=self
        )

    @discord.ui.button(label="Activités", style=discord.ButtonStyle.primary, emoji="🧭", row=1)
    async def activities_shortcut(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shortcut(interaction, "activites")

    @discord.ui.button(label="Ma vie", style=discord.ButtonStyle.primary, emoji="🌠", row=1)
    async def journey_shortcut(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shortcut(interaction, "suivi")

    @discord.ui.button(label="Mon coffre", style=discord.ButtonStyle.primary, emoji="🎁", row=1)
    async def treasures_shortcut(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.open_shortcut(interaction, "coffre")

    @discord.ui.button(label="Retour au Centre", style=discord.ButtonStyle.secondary, emoji="🏠", row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.selected = None
        self.update_section_controls(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(embed=home_embed(interaction.user, self.visits, self.last_visit, interaction.guild_id), view=self)

    @discord.ui.button(label="Actualiser", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.update_section_controls(interaction.guild_id, interaction.user.id)
        embed = section_embed(self.selected, interaction.user, interaction.guild_id) if self.selected else home_embed(interaction.user, self.visits, self.last_visit, interaction.guild_id)
        await interaction.response.edit_message(embed=embed, view=self)


class CentreHorizons(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Action migrée vers /dashboard → Capsules staff.
    async def capsule_question(self, interaction: discord.Interaction, question: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Permission de gestion du serveur nécessaire.",ephemeral=True)
            return
        try:
            collective_capsules.set_question(interaction.guild_id,interaction.user.id,question)
        except ValueError as exc:
            await interaction.response.send_message(str(exc),ephemeral=True)
            return
        await interaction.response.send_message("🌌 Question du mois activée dans /centre.",ephemeral=True)

    # Action migrée vers /dashboard → Capsules staff.
    async def capsule_moderer(self, interaction: discord.Interaction, numero: int, decision: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Permission de gestion du serveur nécessaire.",ephemeral=True)
            return
        ok = collective_capsules.moderate(interaction.guild_id,interaction.user.id,numero,decision=="approve")
        await interaction.response.send_message("Décision enregistrée." if ok else "Contribution absente ou déjà traitée.",ephemeral=True)

    # Action migrée vers /dashboard → Capsules staff.
    async def capsule_attente(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("Permission de gestion du serveur nécessaire.",ephemeral=True)
            return
        rows = collective_capsules.pending(interaction.guild_id)
        message = "\n\n".join(f"**N°{r['id']}** · membre {r['user_id']}\n{discord.utils.escape_mentions(r['content'][:700])}" for r in rows) or "Aucune contribution en attente."
        await interaction.response.send_message(message[:1900],ephemeral=True)

    @app_commands.command(name="capsule_reveler", description="Consulter les contributions approuvées d'un mois arrivé à échéance.")
    @app_commands.guild_only()
    async def capsule_reveler(self, interaction: discord.Interaction, mois: str):
        import re
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])",mois):
            await interaction.response.send_message("Indique un mois au format AAAA-MM.",ephemeral=True)
            return
        rows = collective_capsules.revealed(interaction.guild_id,mois)
        content = "\n\n".join(f"✦ {discord.utils.escape_mentions(r['content'])}" for r in rows) or "Aucune contribution approuvée disponible pour ce mois, ou capsule encore fermée."
        await interaction.response.send_message(content[:1900],ephemeral=True)

    @app_commands.command(name="centre", description="Ouvrir ton Centre HORIZONS personnel et interactif.")
    @app_commands.guild_only()
    async def centre(self, interaction: discord.Interaction):
        if interaction.guild_id is None:
            await interaction.response.send_message("Le Centre est disponible uniquement sur HORIZONS.", ephemeral=True)
            return
        # Acquitter avant les accès SQLite : Discord impose une réponse rapide.
        await interaction.response.defer(ephemeral=True)
        try:
            visits, last_visit = visit(interaction.guild_id, interaction.user.id)
            from .sky_map import grant
            grant(interaction.guild_id, interaction.user.id, "origins.centre")
        except Exception:
            log.exception("Impossible d'ouvrir le Centre pour le membre %s", interaction.user.id)
            await interaction.followup.send("Le Centre est momentanément indisponible. Réessaie dans un instant.", ephemeral=True)
            return
        await interaction.followup.send(embed=home_embed(interaction.user, visits, last_visit, interaction.guild_id), view=CentreView(interaction.user.id, visits, last_visit), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CentreHorizons(bot))

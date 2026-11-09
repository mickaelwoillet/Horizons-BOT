"""Guides d'accueil HORIZONS : publications hebdomadaires et présentation permanente."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

from datetime import datetime
from typing import Iterable

import discord
from discord.ext import commands, tasks

from config import (
    GUILD_ID, LOCAL_TIMEZONE, BIRTHDAY_CHANNEL_ID, INTRO_CHANNEL_ID,
    ANONYMOUS_CHANNEL_ID, CONFESSION_CHANNEL_ID, SPIRIT_CHANNEL_ID,
    STAFF_COMMANDS_CHANNEL_ID, FIND_PARTNER_CHANNEL_ID,
    COLLECTIVE_CHALLENGES_CHANNEL_ID,
)
from .storage import db

FOOTER_PREFIX = "HORIZONS-GUIDE:"

# Les descriptions et les commandes sont tirées des extensions réellement chargées.
STAFF_ONLY = {
    "annonce", "alerte_equipe", "actualiser_rangs", "avertir", "avertissements",
    "retirer_avertissement", "timeout", "untimeout", "expulser", "bannir",
    "debannir", "purger", "note_membre", "evenement_creer", "evenement_fermer",
    "concours_creer", "concours_annuler", "quiz_lancer", "quiz_arreter", "creer_defi",
    "dashboard", "tache_creer", "taches", "tache_statut", "service", "publier_guides_cercles",
}
CATEGORY = {
    "ping": "⚙️ Outils généraux", "aide": "⚙️ Outils généraux", "profil": "⚙️ Outils généraux",
    "serveur": "⚙️ Outils généraux", "proposer": "⚙️ Outils généraux", "presentation": "⚙️ Outils généraux",
    "anniversaire_supprimer": "🎂 Anniversaires",
    "question_du_jour": "💬 Vie communautaire", "compliment": "💬 Vie communautaire",
    "blague": "🎲 Jeux et détente", "devinette": "🎲 Jeux et détente",
    "quiz_lancer": "🎲 Jeux et détente", "quiz_arreter": "🎲 Jeux et détente",
    "mon_passeport": "🧭 Expériences HORIZONS", "valider_mission": "🧭 Expériences HORIZONS",
    "chercher": "🧭 Expériences HORIZONS", "defi_collectif": "🧭 Expériences HORIZONS",
    "rejoindre_defi": "🧭 Expériences HORIZONS", "creer_defi": "🧭 Expériences HORIZONS",
    "mon_parcours": "🌱 Progression", "actualiser_rangs": "🌱 Progression",
    "evenement_creer": "🎉 Événements et concours", "evenements": "🎉 Événements et concours",
    "evenement_fermer": "🎉 Événements et concours", "concours_creer": "🎉 Événements et concours",
    "concours_annuler": "🎉 Événements et concours", "proposer": "💡 Suggestions",
    "signaler": "🛡️ Aide et modération", "alerte_equipe": "🛡️ Aide et modération",
    "message_anonyme": "🛡️ Aide et modération", "ticket_ouvrir": "🎫 Tickets",
    "ticket_fermer": "🎫 Tickets", "avertir": "🛡️ Modération (équipe)",
    "avertissements": "🛡️ Modération (équipe)", "retirer_avertissement": "🛡️ Modération (équipe)",
    "timeout": "🛡️ Modération (équipe)", "untimeout": "🛡️ Modération (équipe)",
    "expulser": "🛡️ Modération (équipe)", "bannir": "🛡️ Modération (équipe)",
    "debannir": "🛡️ Modération (équipe)", "purger": "🛡️ Modération (équipe)",
    "note_membre": "🛡️ Modération (équipe)", "annonce": "📣 Communication (équipe)",
    "dashboard": "🧭 Centre de commandement staff", "service": "🧭 Centre de commandement staff",
    "tache_creer": "📋 Organisation du staff", "taches": "📋 Organisation du staff",
    "tache_statut": "📋 Organisation du staff", "traduire": "🌍 Utilitaires", "publier_guides_cercles": "🧭 Organisation communautaire (équipe)",
}

class ServerGuides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        with db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS guide_publications (
                guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
                guide_key TEXT NOT NULL, period_key TEXT NOT NULL,
                message_id INTEGER, published_at TEXT NOT NULL,
                PRIMARY KEY(guild_id, channel_id, guide_key, period_key)
            )""")
        self.publish_guides.start()

    def cog_unload(self):
        self.publish_guides.cancel()

    @staticmethod
    def week_key() -> str:
        return datetime.now(LOCAL_TIMEZONE).strftime("%G-W%V")

    async def resolve_channel(self, channel_id: int | None):
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return None
        return channel if isinstance(channel, (discord.TextChannel, discord.Thread)) else None

    async def already_posted(self, channel, guide_key: str, period_key: str) -> bool:
        with db() as conn:
            found = conn.execute(
                "SELECT 1 FROM guide_publications WHERE guild_id=? AND channel_id=? AND guide_key=? AND period_key=?",
                (channel.guild.id, channel.id, guide_key, period_key),
            ).fetchone()
        if found:
            return True
        # Protection supplémentaire contre les doublons si la base a été restaurée.
        marker = f"{FOOTER_PREFIX}{guide_key}:{period_key}"
        try:
            async for message in channel.history(limit=60):
                if message.author.id == self.bot.user.id and any(
                    embed.footer and marker in (embed.footer.text or "") for embed in message.embeds
                ):
                    self.record_post(channel, guide_key, period_key, message.id)
                    return True
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass
        return False

    @staticmethod
    def record_post(channel, guide_key: str, period_key: str, message_id: int):
        with db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO guide_publications(guild_id,channel_id,guide_key,period_key,message_id,published_at) VALUES(?,?,?,?,?,?)",
                (channel.guild.id, channel.id, guide_key, period_key, message_id, datetime.now(LOCAL_TIMEZONE).isoformat()),
            )

    async def publish(self, channel_id: int | None, guide_key: str, period_key: str, embed: discord.Embed):
        channel = await self.resolve_channel(channel_id)
        if channel is None:
            return
        marker = f"{FOOTER_PREFIX}{guide_key}:{period_key}"
        embed.set_footer(text=f"{embed.footer.text + ' • ' if embed.footer and embed.footer.text else ''}{marker}")
        # Une publication déjà connue est actualisée en place : pas de doublon
        # lorsqu'une nouvelle identité visuelle ou un texte corrigé est déployé.
        existing = None
        with db() as conn:
            row = conn.execute(
                "SELECT message_id FROM guide_publications WHERE guild_id=? AND channel_id=? AND guide_key=? AND period_key=?",
                (channel.guild.id, channel.id, guide_key, period_key),
            ).fetchone()
        if row and row[0]:
            try:
                existing = await channel.fetch_message(int(row[0]))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                existing = None
        if existing is None:
            try:
                async for candidate in channel.history(limit=100):
                    if candidate.author.id == self.bot.user.id and any(
                        e.footer and marker in (e.footer.text or "") for e in candidate.embeds
                    ):
                        existing = candidate
                        break
            except (discord.Forbidden, discord.HTTPException, AttributeError):
                pass
        try:
            if existing is not None:
                await existing.edit(embed=embed)
                self.record_post(channel, guide_key, period_key, existing.id)
                return
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.HTTPException):
            return
        self.record_post(channel, guide_key, period_key, message.id)

    async def update_permanent(self, channel_id: int | None, guide_key: str, embed: discord.Embed, view: discord.ui.View | None = None):
        """Met à jour le message permanent existant au lieu d'en publier un nouveau."""
        channel = await self.resolve_channel(channel_id)
        if channel is None:
            return
        period_key = "permanent"
        marker = f"{FOOTER_PREFIX}{guide_key}:{period_key}"
        embed.set_footer(text=f"{FOOTER_PREFIX}{guide_key}:{period_key}")
        message = None

        # 1) Retrouver le message déjà enregistré en base.
        with db() as conn:
            row = conn.execute(
                "SELECT message_id FROM guide_publications WHERE guild_id=? AND channel_id=? AND guide_key=? AND period_key=?",
                (channel.guild.id, channel.id, guide_key, period_key),
            ).fetchone()
        if row and row[0]:
            try:
                message = await channel.fetch_message(int(row[0]))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                message = None

        # 2) Si la base ne référence plus le message, le retrouver grâce au marqueur.
        if message is None:
            try:
                async for candidate in channel.history(limit=500):
                    if candidate.author.id == self.bot.user.id and any(
                        e.footer and marker in (e.footer.text or "") for e in candidate.embeds
                    ):
                        message = candidate
                        break
            except (discord.Forbidden, discord.HTTPException, AttributeError):
                pass

        try:
            if message is not None:
                await message.edit(embed=embed, view=view)
                with db() as conn:
                    conn.execute(
                        "INSERT INTO guide_publications(guild_id,channel_id,guide_key,period_key,message_id,published_at) VALUES(?,?,?,?,?,?) "
                        "ON CONFLICT(guild_id,channel_id,guide_key,period_key) DO UPDATE SET message_id=excluded.message_id,published_at=excluded.published_at",
                        (channel.guild.id, channel.id, guide_key, period_key, message.id, datetime.now(LOCAL_TIMEZONE).isoformat()),
                    )
                return

            # Aucun ancien message retrouvé : une seule création, puis mémorisation.
            message = await channel.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
            with db() as conn:
                conn.execute(
                    "INSERT INTO guide_publications(guild_id,channel_id,guide_key,period_key,message_id,published_at) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(guild_id,channel_id,guide_key,period_key) DO UPDATE SET message_id=excluded.message_id,published_at=excluded.published_at",
                    (channel.guild.id, channel.id, guide_key, period_key, message.id, datetime.now(LOCAL_TIMEZONE).isoformat()),
                )
        except (discord.Forbidden, discord.HTTPException):
            return

    def weekly_embeds(self) -> list[tuple[int | None, str, discord.Embed]]:
        week = self.week_key()
        purple = discord.Color.from_rgb(155, 89, 182)
        teal = discord.Color.teal()
        blue = discord.Color.blurple()
        gold = discord.Color.gold()
        result: list[tuple[int | None, str, discord.Embed]] = []

        confession = horizons_embed(
            title="💜 Le salon Confession — un espace pour déposer tes mots",
            description=(
                "Tu peux partager une pensée, une difficulté, une expérience, une question ou simplement quelque chose que tu gardes pour toi. "
                "Ici, on privilégie l'écoute, le respect et l'absence de jugement. Tu n'es jamais obligé(e) de tout raconter.\n\n"
                "**Tu préfères ne pas afficher ton identité ?** Utilise la commande `/message_anonyme`. "
                "Ton texte sera publié dans <#1567218950180311210>, sans afficher ton nom aux membres. "
                "L'équipe conserve toutefois une trace interne de l'auteur pour prévenir les abus.\n\n"
                "Évite de publier des coordonnées, des informations très personnelles ou celles d'une autre personne. "
                "En cas de danger immédiat, contacte les services d'urgence plutôt que d'attendre une réponse sur Discord."
            ), color=purple,
        )
        confession.add_field(name="🌱 À retenir", value="Tu peux parler à ton rythme, demander une écoute ou simplement lire. Le respect de chacun passe avant tout.", inline=False)
        # Ancien salon confession : conservé en lecture/historique, plus de panneau récurrent.

        partner = horizons_embed(
            title="✦ Cherche quelqu'un pour partager une activité",
            description=(
                "Envie de jouer, regarder un film, discuter, faire un vocal ou découvrir une activité avec quelqu'un ? "
                "La commande `/chercher` te permet de publier une annonce dans ce salon.\n\n"
                "1. Lance `/chercher` et choisis ton activité.\n"
                "2. Ajoute une précision si tu le souhaites.\n"
                "3. Choisis combien de temps ton annonce reste visible (1 à 24 h).\n"
                "4. Les membres intéressés cliquent sur **Ça m'intéresse** ; tu reçois alors un message privé.\n\n"
                "Respecte le choix de chacun, ne partage pas d'informations personnelles et signale tout comportement inadapté à l'équipe."
            ), color=blue,
        )
        partner.add_field(name="✨ Petit conseil", value="Précise le jeu, le créneau ou le type d'échange recherché pour faciliter les rencontres.", inline=False)
        # Ancien panneau remplacé par le panneau interactif géré par salon_harmony.

        challenge = horizons_embed(
            title="✦ Défis collectifs HORIZONS",
            description=(
                "Ici, on avance ensemble ! Les défis collectifs proposent un objectif commun pour faire vivre le serveur et créer des liens.\n\n"
                "• `/defi_collectif` : consulter le défi en cours et sa progression.\n"
                "• `/rejoindre_defi` : rejoindre le défi et contribuer à l'objectif commun.\n"
                "• `/creer_defi` : proposer un nouveau défi (commande réservée à l'équipe autorisée).\n\n"
                "Chaque participation compte. L'idée n'est pas de se comparer, mais de construire quelque chose ensemble, dans la bonne humeur et sans pression."
            ), color=teal,
        )
        challenge.add_field(name="🧭 L'esprit du défi", value="Un objectif partagé, une participation libre et une communauté qui progresse à son rythme.", inline=False)
        # Ancien panneau remplacé par le panneau interactif géré par salon_harmony.

        birthday = horizons_embed(
            title="✦ Les anniversaires HORIZONS",
            description=(
                "Clique sur le bouton **Enregistrer / modifier mon anniversaire** pour indiquer ton jour et ton mois de naissance.\n\n"
                "Tu peux aussi ajouter ton **année de naissance**, mais elle reste facultative. Si tu la renseignes, ton âge sera annoncé le jour de ton anniversaire. "
                "Le bot publie un petit message dans ce salon le jour venu, à 9 h (heure de Paris).\n\n"
                "Tu peux modifier ta date avec le même bouton ou la supprimer à tout moment avec `/anniversaire_supprimer`. "
                "Cette démarche est entièrement facultative."
            ), color=gold,
        )
        result.append((BIRTHDAY_CHANNEL_ID, "anniversaires", birthday))

        anonymous = horizons_embed(
            title="✦ Messages anonymes",
            description=(
                "Tu as quelque chose à partager, mais tu ne souhaites pas que ton nom apparaisse ? Utilise `/message_anonyme` et écris ton texte.\n\n"
                "Le bot publie le contenu ici sans afficher ton identité aux autres membres. La commande accepte un texte de 5 à 1 500 caractères et limite les envois à deux messages par période de 10 minutes.\n\n"
                "**Important :** l'anonymat concerne l'affichage public. L'équipe conserve une trace interne de l'auteur dans un journal réservé au staff, afin de pouvoir prévenir et traiter les abus. "
                "N'utilise pas cette fonction pour viser, harceler ou exposer quelqu'un."
            ), color=teal,
        )
        # Panneau permanent géré par AnonymousPanelManager.

        intro = horizons_embed(
            title="✦ Présente-toi à la communauté",
            description=(
                "Bienvenue sur HORIZONS ! Si tu en as envie, ce salon est l'occasion de nous dire quelques mots sur toi. "
                "Pas besoin d'écrire un roman : une présentation simple et sincère suffit.\n\n"
                "Tu peux nous partager :\n"
                "• le prénom ou pseudo que tu souhaites qu'on utilise ;\n"
                "• tes passions, loisirs, jeux ou univers préférés ;\n"
                "• la musique, les films, les séries ou les lectures que tu aimes ;\n"
                "• ce que tu aimerais trouver ici : discuter, jouer, rencontrer des amis, participer aux activités… ;\n"
                "• une petite anecdote ou un fait amusant, si tu le souhaites.\n\n"
                "Tu choisis ce que tu souhaites dévoiler. Évite les informations privées comme ton adresse, ton numéro de téléphone, ton établissement ou tes habitudes précises. "
                "Et surtout : sois toi-même, sans pression. 💜"
            ), color=purple,
        )
        result.append((INTRO_CHANNEL_ID, "presentation", intro))

        return result

    def staff_command_embeds(self, week: str) -> list[discord.Embed]:
        """Même source que /aidestaff : pas de catalogue contradictoire."""
        from .command_catalog import build_catalog_embeds
        return build_catalog_embeds(self.bot, audience="staff", updated=week)

    @tasks.loop(minutes=30)
    async def publish_guides(self):
        if not GUILD_ID:
            return
        week = self.week_key()
        for channel_id, key, embed in self.weekly_embeds():
            if key == "anniversaires":
                continue
            await self.publish(channel_id, key, week, embed)

        # Catalogue staff : panneaux permanents, mis à jour en place plutôt que
        # repostés chaque semaine. Il reflète exactement la commande /aidestaff.
        for index, embed in enumerate(self.staff_command_embeds(week), start=1):
            await self.update_permanent(STAFF_COMMANDS_CHANNEL_ID, f"catalogue_staff_{index}", embed)

        spirit = horizons_embed(
            title="✦ L'histoire de HORIZONS",
            description=(
                "*Et si, finalement, ce qui nous rassemble était bien plus fort que ce qui nous différencie ?*\n\n"
                "HORIZONS est né d'une idée simple, mais profondément humaine : créer un endroit où chacun peut trouver sa place, "
                "sans avoir à se justifier d'être qui il est.\n\n"
                "Ici, une personne ne se résume ni à son genre, ni à son orientation sexuelle, ni à ses origines, ni à sa culture, ni à son histoire. "
                "Nous sommes toutes et tous différents. Nous avons grandi dans des environnements différents, traversé des épreuves différentes, "
                "connu des joies, des doutes, des réussites et parfois des blessures que les autres ne peuvent pas toujours voir.\n\n"
                "Et pourtant, nous avons quelque chose en commun : **nous avons tous une histoire à raconter, quelque chose à partager "
                "et peut-être quelque chose à apprendre les uns des autres.**\n\n"
                "HORIZONS, c'est cette envie de faire se rencontrer nos chemins. C'est pouvoir parler librement, rire ensemble, partager ses expériences, "
                "découvrir d'autres façons de voir le monde, tendre la main quand quelqu'un en a besoin et parfois simplement être là, "
                "sans avoir besoin de trouver les bons mots.\n\n"
                "C'est comprendre qu'on n'a pas besoin de se ressembler pour s'apprécier, ni de vivre les mêmes choses pour se respecter. "
                "Nous voulons faire de cet espace un lieu vivant, où les rencontres ont du sens, où la différence est une richesse "
                "et où personne ne devrait avoir l'impression d'être de trop.\n\n"
                "Parce qu'au fond, HORIZONS ne se construit pas avec un nom, un logo ou quelques salons Discord. "
                "**HORIZONS se construit avec vous.** Avec vos voix, vos histoires, vos différences, vos sourires et votre présence.\n\n"
                "Chacun apporte un petit morceau de son monde. Et c'est en réunissant tous ces morceaux que nous construisons le nôtre.\n\n"
                "✦ Peu importe d'où tu viens, qui tu es ou le chemin que tu as parcouru…\n\n"
                "**Il y a une place pour toi à l'horizon.**\n\n"
                "Bienvenue chez HORIZONS. ✦"
            ),
            color=discord.Color.gold(),
        )
        await self.update_permanent(SPIRIT_CHANNEL_ID, "notre_esprit", spirit)
        # Panneau d'anniversaire persistant : mis à jour en place, jamais dupliqué.
        from .birthdays import BirthdayPanel
        for channel_id, key, embed in self.weekly_embeds():
            if key == "anniversaires":
                await self.update_permanent(channel_id, "anniversaires_bouton", embed, view=BirthdayPanel())

    @publish_guides.before_loop
    async def before_publish_guides(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerGuides(bot))

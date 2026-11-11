"""Point d'entrée du bot Discord HORIZONS.

Les fonctionnalités sont isolées dans des extensions du dossier cogs/.
Les secrets et identifiants sont fournis par le fichier .env (jamais codés ici).
"""
from __future__ import annotations

import asyncio
import logging
import json
import os
import sys
from typing import Final

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    BASE_DIR, DISCORD_TOKEN, GUILD_ID, STAFF_ROLE_ID, ALERT_LOG_CHANNEL_ID,
    JOKE_DAILY_CHANNEL_ID, RIDDLE_DAILY_CHANNEL_ID, LOG_CHANNEL_ID,
    MOD_LOG_CHANNEL_ID, WELCOME_CHANNEL_ID, LEAVE_CHANNEL_ID, STAFF_COMMANDS_CHANNEL_ID,
    BIRTHDAY_CHANNEL_ID, SUGGESTION_CHANNEL_ID, INTRO_CHANNEL_ID,
    ANONYMOUS_CHANNEL_ID, DAILY_QUESTION_CHANNEL_ID, QUIZ_CHANNEL_ID, TEMP_VOICE_TRIGGER_ID,
    TEMP_VOICE_CATEGORY_ID, TICKET_CATEGORY_ID, AUTO_MOD_ENABLED,
    BLOCK_DISCORD_INVITES, TRANSLATE_API_URL, TRANSLATE_API_KEY, RANK_ROLE_IDS, DEFAULT_ANNOUNCEMENT_IMAGE_URL,
    TIMEZONE_NAME, LOCAL_TIMEZONE, COGS_DIR, DATA_DIR, LOG_DIR,
)

# Identité visuelle : le logo est publié une seule fois comme pièce jointe Discord.
from cogs.embed_theme import LOGO_PATH, LOGO_STATE_PATH, set_logo_url

_LOGO_SETUP_LOCK = asyncio.Lock()
_LOGO_SETUP_ATTEMPTED = False
# Référence du dépôt déjà présent sur Discord et consignée dans le ZIP fourni.
LOGO_FALLBACK_CHANNEL_ID = 1566562235793416242
LOGO_FALLBACK_MESSAGE_ID = 1567595402247667802


async def ensure_horizons_logo_asset(bot: commands.Bot) -> None:
    """Réutilise un dépôt existant ; ne republie pas si Discord est indisponible.

    Les identifiants du ZIP peuvent être périmés sur l'hébergement : rechercher
    dans l'historique avant de publier, puis enregistrer le message retrouvé.
    """
    global _LOGO_SETUP_ATTEMPTED
    async with _LOGO_SETUP_LOCK:
        if _LOGO_SETUP_ATTEMPTED:
            return
        _LOGO_SETUP_ATTEMPTED = True
        if not LOGO_PATH.is_file():
            logger.warning("Logo HORIZONS introuvable : %s", LOGO_PATH)
            set_logo_url(bot.user.display_avatar.url if bot.user else None)
            return

        try:
            state = json.loads(LOGO_STATE_PATH.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (OSError, json.JSONDecodeError):
            state = {}

        def remember(message: discord.Message) -> bool:
            attachments = [a for a in message.attachments if a.filename.lower() == "horizons_logo.png"]
            if not attachments:
                return False
            set_logo_url(attachments[0].url)
            try:
                LOGO_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
                temporary = LOGO_STATE_PATH.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps({"channel_id": message.channel.id, "message_id": message.id},
                               ensure_ascii=False, indent=2), encoding="utf-8")
                temporary.replace(LOGO_STATE_PATH)
            except OSError:
                logger.warning("Impossible d'enregistrer la référence du logo ; recherche Discord au prochain démarrage.")
            return True

        # L'historique du salon constitue la référence de secours si le fichier
        # local est réinitialisé à chaque déploiement.
        candidates = []
        for cid in (state.get("channel_id"), LOGO_FALLBACK_CHANNEL_ID,
                    STAFF_COMMANDS_CHANNEL_ID, LOG_CHANNEL_ID):
            if cid and cid not in candidates:
                candidates.append(cid)

        destination = None
        for cid in candidates:
            try:
                channel = bot.get_channel(int(cid)) or await bot.fetch_channel(int(cid))
                if not isinstance(channel, discord.TextChannel):
                    continue
                if destination is None and cid in (STAFF_COMMANDS_CHANNEL_ID, LOG_CHANNEL_ID):
                    destination = channel
                if cid == state.get("channel_id") and state.get("message_id"):
                    try:
                        if remember(await channel.fetch_message(int(state["message_id"]))):
                            return
                    except discord.NotFound:
                        pass
                if cid == LOGO_FALLBACK_CHANNEL_ID:
                    try:
                        if remember(await channel.fetch_message(LOGO_FALLBACK_MESSAGE_ID)):
                            return
                    except discord.NotFound:
                        pass
                async for message in channel.history(limit=200):
                    if message.author.id == bot.user.id and remember(message):
                        logger.info("Dépôt du logo HORIZONS retrouvé dans l'historique Discord.")
                        return
            except (discord.Forbidden, discord.HTTPException, ValueError, AttributeError) as exc:
                # Une erreur réseau/permission ne signifie pas que le message a
                # disparu. Ne jamais republier dans ce cas.
                logger.warning("Recherche du logo impossible (%s) : aucune republication automatique.", exc)
                set_logo_url(bot.user.display_avatar.url if bot.user else None)
                return

        # Ne jamais publier une image technique automatiquement au démarrage.
        # Le logo Discord existant ou l'avatar de l'application servent de secours.
        fallback_avatar = bot.user.display_avatar.url if bot.user else None
        logger.warning("Dépôt du logo introuvable : avatar du bot utilisé sans publication.")
        set_logo_url(fallback_avatar)
        return

# Charger uniquement les extensions présentes. Les extensions pourront être
# ajoutées progressivement sans empêcher le démarrage du bot.
EXTENSIONS: Final[tuple[str, ...]] = (
    "cogs.general",
    "cogs.centre_horizons",
    "cogs.onboarding",
    "cogs.smart_welcome",
    "cogs.regard_du_jour",
    "cogs.today_hub",
    "cogs.salon_harmony",
    "cogs.visual_identity",
    "cogs.continuity",
    "cogs.moderation",
    "cogs.logging_tools",
    "cogs.birthdays",
    "cogs.announcements",
    "cogs.jokes",
    "cogs.riddles",
    "cogs.community_ranks",
    "cogs.events",
    "cogs.staff_tools",
    "cogs.automod",
    "cogs.voice_rooms",
    "cogs.giveaways",
    "cogs.role_panels",
    "cogs.horizons_features",
    "cogs.community_hub",
    "cogs.staff_dashboard",
    "cogs.horizons_dashboard",
    "cogs.quizzes",
    "cogs.community",
    "cogs.experiences",
    "cogs.seasons",
    "cogs.mission_hub",
    "cogs.circle_proposals",
    "cogs.circle_guides",
    "cogs.server_audit_export",
    "cogs.horizons_daily",
    "cogs.publication_calendar",
    "cogs.weekly_animations",
    "cogs.horizons_path",
    "cogs.server_guides",
    "cogs.tickets",
    "cogs.translation",
    "cogs.horizons_arcade",
    "cogs.celestial_treasures",
    "cogs.chaos_cosmique",
    "cogs.nox_tv",
    "cogs.nox_publications",
    "cogs.nox_refuge",
    "cogs.nox_presence",
    "cogs.nox_life",
)

# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "horizons.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("horizons")


class HorizonsBot(commands.Bot):
    """Bot HORIZONS avec commandes slash synchronisées sur le serveur cible."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        # L'intent de présence n'est volontairement pas activé : inutile
        # pour les fonctions prévues et demande une permission privilégiée.
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.guild_object = discord.Object(id=GUILD_ID) if GUILD_ID else None

    async def setup_hook(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        COGS_DIR.mkdir(parents=True, exist_ok=True)
        from cogs.storage import init_db
        init_db()

        # Extensions optionnelles : les modules seront ajoutés au fil de la
        # reconstruction. Une extension absente est signalée sans bloquer le bot.
        for extension in EXTENSIONS:
            module_path = BASE_DIR.joinpath(*extension.split(".")).with_suffix(".py")
            if not module_path.is_file():
                logger.info("Extension en attente : %s", extension)
                continue
            try:
                await self.load_extension(extension)
                logger.info("Extension chargée : %s", extension)
            except Exception:
                logger.exception("Échec du chargement de l'extension %s", extension)

        if self.guild_object:
            # Les commandes définies dans les cogs sont globales par défaut.
            # On les copie dans le serveur cible avant la synchronisation locale.
            self.tree.copy_global_to(guild=self.guild_object)
            synced = await self.tree.sync(guild=self.guild_object)
            logger.info("%d commande(s) slash synchronisée(s) sur HORIZONS.", len(synced))
        else:
            logger.warning("GUILD_ID absent : aucune synchronisation slash effectuée.")

    async def on_ready(self) -> None:
        await ensure_horizons_logo_asset(self)
        if self.user:
            logger.info("Connecté en tant que %s (ID : %s)", self.user, self.user.id)
            await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="les horizons se rencontrer"))
        guild = self.get_guild(GUILD_ID) if GUILD_ID else None
        if GUILD_ID and guild is None:
            logger.warning("Le bot n'a pas accès au serveur configuré (GUILD_ID=%s).", GUILD_ID)
        elif guild:
            logger.info("Serveur actif : %s (%s membres connus)", guild.name, guild.member_count)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        if GUILD_ID and guild.id != GUILD_ID:
            logger.warning("Le bot a rejoint un serveur non configuré : %s (%s).", guild.name, guild.id)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        original = getattr(error, "original", error)
        if isinstance(error, app_commands.MissingPermissions):
            message = "Tu ne disposes pas des permissions Discord nécessaires pour cette commande."
        elif isinstance(error, app_commands.CheckFailure):
            message = "Tu n'es pas autorisé à utiliser cette commande."
        else:
            message = "Une erreur est survenue pendant l'exécution de cette commande. L'équipe HORIZONS en a été informée."
        logger.error(
            "Erreur commande slash %s : %s",
            getattr(interaction.command, "qualified_name", "inconnue"),
            original,
            exc_info=(type(original), original, original.__traceback__),
        )
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Impossible d'envoyer le message d'erreur à l'utilisateur.")


async def main() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN est absent. Ajoute le nouveau token dans le fichier .env local, "
            "sans le partager dans une conversation ou dans Git."
        )

    async with HorizonsBot() as bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Arrêt demandé : fermeture de HORIZONS.")

### NOX — vie spontanée (V10.85.7)

- `/nox` → Administration → Vie spontanée (salon et activation) : administrateur ; active ou suspend les interventions humoristiques spontanées de NOX dans le salon choisi. Par défaut désactivé. Maximum une intervention toutes les 22 h entre 9 h et 22 h (Europe/Paris). Webhook NOX requis.
- Les 160 dialogues sont dans `data/nox/dialogues_vie.json`. Ils ne lisent aucun message privé ou public et ne déclenchent pas de mentions.

### NOX V10.85.8 — Réactions et rythme
- Les six boutons du Refuge disposent chacun de 12 réponses originales (72 au total), envoyées uniquement à la personne qui a cliqué, sans spam public.
- Les interventions de besoin (`/nox` → Administration → Besoins de NOX) et de vie (`/nox` → Administration → Vie spontanée) s’espacent mutuellement d’au moins 2 heures. Leurs limites individuelles restent en vigueur.
- Les répliques sont modifiables dans `data/nox/reactions_soins.json`.

### NOX — réactions aux événements (V10.85.9)

`/nox` → Administration → Événements (anniversaires et quiz) — administrateurs uniquement. Désactivé par défaut. Anniversaire : NOX remplace le message habituel avec retour automatique au message classique si webhook indisponible. Quiz : réaction optionnelle après classement, une fois par session.

### V10.85.10 — Surprises collectives NOX
`/nox` → Animations → Surprise (administrateur) : choisir parmi 4 thèmes (absurdité, question, mini-défi, douceur) et un salon. NOX publie via webhook ; pas de publication automatique. 32 répliques dans `data/nox/surprises_collectives.json`.

### Aventures collectives de NOX (V10.85.11)
- `/noxaventure action:lancer salon:#salon` : administrateur, lance une aventure avec 3 boutons de vote.
- `/noxaventure action:conclure` : administrateur, clôture et publie le résultat (votes persistants, un vote par membre modifiable).
- Une aventure active par serveur ; votes pendant 30 minutes ; aucun envoi automatique.

### Distinctions NOX (V10.85.13)
- `/noxtitres` : membre, affiche en privé les distinctions symboliques calculées à partir des soins du Refuge. Rôles Discord attribués si installés, aucun XP.

- `/nox` → Administration → Créer les rôles : administrateur, crée les sept rôles de NOX sans doublons.
- `/nox` → Administration → Synchroniser rôles : administrateur, attribue les rôles acquis aux membres déjà contributeurs (100 par appel, paramètre `debut` pour les suivants).\n
- `/noxmission lancer [salon]` : lance une mission collective de NOX (administrateurs).
- `/noxmission conclure` : clôture la mission et publie son bilan (administrateurs).

- `/noxquotidien salon:#salon actif:true|false` (administrateur) : 12 publications de NOX par jour, de 10 h à 22 h 50 (Europe/Paris), dans le salon choisi. Pas de rattrapage après interruption.

### NOX : publications illustrées
`/noxquotidien` : 12 publications entre 10 h et 22 h 50, dont 6 avec une image directement liée au texte. Le bot doit pouvoir joindre des fichiers.

V10.85.17 : `/noxquotidien` répartit les 12 créneaux entre humour, questions, aventures, entraide, défis, discussions, bienveillance et soirée ; six sont illustrés.

### Réponses spontanées NOX (V10.85.18)
NOX peut répondre occasionnellement aux réponses directes à ses 12 publications quotidiennes : 35 % de chance, maximum 3 réactions par serveur et par jour, 20 minutes minimum entre deux réponses, et une seule par membre et par jour. Entre 10 h et 23 h (Paris). Aucun contenu des messages des membres n’est lu ni conservé. Aucune nouvelle commande.

### V10.85.19 — Sondages interactifs de NOX
Deux des 12 publications quotidiennes (11h10 et 18h10) sont des mini-sondages à trois boutons. Un vote par membre et par sondage, modifiable jusqu’à 23h ; résultats provisoires privés. Aucun message quotidien supplémentaire, aucune nouvelle commande.

### NOX — défis quotidiens (V10.85.20)
À **15 h 50**, NOX publie un défi communautaire à la place du créneau textuel existant. Bouton persistant « Je relève le défi ! », une inscription par membre et par jour, clôture à 23 h. Aucun nouveau salon, aucune commande et aucun XP.

### NOX — bilan du soir (V10.85.21)
À **22 h 50**, le créneau textuel existant devient le journal de bord de NOX : bilan du défi de 15 h 50 fondé sur les inscriptions réellement enregistrées, remerciements et conclusion humoristique. Si aucun défi n'a été publié, NOX ne prétend pas avoir compté des participations. Aucun message, salon, commande ou rôle supplémentaire.


### V10.85.22 — Célébrations collectives NOX
Les défis quotidiens félicitent en privé les participants qui franchissent les paliers collectifs 3, 5, 10, 15, 20, 30, 50 et 100. Le bilan de 22h50 souligne le plus haut palier atteint, sans publication supplémentaire, classement, XP ni nouvelle commande.

### V10.85.24 — Vérification technique
- Aucun changement de commande utilisateur ; sécurisation de la boucle des publications quotidiennes NOX.
- Ajout de `tests/test_nox_stabilisation_v108524.py` pour les contrôles hors ligne.

### V10.85.25 — Diagnostic de préproduction
- `/noxdiagnostic` (administrateur) : contrôle en lecture seule du salon, des permissions webhook et pièces jointes, des illustrations, des réservations de publication et des identifiants de sondages/défis. Aucun message public ni webhook créé.
- Les réservations en attente ne sont pas réinitialisées automatiquement : vérifier manuellement le message Discord pour éviter les doublons.

- `/noxplanning` (administrateur) : vue privée en lecture seule des 12 créneaux, du salon configuré et des états envoyés / réservés / non enregistrés. Ne publie rien. (V10.85.26)


## Centre NOX — V10.85.27
- `/nox` : tableau de bord principal avec rubriques Univers, Refuge, Animations, Publications, NOX TV et Administration.
- Les anciennes entrées `/noxplanning`, `/noxdiagnostic` et `/noxquotidien` sont remplacées par des boutons dans `/nox` (Administration). Les fonctions restent présentes dans le code.
- NOX TV conserve son sous-panneau et ses commandes avancées. Les autres commandes NOX restent temporairement accessibles jusqu'à leur migration complète, pour ne pas perdre de fonctionnalité.


### V10.85.28 — Centralisation des animations de NOX
- `/nox` → **Animations** : lancer / conclure une aventure et lancer / conclure une mission collective. Les actions sont réservées aux administrateurs et utilisent le salon dans lequel le panneau est ouvert.
- `/nox` → **Refuge** : accès privé aux souvenirs et distinctions.
- Les commandes slash `/noxaventure`, `/noxmission`, `/noxmemoire` et `/noxtitres` sont remplacées par ces boutons. La logique métier et les données sont conservées.
- `/nox` → **Administration** : planning, diagnostic et configuration du quotidien.


### V10.85.29 — Réglages NOX centralisés
Les anciennes commandes `/noxpresence`, `/noxvie`, `/noxevenements`, `/noxsurprise` et `/noxroles` ne sont plus enregistrées comme commandes slash. Leurs fonctions sont accessibles dans `/nox`, via les menus privés. La synchronisation des rôles conserve sa pagination.


### V10.85.30 — Publications depuis `/nox`
- `/nox` → Publications → **Publier une réplique** : catalogue des 20 messages, publication dans le salon actuel (administration).
- `/nox` → Publications → **Faire parler NOX** : formulaire de texte personnalisé, publication dans le salon actuel (administration).
- `/noxpublier` et `/me` ne sont plus enregistrées comme commandes slash. Les méthodes internes sont conservées pour le tableau de bord.
- Les fonctions des autres commandes ne sont pas modifiées dans cette étape.


### V10.85.34 — Livraison finale candidate (remplace les anciennes indications NOX ci-dessus)
- `/nox` : centre de contrôle principal, rubriques Publications, Animations, Refuge, NOX TV, Administration.
- `/nox` → Administration → Planning, Diagnostic, Configurer le quotidien.
- `/nox` → Publications → Publier une réplique, Faire parler NOX.
- `/nox` → Animations → Aventures, Missions, Surprise.
- `/nox` → Refuge → Souvenirs, Distinctions.
- Les commandes `/noxquotidien`, `/noxdiagnostic`, `/noxplanning`, `/noxaventure`, `/noxmission`, `/noxmemoire`, `/noxtitres`, `/noxpresence`, `/noxvie`, `/noxevenements`, `/noxsurprise`, `/noxroles`, `/noxpublier` et `/me` mentionnées dans l'historique **ne sont plus des commandes slash à utiliser**.
- `/dashboard` : tableau de bord staff ; `/centre` : centre membres ; `/aide` et `/aidestaff` : aides.
- Pour NOX TV, privilégier `/nox` → NOX TV ; consulter `/aide` pour les autres commandes encore réellement enregistrées.


V10.85.43 : le bouton « Faire parler NOX » du tableau `/nox` illustre les textes libres selon leur thème (portrait neutre sinon), sans nouvelle commande.

## Audit V10.85.44
Aucune nouvelle commande slash. NOX TV conserve sa réservation de publication quotidienne si l'envoi échoue de manière ambiguë, afin de limiter les doublons. Tests Discord à effectuer lors de la mise en production.


### V10.85.45 — Audit tableaux de bord
Aucune nouvelle commande. `/centre` acquitte les interactions avant les accès SQLite ; correction d’un ancien callback de navigation staff.


## V10.85.46 — Candidate finale
Aucune nouvelle commande. Recette et déploiement : `V10_85_46_RAPPORT_FINAL.md`.


### V10.85.50 — Audit cohérence NOX
Aucune nouvelle commande. Restauration des boutons d’aventure liée au message Discord, validation des votes et robustesse des interventions spontanées.

## V10.85.51 — Fiabilisation du programmateur NOX

Aucune nouvelle commande. Les identifiants des sondages/défis et l'état des publications sont enregistrés dans une transaction unique. En cas d'échec d'envoi incertain, la réservation est conservée pour éviter les doublons. Voir `V10_85_51_RAPPORT.md`.

## NOX Junior V0.1 (fondations)
- `/monnox` : adoption privée (rôle Lien vivant `1567215752656715927` et 10 soins au NOX collectif), sélection de compagnon, soins et renommage unique.
- `/givemonnox membre` : rôle Fondateur `1566561887305339001` uniquement ; autorisation confirmée d'une deuxième adoption (maximum deux).
- Soins Junior : 30 minutes de repos partagé entre les soins ; croissance par temps, complicité et activités.
- Les mini-jeux complets, inventaires, cadeaux, chambres, talents et rencontres sont **prévus mais non encore implémentés** en V0.1.

## NOX Junior V0.2 — Vie quotidienne
- `/monnox` : panneau privé avec les six soins (nourrir, boire, jouer, câlin, laver, repos), actualisation des cinq jauges et humeur contextuelle.
- Bouton **Journal** : dernières actions horodatées du compagnon ; bouton **Actualiser** : recalcul de l'état du compagnon.
- Les jauges diminuent progressivement lors des consultations, avec un plancher de 30/100 et un maximum de 72 h de décroissance comptabilisée par période hors ligne.
- Les six soins partagent le même repos de 30 minutes ; le renommage reste limité à une fois.
- Les jeux avancés, les talents, les cadeaux, les rencontres et les chambres illustrées ne sont pas encore livrés.

## NOX Junior V0.3 — Jeux et présentation
- `/monnox` : bouton **Mini-jeux** (chasse aux étoiles, mémoire cosmique, décision cosmique) et bouton **Talents** (affinités enregistrées). Récompenses plafonnées à une partie par dix minutes et par compagnon.
- `/montrermonnox [compagnon:1|2]` : publie volontairement dans le salon courant une illustration originale du bébé NOX et sa fiche (nom, âge, stade, couleur, humeur, complicité, activités et talent si révélé). Aucun message automatique.
- `/givemonnox membre` : autorisation Fondateur de deuxième adoption, inchangée.

## NOX Junior V0.4
- `/monnox` : panneau privé, six mini-jeux (Chasse aux étoiles, Mémoire cosmique, Décision cosmique, Cristaux mystérieux, Énigmes stellaires, Constellations), explorations dans cinq régions et carnet des découvertes.
- `/montrermonnox` : présentation publique volontaire avec portrait.
- `/givemonnox` : attribution exceptionnelle Fondateur.
- Les six mini-jeux restants (Parcours cosmique, Course des comètes, Mission sauvetage, Duo des étoiles, Chasse au trésor collective, Festival cosmique) sont prévus pour les phases suivantes.

## NOX Junior V0.5
- `/monnox` : neuf mini-jeux, dont Parcours cosmique, Course des comètes et Mission sauvetage.
- `/monnox` → **Journal** : souvenirs automatiques, notes personnelles (titre 80 caractères, texte 1 000 caractères), création, lecture, modification, suppression confirmée et partage public confirmé. Chaque compagnon conserve son journal indépendant.
- `/montrermonnox` : présentation publique volontaire, inchangée.
- `/givemonnox` : attribution exceptionnelle Fondateur, inchangée.
- Jeux sociaux restants : Duo des étoiles, Chasse au trésor collective, Festival cosmique (3 jeux).

## NOX Junior V0.6 — Inventaire, cadeaux et chambres
- `/monnox` → **Sac cosmique** : consulter les objets gagnés en exploration, fabriquer une veilleuse ou un coussin avec les matériaux nécessaires, proposer un cadeau à un autre membre possédant un NOX Junior.
- `/monnox` → **Chambre** : choisir un thème et installer une décoration réellement possédée ; chambre indépendante pour chaque compagnon.
- `/monnox` → **Cadeaux reçus** : accepter ou refuser les propositions en attente (expiration 24 h). Les objets non transférables, notamment les souvenirs, sont protégés.
- Les explorations terminées attribuent désormais un matériau à l'inventaire, en transaction avec la récompense existante.
- Aucune commande slash supplémentaire. `/montrermonnox` reste inchangée.

## NOX Junior V0.7 — Rencontres cosmiques
- `/monnox` → sélectionner son compagnon → **Rencontres** : proposer une rencontre à un autre membre possédant un NOX, consulter les invitations reçues ou envoyées et jouer après consentement.
- Trois mini-jeux sociaux supplémentaires : **Duo des étoiles**, **Chasse au trésor collective** et **Festival cosmique** (12 mini-jeux au total : 9 individuels + 3 coopératifs).
- Les invitations expirent après 24 h ; la participation des deux propriétaires est indispensable avant toute récompense. Récompenses attribuées une seule fois aux deux NOX, sauvegardées dans SQLite.
- Aucune nouvelle commande slash. `/montrermonnox` reste une présentation publique volontaire.

### NOX Junior V0.8 — Visuels
- `/monnox` → bouton **Portrait** : illustration privée selon l'âge, la couleur, l'humeur et la chambre du compagnon.
- `/monnox` → **Chambre** : aperçu illustré de l'ambiance choisie.
- `/montrermonnox [compagnon]` : portrait public volontaire reflétant l'évolution et l'ambiance.
- Aucun nouveau slash-command : toutes les actions restent regroupées dans le panneau personnel.

### NOX Junior V0.9 — rencontres en trois manches
- `/monnox` → **Rencontres** → invitation et acceptation inchangées.
- Les trois jeux coopératifs (Duo des étoiles, Chasse au trésor collective, Festival cosmique) proposent chacun **3 manches**, avec trois décisions par manche.
- Chaque membre joue une fois par manche ; le passage à la suivante exige les deux choix. Reprendre dans `/monnox` → Rencontres après la réponse du partenaire.
- Récompense commune une seule fois, à la fin des trois manches, avec bonus pour les choix complémentaires.
- Aucune commande slash supplémentaire.


### NOX Junior V1.0 — Couleur arc-en-ciel 🌈 et consolidation
- `/monnox` → **Adopter** : 9 couleurs disponibles, dont **🌈 Arc-en-ciel** (`arc_en_ciel`), avec motifs multicolores sur l'œuf et le compagnon à chaque stade.
- `/monnox` → **Portrait** et **Chambre** : illustrations adaptées aux neuf couleurs, aux âges et aux humeurs.
- `/montrermonnox [compagnon]` : présentation publique facultative avec portrait multicolore.
- `/givemonnox membre` : **Fondateur uniquement**, autorisation d'adopter un deuxième compagnon.
- `/aide` et `/aidestaff` : catalogue dynamique classant les commandes NOX Junior, avec restriction staff correcte pour `/givemonnox`.
- Aucun changement de couleur automatique pour les compagnons existants. Aucune nouvelle commande slash.
- Dépendance Pillow ajoutée à `requirements.txt` pour éviter un échec d'import au déploiement.

### NOX Junior V1.6 — mini-jeux
Depuis `/monnox` → **Mini-jeux**, 12 activités sont disponibles, dont **Cache-cache cosmique**, **Cuisine des étoiles** et **Danse des constellations**. Les parties sont rejouables ; seules les cinq premières parties terminées par jour rapportent 2 Poussières d'étoiles chacune.

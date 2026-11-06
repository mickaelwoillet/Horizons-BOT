"""Publications quotidiennes Horizon du jour et débat hebdomadaire HORIZONS."""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, time

import discord
from discord.ext import commands, tasks

from config import DATA_DIR, DEBATE_CHANNEL_ID, HORIZON_DAILY_CHANNEL_ID, LOCAL_TIMEZONE
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

log = logging.getLogger(__name__)
STATE_FILE = DATA_DIR / "horizons_publications_history.json"

# Plusieurs propositions par thème afin de varier les publications au fil des semaines.
DAILY_CONTENT: dict[int, tuple[str, list[str]]] = {
    0: ("🌱 La pensée positive du lundi", [
        "Tu n'as pas besoin de tout réussir aujourd'hui. Un petit pas sincère est déjà un progrès.",
        "Ta valeur ne dépend pas de ta productivité. Prends aussi le temps de respirer.",
        "Chaque nouveau départ commence souvent par une décision toute simple : essayer.",
        "Sois aussi patient avec toi-même que tu le serais avec une personne que tu apprécies.",
        "Même une journée ordinaire peut contenir un moment qui fait du bien.",
        "Tu as le droit d'avancer à ton rythme, sans te comparer aux autres.",
        "Un geste de gentillesse, envers toi ou quelqu'un d'autre, peut changer une journée.",
    ]),
    1: ("🎯 Le mini-défi du mardi", [
        "Envoie un message gentil à une personne à laquelle tu n'as pas parlé depuis quelque temps.",
        "Accorde-toi dix minutes sans écran et profite simplement de ce moment.",
        "Découvre une chanson que tu ne connais pas et partage-la avec la communauté.",
        "Remercie sincèrement quelqu'un pour une petite chose qu'il a faite.",
        "Fais une pause, bois un verre d'eau et étire doucement tes épaules.",
        "Aujourd'hui, pose une question avec une vraie curiosité et prends le temps d'écouter.",
        "Partage une petite victoire récente, même si elle te semble toute simple.",
    ]),
    2: ("🎵 La découverte musicale du mercredi", [
        "Fais découvrir à HORIZONS une chanson qui te donne de l'énergie. Qu'est-ce qui te plaît dans ce morceau ?",
        "Choisis une musique qui t'apaise et partage-la avec quelques mots sur ce qu'elle t'évoque.",
        "Et si tu faisais découvrir un artiste francophone que tu apprécies ?",
        "Partage une musique qui te rappelle un beau souvenir, sans obligation de raconter lequel.",
        "Quel morceau te donne instantanément envie de chanter ? Fais-nous écouter !",
        "Propose une musique instrumentale ou classique qui mérite d'être connue.",
        "Fais découvrir une chanson d'une autre époque ou d'un autre pays.",
    ]),
    3: ("🤔 La question insolite du jeudi", [
        "Si tu pouvais maîtriser instantanément une compétence, laquelle choisirais-tu ?",
        "Quel petit objet du quotidien mériterait selon toi une amélioration révolutionnaire ?",
        "Si ta journée avait une bande-son, quelle chanson l'accompagnerait ?",
        "Quel lieu imaginaire aimerais-tu visiter pendant une heure ?",
        "Si tu pouvais dîner avec un personnage de roman, qui inviterais-tu ?",
        "Quelle invention toute simple a le plus changé ton quotidien ?",
        "Si tu devais donner un titre à cette période de ta vie, lequel choisirais-tu ?",
    ]),
    4: ("🤝 L'activité collective du vendredi", [
        "Construisons une playlist HORIZONS : chacun propose un morceau qui met de bonne humeur.",
        "En un mot ou une phrase, partagez quelque chose qui vous a fait sourire cette semaine.",
        "Faisons une chaîne de recommandations : un livre, un film, une série ou une musique à découvrir.",
        "Chacun propose une idée simple pour rendre la communauté encore plus accueillante.",
        "Partageons nos petites astuces pour prendre soin de soi au quotidien.",
        "Écrivons ensemble une histoire : chacun ajoute une phrase à la suite du précédent.",
        "Proposez une activité accessible que nous pourrions organiser ensemble sur HORIZONS.",
    ]),
    5: ("🎨 Le défi créatif du samedi", [
        "Décris ton humeur du jour avec trois couleurs et explique ton choix si tu le souhaites.",
        "Invente un slogan positif de cinq mots maximum pour HORIZONS.",
        "Écris une micro-histoire en trois phrases qui commence par : « Au bout du chemin… »",
        "Prends une photo d'un détail qui attire ton regard et partage ce qu'il t'inspire.",
        "Imagine une nouvelle salle pour le serveur : quel serait son nom et son objectif ?",
        "Crée une petite liste de trois choses qui rendent la vie plus douce.",
        "Trouve une métaphore originale pour décrire l'amitié.",
    ]),
    6: ("💜 Notre rétrospective positive du dimanche", [
        "Avant de commencer une nouvelle semaine, quel moment aimerais-tu garder en mémoire ?",
        "Quelle petite chose as-tu réussie cette semaine et dont tu peux être fier ?",
        "Quel échange ou quelle rencontre t'a fait du bien ces derniers jours ?",
        "Quel apprentissage souhaites-tu emporter avec toi dans la semaine à venir ?",
        "Quel geste de solidarité ou de bienveillance as-tu remarqué cette semaine ?",
        "Quelle difficulté as-tu réussi à traverser, même partiellement ?",
        "Quel souhait positif aimerais-tu adresser à la communauté pour la semaine prochaine ?",
    ]),
}

DEBATE_TOPICS = [
    "Les réseaux sociaux rapprochent-ils vraiment les personnes, ou donnent-ils surtout une illusion de proximité ?",
    "À l'école, devrait-on accorder autant de place à l'intelligence émotionnelle qu'aux matières traditionnelles ?",
    "Peut-on être sincère dans une amitié tout en gardant certaines choses pour soi ?",
    "La technologie nous fait-elle gagner du temps ou nous en prend-elle davantage ?",
    "Faut-il toujours chercher à sortir de sa zone de confort pour évoluer ?",
    "Les petites actions individuelles peuvent-elles réellement faire évoluer la société ?",
    "Dans une communauté en ligne, qu'est-ce qui crée le plus le sentiment d'appartenance ?",
    "L'anonymat sur Internet protège-t-il davantage la liberté de parole ou favorise-t-il les abus ?",
    "Peut-on changer d'avis sur une conviction importante sans renier qui l'on est ?",
    "La bienveillance doit-elle avoir des limites lorsqu'un échange devient irrespectueux ?",
    "Les rencontres virtuelles peuvent-elles créer des liens aussi forts que les rencontres en personne ?",
    "Qu'est-ce qui compte le plus dans un espace communautaire : les règles, la liberté ou la confiance ?",
]


def _load_history() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_history(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)


def _pick_unseen(key: str, pool: list[str]) -> str:
    history = _load_history()
    seen = set(history.get(key, []))
    choices = [item for item in pool if item not in seen]
    if not choices:
        seen.clear()
        choices = pool
    chosen = random.choice(choices)
    seen.add(chosen)
    history[key] = list(seen)[-100:]
    _save_history(history)
    return chosen


async def _get_channel(bot: commands.Bot, channel_id: int | None):
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.exception("Impossible de récupérer le salon configuré (%s).", channel_id)
            return None
    return channel


class HorizonsDaily(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.horizon_of_day.start()
        self.weekly_debate.start()

    def cog_unload(self):
        self.horizon_of_day.cancel()
        self.weekly_debate.cancel()

    @tasks.loop(time=time(hour=9, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def horizon_of_day(self):
        channel = await _get_channel(self.bot, HORIZON_DAILY_CHANNEL_ID)
        if channel is None:
            log.warning("HORIZON_DAILY_CHANNEL_ID non configuré ou salon inaccessible.")
            return
        today = datetime.now(LOCAL_TIMEZONE).weekday()
        title, pool = DAILY_CONTENT[today]
        content = _pick_unseen(f"day_{today}", pool)
        embed = horizons_embed(title=title, description=content, color=discord.Color.blurple())
        embed.set_footer(text="HORIZONS • Un rendez-vous quotidien pour se retrouver")
        try:
            if isinstance(channel, (discord.TextChannel)):
                await channel.send(embed=embed)
            else:
                log.error("Le salon Horizon du jour doit être un salon textuel (type : %s).", type(channel).__name__)
        except discord.Forbidden:
            log.exception("Permissions insuffisantes pour publier Horizon du jour.")
        except discord.HTTPException:
            log.exception("Impossible de publier Horizon du jour.")

    @horizon_of_day.before_loop
    async def before_horizon_of_day(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

    @tasks.loop(time=time(hour=18, minute=0, tzinfo=LOCAL_TIMEZONE))
    async def weekly_debate(self):
        # Le contrôle du jour évite une publication quotidienne : dimanche uniquement.
        if datetime.now(LOCAL_TIMEZONE).weekday() != 6:
            return
        channel = await _get_channel(self.bot, DEBATE_CHANNEL_ID)
        if channel is None:
            log.warning("DEBATE_CHANNEL_ID non configuré ou salon inaccessible.")
            return
        topic = _pick_unseen("debates", DEBATE_TOPICS)
        embed = horizons_embed(
            title="🗣️ Le débat de la semaine",
            description=(
                f"**{topic}**\n\n"
                "La parole est à vous ! Présentez vos arguments, partagez vos expériences "
                "et prenez le temps d'écouter les autres. Les désaccords sont bienvenus, "
                "à condition de rester respectueux.\n\n"
                "💜 Pas de jugement, pas d'attaque personnelle : faisons de ce débat un espace d'échange."
            ),
            color=discord.Color.purple(),
        )
        try:
            if isinstance(channel, discord.ForumChannel):
                title = topic if len(topic) <= 100 else topic[:97].rstrip() + "..."
                await channel.create_thread(
                    name=title,
                    content="🗣️ Le débat HORIZONS de la semaine est ouvert. Vous pouvez répondre directement dans cette publication.",
                    embed=embed,
                )
            elif isinstance(channel, (discord.TextChannel)):
                await channel.send(embed=embed)
            else:
                log.error("Le salon des débats doit être un Forum ou un salon textuel (type : %s).", type(channel).__name__)
        except discord.Forbidden:
            log.exception("Permissions insuffisantes pour publier le débat hebdomadaire.")
        except discord.HTTPException:
            log.exception("Impossible de publier le débat hebdomadaire.")

    @weekly_debate.before_loop
    async def before_weekly_debate(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(HorizonsDaily(bot))

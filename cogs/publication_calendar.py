"""Nouvelles publications quotidiennes du calendrier éditorial HORIZONS."""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, time

import discord
from discord.ext import commands, tasks

from config import (
    AGENDA_CHANNEL_ID,
    DATA_DIR,
    HORIZON_DAILY_CHANNEL_ID,
    INSPIRATION_CHANNEL_ID,
    LOCAL_TIMEZONE,
    QUIZ_CHANNEL_ID,
)
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

log = logging.getLogger(__name__)
STATE_FILE = DATA_DIR / "publication_calendar_history.json"


def _load_json(filename: str):
    try:
        return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception("Impossible de lire la banque %s", filename)
        return []


def _load_state() -> dict:
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _pick_item(filename: str, key: str) -> dict | None:
    items = _load_json(filename)
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict)]
    if not items:
        return None
    state = _load_state()
    history = state.get("seen", {})
    if not isinstance(history, dict):
        history = {}
    seen = set(history.get(key, []))
    candidates = [item for item in items if str(item.get("id", item.get("question", ""))) not in seen]
    if not candidates:
        seen.clear()
        candidates = items
    chosen = random.choice(candidates)
    identifier = str(chosen.get("id", chosen.get("question", "")))
    seen.add(identifier)
    history[key] = list(seen)[-200:]
    state["seen"] = history
    _save_state(state)
    return chosen


async def _get_channel(bot: commands.Bot, channel_id: int | None):
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            log.exception("Salon inaccessible : %s", channel_id)
            return None
    return channel


async def _send_embed(bot: commands.Bot, channel_id: int | None, embed: discord.Embed, *, thread_title: str | None = None):
    channel = await _get_channel(bot, channel_id)
    if channel is None:
        return False
    try:
        if isinstance(channel, discord.ForumChannel):
            title = (thread_title or embed.title or "Publication HORIZONS").strip()
            await channel.create_thread(name=title[:100], content="✦ Une nouvelle publication HORIZONS", embed=embed)
        elif isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.send(embed=embed)
        else:
            log.error("Type de salon non pris en charge pour %s : %s", channel_id, type(channel).__name__)
            return False
        return True
    except (discord.Forbidden, discord.HTTPException):
        log.exception("Échec de publication dans le salon %s", channel_id)
        return False


class PublicationCalendar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_quiz.start()
        self.daily_inspiration.start()
        self.daily_positive_message.start()
        self.daily_thematic_event.start()

    def cog_unload(self):
        self.daily_quiz.cancel()
        self.daily_inspiration.cancel()
        self.daily_positive_message.cancel()
        self.daily_thematic_event.cancel()

    async def cog_load(self):
        # Les dates publiées empêchent une répétition après un redémarrage le même jour.
        state = _load_state()
        state.setdefault("published_dates", {})
        _save_state(state)

    async def _publish_daily_bank(self, filename: str, key: str, channel_id: int, title: str, color, text_field: str = "texte", extra: str | None = None):
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        state = _load_state()
        if state.get("published_dates", {}).get(key) == today:
            return
        item = _pick_item(filename, key)
        if not item or not item.get(text_field):
            log.warning("Aucun contenu valide dans %s", filename)
            return
        embed = horizons_embed(title=title, description=str(item[text_field]), color=color)
        if extra and item.get(extra):
            embed.add_field(name=extra.capitalize(), value=str(item[extra]), inline=False)
        if item.get("theme"):
            embed.add_field(name="Thème", value=str(item["theme"]), inline=True)
        if item.get("categorie"):
            embed.add_field(name="Catégorie", value=str(item["categorie"]), inline=True)
        embed.set_footer(text="HORIZONS • Rendez-vous quotidien")
        if await _send_embed(self.bot, channel_id, embed):
            state = _load_state()
            state.setdefault("published_dates", {})[key] = today
            _save_state(state)

    @tasks.loop(time=time(hour=13, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def daily_quiz(self):
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        state = _load_state()
        if state.get("published_dates", {}).get("quiz") == today:
            return
        item = _pick_item("quiz.json", "quiz")
        if not item or not item.get("question") or not item.get("reponse"):
            log.warning("Banque quiz.json vide ou invalide.")
            return
        embed = horizons_embed(title="🧠 Le quiz du jour", description=str(item["question"]), color=discord.Color.teal())
        if item.get("categorie"):
            embed.add_field(name="Catégorie", value=str(item["categorie"]), inline=True)
        embed.add_field(name="Réponse", value=f"||{item['reponse']}||", inline=False)
        embed.set_footer(text="HORIZONS • Réponse sous spoiler")
        if await _send_embed(self.bot, QUIZ_CHANNEL_ID, embed):
            state = _load_state(); state.setdefault("published_dates", {})["quiz"] = today; _save_state(state)

    @daily_quiz.before_loop
    async def before_daily_quiz(self):
        await self.bot.wait_until_ready(); await wait_for_logo_ready()

    @tasks.loop(time=time(hour=19, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def daily_inspiration(self):
        # Le vendredi est réservé à l'animation collective et le dimanche au débat.
        # On évite donc toute publication concurrente à 19 h 30 ces deux jours.
        weekday = datetime.now(LOCAL_TIMEZONE).weekday()
        if weekday in (4, 6):
            return
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        state = _load_state()
        if state.get("published_dates", {}).get("inspiration") == today:
            return
        quote = _pick_item("citations.json", "citations")
        proverb = _pick_item("proverbes.json", "proverbes")
        if not quote or not quote.get("texte") or not proverb or not proverb.get("texte"):
            log.warning("Banque citations.json ou proverbes.json vide/invalide.")
            return
        description = (
            f"✦ **La citation**\n{quote['texte']}\n"
            f"— {quote.get('auteur', 'Pensée HORIZONS')}\n\n"
            f"🌿 **Le proverbe**\n{proverb['texte']}"
        )
        embed = horizons_embed(title="📚 L'inspiration du soir", description=description, color=discord.Color.blurple())
        if quote.get("theme"):
            embed.add_field(name="Thème de la citation", value=str(quote["theme"]), inline=True)
        if proverb.get("origine"):
            embed.add_field(name="Origine du proverbe", value=str(proverb["origine"]), inline=True)
        embed.set_footer(text="HORIZONS • Une pensée à emporter avec soi")
        if await _send_embed(self.bot, INSPIRATION_CHANNEL_ID, embed):
            state = _load_state(); state.setdefault("published_dates", {})["inspiration"] = today; _save_state(state)

    @daily_inspiration.before_loop
    async def before_daily_inspiration(self):
        await self.bot.wait_until_ready(); await wait_for_logo_ready()

    @tasks.loop(time=time(hour=21, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def daily_positive_message(self):
        await self._publish_daily_bank("messages.json", "messages", INSPIRATION_CHANNEL_ID, "🌻 Le message bienveillant du jour", discord.Color.gold())

    @daily_positive_message.before_loop
    async def before_daily_positive_message(self):
        await self.bot.wait_until_ready(); await wait_for_logo_ready()

    @tasks.loop(time=time(hour=8, minute=0, tzinfo=LOCAL_TIMEZONE))
    async def daily_thematic_event(self):
        today = datetime.now(LOCAL_TIMEZONE)
        key_date = today.strftime("%d-%m")
        state = _load_state()
        if state.get("published_dates", {}).get("evenement") == today.date().isoformat():
            return
        items = _load_json("evenements.json")
        matches = [x for x in items if isinstance(x, dict) and str(x.get("date", "")).strip() == key_date]
        if not matches:
            return
        item = random.choice(matches)
        embed = horizons_embed(title=f"📅 {item.get('titre', 'Journée thématique')}", description=str(item.get("description", "")), color=discord.Color.gold())
        if item.get("categorie"): embed.add_field(name="Catégorie", value=str(item["categorie"]), inline=True)
        if item.get("reference"): embed.add_field(name="Repère", value=str(item["reference"]), inline=True)
        embed.set_footer(text="HORIZONS • À l'occasion du calendrier du jour")
        if await _send_embed(self.bot, AGENDA_CHANNEL_ID, embed):
            state = _load_state(); state.setdefault("published_dates", {})["evenement"] = today.date().isoformat(); _save_state(state)

    @daily_thematic_event.before_loop
    async def before_daily_thematic_event(self):
        await self.bot.wait_until_ready(); await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(PublicationCalendar(bot))

"""Animation collective hebdomadaire automatique HORIZONS."""
from __future__ import annotations
import json, logging, random
from datetime import datetime, time
import discord
from discord.ext import commands, tasks
from config import COLLECTIVE_CHALLENGES_CHANNEL_ID, DATA_DIR, LOCAL_TIMEZONE
from cogs.embed_theme import horizons_embed, wait_for_logo_ready

log = logging.getLogger(__name__)
BANK_FILE = DATA_DIR / "weekly_animations.json"
HISTORY_FILE = DATA_DIR / "weekly_animations_history.json"


def load_bank() -> list[dict]:
    try:
        data = json.loads(BANK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception("Banque des animations hebdomadaires illisible.")
        return []
    return [x for x in data if isinstance(x, dict) and x.get("id") and x.get("nom") and x.get("consigne")] if isinstance(data, list) else []


def load_history() -> dict:
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_history(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(HISTORY_FILE)


def pick_animation() -> dict | None:
    bank = load_bank()
    if not bank:
        log.error("La banque weekly_animations.json ne contient aucune animation valide.")
        return None
    history = load_history()
    seen = set(history.get("seen", []))
    candidates = [item for item in bank if item["id"] not in seen]
    if not candidates:
        seen.clear()
        candidates = bank
    chosen = random.choice(candidates)
    seen.add(chosen["id"])
    history["seen"] = list(seen)[-len(bank):]
    history["last_published"] = chosen["id"]
    save_history(history)
    return chosen


class WeeklyAnimations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.friday_animation.start()

    def cog_unload(self):
        self.friday_animation.cancel()

    @tasks.loop(time=time(hour=19, minute=30, tzinfo=LOCAL_TIMEZONE))
    async def friday_animation(self):
        now = datetime.now(LOCAL_TIMEZONE)
        if now.weekday() != 4:
            return
        state = load_history()
        if state.get("published_week") == list(now.date().isocalendar()[:2]):
            return
        channel = self.bot.get_channel(COLLECTIVE_CHALLENGES_CHANNEL_ID) if COLLECTIVE_CHALLENGES_CHANNEL_ID else None
        if channel is None and COLLECTIVE_CHALLENGES_CHANNEL_ID:
            try:
                channel = await self.bot.fetch_channel(COLLECTIVE_CHALLENGES_CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                log.exception("Salon des défis collectifs inaccessible.")
                return
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            log.error("Le salon des défis collectifs doit être textuel ou Forum.")
            return
        item = pick_animation()
        if not item:
            return
        embed = horizons_embed(
            title=f"🎯 L'animation collective de la semaine — {item['nom']}",
            description=f"{item.get('description', '')}\n\n**Comment participer ?**\n{item['consigne']}",
            color=discord.Color.blurple(),
        )
        if item.get("categorie"):
            embed.add_field(name="Thème", value=str(item["categorie"]), inline=True)
        if item.get("duree"):
            embed.add_field(name="Durée indicative", value=str(item["duree"]), inline=True)
        if item.get("materiel"):
            embed.add_field(name="Matériel", value=str(item["materiel"]), inline=True)
        embed.set_footer(text="HORIZONS • Le rendez-vous collectif du vendredi")
        try:
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎯 {item['nom']}"[:100], content="L'animation collective de la semaine est ouverte !", embeds=[embed])
            else:
                await channel.send(embed=embed)
            state = load_history()
            state["published_week"] = list(now.date().isocalendar()[:2])
            state["published_at"] = now.isoformat()
            save_history(state)
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Impossible de publier l'animation collective hebdomadaire.")

    @friday_animation.before_loop
    async def before_friday_animation(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(WeeklyAnimations(bot))

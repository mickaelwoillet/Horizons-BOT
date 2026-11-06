"""Tests de publication HORIZONS sans effet sur les données de production."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    AGENDA_CHANNEL_ID, BIRTHDAY_CHANNEL_ID, COLLECTIVE_CHALLENGES_CHANNEL_ID,
    CONFESSION_CHANNEL_ID, DATA_DIR, DAILY_QUESTION_CHANNEL_ID, DEBATE_CHANNEL_ID,
    FIND_PARTNER_CHANNEL_ID, HORIZON_DAILY_CHANNEL_ID, INTRO_CHANNEL_ID,
    JOKE_DAILY_CHANNEL_ID, MISSIONS_CHANNEL_ID, QUIZ_CHANNEL_ID,
    RIDDLE_DAILY_CHANNEL_ID, STAFF_COMMANDS_CHANNEL_ID, SUCCESS_CHANNEL_ID,
)
from cogs.embed_theme import horizons_embed
from cogs.experiences import current_missions, week_key
from cogs.horizons_daily import DAILY_CONTENT, DEBATE_TOPICS
from cogs.riddles import RiddleView
from cogs.server_guides import ServerGuides
from cogs.content_utils import categories

log = logging.getLogger(__name__)


def read_json(filename: str, default=None):
    try:
        return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else []


async def fetch_channel(bot: commands.Bot, channel_id: int | None):
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    return channel


async def send_test(bot: commands.Bot, channel_id: int | None, name: str, embed: discord.Embed, view: discord.ui.View | None = None):
    channel = await fetch_channel(bot, channel_id)
    if channel is None:
        return False, f"{name} : salon introuvable ou inaccessible (ID {channel_id})."
    marker = "TEST TECHNIQUE – HORIZONS"
    embed.description = f"**{marker}**\n\n{embed.description or ''}"
    try:
        if isinstance(channel, discord.ForumChannel):
            title = (embed.title or name)[:85]
            await channel.create_thread(name=f"[TEST] {title}"[:100], content=marker, embed=embed, view=view)
        elif isinstance(channel, (discord.TextChannel, discord.Thread)):
            await channel.send(content=marker, embed=embed, view=view)
        else:
            return False, f"{name} : type de salon non pris en charge ({type(channel).__name__})."
        return True, f"{name} → #{getattr(channel, 'name', str(channel.id))}"
    except discord.Forbidden as exc:
        log.exception("Permissions insuffisantes pour le test %s dans %s", name, channel_id)
        return False, (
            f"{name} → #{getattr(channel, 'name', str(channel.id))} : "
            f"permissions insuffisantes (HTTP {getattr(exc, 'status', '?')})."
        )
    except discord.HTTPException as exc:
        log.exception("Erreur HTTP Discord pendant le test %s dans %s", name, channel_id)
        detail = (getattr(exc, "text", None) or str(exc) or "détail non fourni")[:250]
        return False, (
            f"{name} → #{getattr(channel, 'name', str(channel.id))} : "
            f"HTTP {getattr(exc, 'status', '?')} / code {getattr(exc, 'code', '?')} "
            f"({detail})."
        )


class PublicationTests(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._test_lock = asyncio.Lock()

    @app_commands.command(name="tester_publications", description="Publier un exemple de chaque publication HORIZONS dans les salons prévus.")
    @app_commands.checks.has_permissions(administrator=True)
    async def tester_publications(self, interaction: discord.Interaction):
        if self._test_lock.locked():
            await interaction.response.send_message("Un test de publications est déjà en cours. Réessaie dans quelques instants.", ephemeral=True)
            return
        await self._test_lock.acquire()
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            results: list[tuple[bool, str]] = []
            async def attempt(name, channel_id, embed, view=None):
                try:
                    results.append(await send_test(self.bot, channel_id, name, embed, view))
                except Exception as exc:  # Une erreur isolée ne bloque pas les autres salons.
                    log.exception("Erreur inattendue pendant le test %s", name)
                    results.append((False, f"{name} : erreur {type(exc).__name__} : {exc}"))

            # Anniversaire fictif : aucun membre ni aucune table SQLite n'est consulté.
            await attempt("Anniversaire", BIRTHDAY_CHANNEL_ID, horizons_embed(
                title="🎂 Joyeux anniversaire !",
                description="Aujourd'hui, HORIZONS souhaite un très bel anniversaire à **Membre de démonstration**. Que cette journée soit douce et remplie de beaux moments !",
                color=discord.Color.gold(),
            ))

            today = __import__("datetime").datetime.now(__import__("config").LOCAL_TIMEZONE).weekday()
            day_title, day_pool = DAILY_CONTENT[today]
            await attempt("Horizon du jour", HORIZON_DAILY_CHANNEL_ID, horizons_embed(title=day_title, description=day_pool[0], color=discord.Color.blurple()))

            daily_questions = read_json("questions_du_jour.json", [])
            q = next((x for x in daily_questions if isinstance(x, str) and x.strip()), "Quelle petite chose a rendu ta journée plus agréable ?")
            await attempt("Question du jour", DAILY_QUESTION_CHANNEL_ID, horizons_embed(title="💬 La question du jour", description=q, color=discord.Color.teal()))

            joke_banks = categories()
            joke_cat = sorted(joke_banks)[0] if joke_banks else None
            joke = joke_banks[joke_cat][0] if joke_cat else "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tombent dans le bateau !"
            await attempt("Blague du jour", JOKE_DAILY_CHANNEL_ID, horizons_embed(title="😄 La blague du jour", description=joke, color=discord.Color.gold()))

            riddles = read_json("devinettes.json", [])
            riddle = next((x for x in riddles if isinstance(x, dict) and x.get("question") and x.get("reponse")), None)
            if riddle:
                embed = horizons_embed(title="🧩 La devinette du jour", description=riddle["question"], color=discord.Color.teal())
                await attempt("Devinette du jour", RIDDLE_DAILY_CHANNEL_ID, embed, RiddleView(None, str(riddle["reponse"])))
            else:
                results.append((False, "Devinette du jour : aucune entrée valide dans devinettes.json."))

            quiz = read_json("quiz.json", [])
            quiz_item = next((x for x in quiz if isinstance(x, dict) and x.get("question") and x.get("reponse")), None)
            if quiz_item:
                embed = horizons_embed(title="🧠 Le quiz du jour", description=str(quiz_item["question"]), color=discord.Color.teal())
                embed.add_field(name="Réponse", value=f"||{quiz_item['reponse']}||", inline=False)
                if quiz_item.get("categorie"): embed.add_field(name="Catégorie", value=str(quiz_item["categorie"]), inline=True)
                await attempt("Quiz du jour", QUIZ_CHANNEL_ID, embed)
            else:
                results.append((False, "Quiz du jour : aucune entrée valide dans quiz.json."))

            for filename, key, title, field, channel_id, color in (
                ("citations.json", "citation", "✦ La citation du jour", "texte", HORIZON_DAILY_CHANNEL_ID, discord.Color.blurple()),
                ("proverbes.json", "proverbe", "🌿 Le proverbe du jour", "texte", HORIZON_DAILY_CHANNEL_ID, discord.Color.green()),
                ("messages.json", "message positif", "🌻 Le message bienveillant du jour", "texte", SUCCESS_CHANNEL_ID, discord.Color.gold()),
            ):
                items = read_json(filename, [])
                item = next((x for x in items if isinstance(x, dict) and x.get(field)), None)
                if item:
                    embed = horizons_embed(title=title, description=str(item[field]), color=color)
                    for optional in ("auteur", "origine", "theme", "categorie"):
                        if item.get(optional): embed.add_field(name=optional.capitalize(), value=str(item[optional]), inline=True)
                    await attempt(key.capitalize(), channel_id, embed)
                else:
                    results.append((False, f"{key.capitalize()} : banque {filename} vide ou invalide."))

            events = read_json("evenements.json", [])
            event_item = next((x for x in events if isinstance(x, dict) and x.get("titre") and x.get("description")), None)
            if event_item:
                embed = horizons_embed(title=f"📅 {event_item['titre']}", description=str(event_item["description"]), color=discord.Color.gold())
                if event_item.get("date"): embed.add_field(name="Date de référence", value=str(event_item["date"]), inline=True)
                await attempt("Journée thématique", AGENDA_CHANNEL_ID, embed)
            else:
                results.append((False, "Journée thématique : aucune entrée valide dans evenements.json."))

            await attempt("Débat hebdomadaire", DEBATE_CHANNEL_ID, horizons_embed(title="💬 Le débat de la semaine", description=DEBATE_TOPICS[0], color=discord.Color.blurple()))

            mission_embed = horizons_embed(title="🧭 Les missions de la semaine", description="Voici un aperçu des trois missions proposées. Ce test ne valide aucune progression.", color=discord.Color.blurple())
            for number, mission in enumerate(current_missions(), 1): mission_embed.add_field(name=f"Mission {number}", value=mission, inline=False)
            await attempt("Missions de la semaine", MISSIONS_CHANNEL_ID, mission_embed)

            # Les guides hebdomadaires sont construits par la classe existante, mais envoyés directement :
            # aucune écriture dans guide_publications et aucune mise à jour des messages permanents.
            try:
                guide_cog = self.bot.get_cog("ServerGuides")
                if guide_cog is None:
                    guide_cog = ServerGuides(self.bot)
                for channel_id, guide_key, guide_embed in guide_cog.weekly_embeds():
                    if guide_key.startswith("commandes_staff_"):
                        # Tous les embeds staff sont publiés comme exemples indépendants plus bas.
                        continue
                    await attempt(f"Guide {guide_key}", channel_id, guide_embed.copy())
                staff_embeds = guide_cog.staff_command_embeds(guide_cog.week_key())
                for index, guide_embed in enumerate(staff_embeds, 1):
                    await attempt(f"Guide commandes staff {index}", STAFF_COMMANDS_CHANNEL_ID, guide_embed.copy())
            except Exception as exc:
                log.exception("Impossible de construire les guides de test")
                results.append((False, f"Guides communautaires : erreur {type(exc).__name__} : {exc}"))

            games = read_json("jeux.json", [])
            game = next((x for x in games if isinstance(x, dict) and x.get("nom") and x.get("consigne")), None)
            if game:
                embed = horizons_embed(title=f"🎲 Jeu à découvrir : {game['nom']}", description=str(game["consigne"]), color=discord.Color.purple())
                if game.get("duree"): embed.add_field(name="Durée", value=str(game["duree"]), inline=True)
                if game.get("materiel"): embed.add_field(name="Matériel", value=str(game["materiel"]), inline=True)
                await attempt("Banque des jeux", COLLECTIVE_CHALLENGES_CHANNEL_ID, embed)
            else:
                results.append((False, "Banque des jeux : jeux.json vide ou invalide."))

            discussion = read_json("questions.json", [])
            discussion_item = next((x for x in discussion if isinstance(x, dict) and x.get("texte")), None)
            if discussion_item:
                embed = horizons_embed(title="💭 Une question pour échanger", description=str(discussion_item["texte"]), color=discord.Color.teal())
                if discussion_item.get("categorie"): embed.add_field(name="Thème", value=str(discussion_item["categorie"]), inline=True)
                await attempt("Banque des questions", HORIZON_DAILY_CHANNEL_ID, embed)
            else:
                results.append((False, "Banque des questions : questions.json vide ou invalide."))

            successes = [message for ok, message in results if ok]
            failures = [message for ok, message in results if not ok]
            await interaction.followup.send(
                f"**Test terminé : {len(successes)} réussite(s), {len(failures)} échec(s).**",
                ephemeral=True,
            )
            report_lines = ([f"✅ {x}" for x in successes] + [f"❌ {x}" for x in failures])
            chunk = ""
            for line in report_lines:
                candidate = f"{chunk}\n{line}" if chunk else line
                if len(candidate) > 1800:
                    await interaction.followup.send(chunk, ephemeral=True)
                    chunk = line
                else:
                    chunk = candidate
            if chunk:
                await interaction.followup.send(chunk, ephemeral=True)
        finally:
            self._test_lock.release()

    @tester_publications.error
    async def tester_publications_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            message = "Cette commande est réservée aux administrateurs du serveur."
        else:
            log.exception("Erreur de commande /tester_publications", exc_info=error)
            message = "Une erreur est survenue pendant le lancement du test. Consulte les journaux du bot."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PublicationTests(bot))

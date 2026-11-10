"""Quiz culturel HORIZONS : manches successives et classement de soirée."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed

import asyncio
import logging
import json
import random
import re
import unicodedata

import discord
from discord import app_commands
from discord.ext import commands

from config import DATA_DIR, STAFF_ROLE_ID, QUIZ_CHANNEL_ID
from .sky_map import grant as grant_sky_star

log = logging.getLogger(__name__)


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", value).strip()


class QuizAnswerModal(discord.ui.Modal, title="Ta réponse"):
    answer = discord.ui.TextInput(
        label="Réponse", placeholder="Écris ta réponse ici…", max_length=150
    )

    def __init__(self, cog: "Quizzes", guild_id: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.submit_answer(interaction, self.guild_id, str(self.answer.value))


class QuizView(discord.ui.View):
    def __init__(self, cog: "Quizzes", guild_id: int):
        super().__init__(timeout=600)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Participer", style=discord.ButtonStyle.success, emoji="🙋")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.sessions.get(self.guild_id)
        if not session or session["closed"] or session["winner"] is not None:
            await interaction.response.send_message("Cette manche est terminée.", ephemeral=True)
            return
        if interaction.user.id not in session["players"] and len(session["players"]) >= 12:
            await interaction.response.send_message(
                "La limite de 12 participants est atteinte.", ephemeral=True
            )
            return
        session["players"].add(interaction.user.id)
        session["scores"].setdefault(interaction.user.id, 0)
        await interaction.response.send_message(
            f"Tu participes ! ({len(session['players'])}/12)", ephemeral=True
        )
        await self.cog.refresh_message(self.guild_id)

    @discord.ui.button(label="Proposer une réponse", style=discord.ButtonStyle.primary, emoji="✍️")
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.cog.sessions.get(self.guild_id)
        if not session or session["closed"] or session["winner"] is not None:
            await interaction.response.send_message("Cette manche est terminée.", ephemeral=True)
            return
        if interaction.user.id not in session["players"]:
            await interaction.response.send_message(
                "Inscris-toi d'abord avec le bouton Participer.", ephemeral=True
            )
            return
        if interaction.user.id in session["answered"]:
            await interaction.response.send_message(
                "Tu as déjà proposé une réponse pour cette manche.", ephemeral=True
            )
            return
        await interaction.response.send_modal(QuizAnswerModal(self.cog, self.guild_id))

    async def on_timeout(self):
        session = self.cog.sessions.get(self.guild_id)
        if session and not session["closed"] and session["winner"] is None:
            await self.cog.finish_quiz(
                self.guild_id,
                f"⏱️ Temps écoulé ! La bonne réponse était **{session['answer']}**."
            )


class Quizzes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sessions: dict[int, dict] = {}

    def questions(self):
        path = DATA_DIR / "quiz_culturel.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [
                q for q in data
                if isinstance(q, dict) and q.get("question") and q.get("reponse")
            ]
        except (OSError, json.JSONDecodeError, TypeError):
            return []

    def make_embed(self, session: dict) -> discord.Embed:
        index = session["index"] + 1
        total = len(session["questions"])
        question = session["questions"][session["index"]]
        embed = horizons_embed(
            title=f"🧠 Quiz culturel HORIZONS • Manche {index}/{total}",
            description=question["question"],
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="Participants",
            value=f"{len(session['players'])}/12",
            inline=True,
        )
        embed.add_field(
            name="Catégorie",
            value=question.get("categorie", "Culture générale"),
            inline=True,
        )
        scores = self.score_text(session)
        embed.add_field(name="Scores", value=scores, inline=False)
        embed.add_field(
            name="Règles",
            value=(
                "Inscris-toi, puis propose une réponse. Une seule tentative par manche. "
                "Le premier à trouver marque un point."
            ),
            inline=False,
        )
        embed.set_footer(text="HORIZONS • 10 minutes par manche • Culture, curiosité et bonne humeur")
        return embed

    @staticmethod
    def score_text(session: dict) -> str:
        scores = session["scores"]
        if not scores:
            return "Aucun point pour le moment."
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:8]
        lines = []
        for user_id, score in ordered:
            lines.append(f"<@{user_id}> — **{score}** point(s)")
        return "\n".join(lines)

    async def refresh_message(self, guild_id: int):
        session = self.sessions.get(guild_id)
        if not session or not session.get("message_id"):
            return
        channel = self.bot.get_channel(session["channel_id"])
        if not channel:
            return
        try:
            message = await channel.fetch_message(session["message_id"])
            await message.edit(embed=self.make_embed(session))
        except discord.HTTPException:
            pass

    async def submit_answer(self, interaction: discord.Interaction, guild_id: int, answer: str):
        session = self.sessions.get(guild_id)
        if not session or session["closed"] or session["winner"] is not None:
            await interaction.response.send_message("Cette manche est terminée.", ephemeral=True)
            return
        if interaction.user.id not in session["players"]:
            await interaction.response.send_message(
                "Inscris-toi d'abord avec le bouton Participer.", ephemeral=True
            )
            return
        if interaction.user.id in session["answered"]:
            await interaction.response.send_message(
                "Tu as déjà proposé une réponse pour cette manche.", ephemeral=True
            )
            return

        session["answered"].add(interaction.user.id)
        if normalize(answer) == normalize(session["answer"]):
            session["winner"] = interaction.user.id
            session["scores"][interaction.user.id] = session["scores"].get(interaction.user.id, 0) + 1
            # Récompense uniquement une réponse correcte vérifiée par le quiz.
            # Un échec SQLite ne doit jamais empêcher la fin de la manche.
            try:
                if grant_sky_star(guild_id, interaction.user.id, "origins.quiz"):
                    log.info("Étoile Esprit Curieux attribuée au membre %s", interaction.user.id)
            except Exception:
                log.exception("Échec de l'attribution de l'étoile quiz au membre %s", interaction.user.id)
            await interaction.response.send_message(
                "🎉 Bonne réponse ! Tu remportes cette manche et marques un point !",
                ephemeral=True,
            )
            channel = self.bot.get_channel(session["channel_id"])
            if channel:
                await channel.send(
                    f"🏆 Bravo {interaction.user.mention} ! La bonne réponse était "
                    f"**{session['answer']}**."
                )
            await asyncio.sleep(2)
            await self.advance_round(guild_id)
        else:
            await interaction.response.send_message(
                "Ce n'est pas la bonne réponse. Tu as utilisé ton essai pour cette manche !",
                ephemeral=True,
            )

    async def advance_round(self, guild_id: int):
        session = self.sessions.get(guild_id)
        if not session or session["closed"]:
            return
        previous_view = session.get("view")
        if previous_view:
            previous_view.stop()
        session["index"] += 1
        if session["index"] >= len(session["questions"]):
            await self.finish_quiz(guild_id, "🏁 Toutes les manches sont terminées !")
            return
        question = session["questions"][session["index"]]
        session["answer"] = question["reponse"]
        session["answered"] = set()
        session["winner"] = None
        channel = self.bot.get_channel(session["channel_id"])
        if not channel:
            session["closed"] = True
            return
        view = QuizView(self, guild_id)
        session["view"] = view
        try:
            message = await channel.fetch_message(session["message_id"])
            await message.edit(embed=self.make_embed(session), view=view)
        except discord.HTTPException:
            message = await channel.send(embed=self.make_embed(session), view=view)
            session["message_id"] = message.id

    async def finish_quiz(self, guild_id: int, announcement: str):
        session = self.sessions.get(guild_id)
        if not session or session["closed"]:
            return
        session["closed"] = True
        active_view = session.get("view")
        if active_view:
            active_view.stop()
        channel = self.bot.get_channel(session["channel_id"])
        if not channel:
            return
        scores = session["scores"]
        if scores:
            ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            lines = [
                f"**{position}.** <@{uid}> — {score} point(s)"
                for position, (uid, score) in enumerate(ordered, 1)
            ]
            leaderboard = "\n".join(lines)
        else:
            leaderboard = "Aucun participant n'a marqué de point."
        embed = horizons_embed(
            title="🏆 Classement du quiz HORIZONS",
            description=f"{announcement}\n\n{leaderboard}",
            color=discord.Color.gold(),
        )
        try:
            message = await channel.fetch_message(session["message_id"])
            await message.edit(view=None)
            await channel.send(embed=embed)
        except discord.HTTPException:
            await channel.send(embed=embed)
        # Le classement reste publié par le bot ; NOX peut le commenter (option admin).
        from .nox_events import quiz as nox_quiz
        winner = ordered[0][0] if scores else None
        await nox_quiz(channel, str(session["message_id"]), winner)

    async def quiz_lancer(
        self,
        interaction: discord.Interaction,
        manches: app_commands.Range[int, 1, 10] = 5,
    ):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_messages
            or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles))
        )
        if not allowed:
            await interaction.response.send_message(
                "Le lancement d'un quiz est réservé à l'équipe.", ephemeral=True
            )
            return
        pool = self.questions()
        if not pool:
            await interaction.response.send_message(
                "La banque de questions est indisponible.", ephemeral=True
            )
            return
        if interaction.guild_id in self.sessions and not self.sessions[interaction.guild_id]["closed"]:
            await interaction.response.send_message(
                "Un quiz est déjà en cours sur ce serveur.", ephemeral=True
            )
            return
        target = interaction.guild.get_channel(QUIZ_CHANNEL_ID) if QUIZ_CHANNEL_ID else interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                "Le salon du quiz n'est pas configuré ou accessible.", ephemeral=True
            )
            return

        selected = random.sample(pool, min(manches, len(pool)))
        self.sessions[interaction.guild_id] = {
            "questions": selected,
            "index": 0,
            "answer": selected[0]["reponse"],
            "players": set(),
            "answered": set(),
            "scores": {},
            "winner": None,
            "closed": False,
            "channel_id": target.id,
            "message_id": None,
            "view": None,
        }
        session = self.sessions[interaction.guild_id]
        await interaction.response.send_message(
            f"Le quiz de **{len(selected)} manche(s)** est lancé dans {target.mention} !",
            ephemeral=True,
        )
        view = QuizView(self, interaction.guild_id)
        session["view"] = view
        message = await target.send(embed=self.make_embed(session), view=view)
        session["message_id"] = message.id

    async def quiz_arreter(self, interaction: discord.Interaction):
        member = interaction.user
        allowed = isinstance(member, discord.Member) and (
            member.guild_permissions.administrator
            or (STAFF_ROLE_ID and any(r.id == STAFF_ROLE_ID for r in member.roles))
        )
        if not allowed:
            await interaction.response.send_message("Commande réservée à l'équipe.", ephemeral=True)
            return
        session = self.sessions.get(interaction.guild_id)
        if not session or session["closed"]:
            await interaction.response.send_message("Aucun quiz n'est en cours.", ephemeral=True)
            return
        await interaction.response.send_message("Le quiz est arrêté. Le classement final est publié.")
        await self.finish_quiz(interaction.guild_id, "⛔ Quiz arrêté par l'équipe.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Quizzes(bot))

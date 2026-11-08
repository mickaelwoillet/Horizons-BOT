"""Question du jour et messages positifs de la communauté."""
from __future__ import annotations
from cogs.embed_theme import horizons_embed, wait_for_logo_ready
import json, random
from datetime import time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import DATA_DIR, DAILY_QUESTION_CHANNEL_ID, LOCAL_TIMEZONE
from .content_utils import load_json, save_json

STATE = DATA_DIR / "community_history.json"

class Community(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_question.start()

    def cog_unload(self): self.daily_question.cancel()

    def pick_question(self) -> str | None:
        questions = load_json(DATA_DIR / "questions_du_jour.json", [])
        questions = [q for q in questions if isinstance(q,str) and q.strip()]
        if not questions: return None
        state = load_json(STATE, {"questions":[]})
        seen = set(state.get("questions",[]))
        choices = [q for q in questions if q not in seen]
        if not choices: seen.clear(); choices = questions
        chosen = random.choice(choices)
        seen.add(chosen); state["questions"] = list(seen)[-100:]
        save_json(STATE,state)
        return chosen

    @app_commands.command(name="question_du_jour", description="Afficher une question pour lancer la conversation.")
    async def question_du_jour(self, interaction: discord.Interaction):
        question = self.pick_question()
        if not question: await interaction.response.send_message("Aucune question n'est disponible.", ephemeral=True); return
        await interaction.response.send_message(embed=horizons_embed(title="💬 Et si on échangeait ?", description=question, color=discord.Color.teal()))

    @app_commands.command(name="compliment", description="Offrir un mot positif à quelqu'un de la communauté.")
    async def compliment(self, interaction: discord.Interaction, membre: discord.Member | None = None):
        messages = load_json(DATA_DIR / "compliments.json", [])
        messages = [m for m in messages if isinstance(m,str) and m.strip()]
        if not messages: await interaction.response.send_message("Les messages positifs ne sont pas disponibles.", ephemeral=True); return
        target = membre or interaction.user
        if target.bot: await interaction.response.send_message("Choisis une personne de la communauté.", ephemeral=True); return
        text = random.choice(messages)
        embed = horizons_embed(title="🌻 Une pensée positive", description=f"{target.mention}, {text}", color=discord.Color.gold())
        embed.set_footer(text=f"Offert par {interaction.user.display_name} • HORIZONS")
        await interaction.response.send_message(embed=embed)

    @tasks.loop(time=time(hour=11,minute=30,tzinfo=LOCAL_TIMEZONE))
    async def daily_question(self):
        channel = self.bot.get_channel(DAILY_QUESTION_CHANNEL_ID) if DAILY_QUESTION_CHANNEL_ID else None
        if channel is None and DAILY_QUESTION_CHANNEL_ID:
            try: channel = await self.bot.fetch_channel(DAILY_QUESTION_CHANNEL_ID)
            except discord.HTTPException: return
        if channel is None: return
        question = self.pick_question()
        if question:
            embed = horizons_embed(
                title="💬 La question du jour",
                description=question,
                color=discord.Color.teal(),
            )
            try:
                if isinstance(channel, discord.ForumChannel):
                    # Un salon Forum reçoit des publications (threads), pas des messages classiques.
                    # Le titre Discord est limité à 100 caractères ; l'embed conserve la question complète.
                    thread_title = question.strip()
                    if len(thread_title) > 100:
                        thread_title = thread_title[:97].rstrip() + "..."

                    await channel.create_thread(
                        name=thread_title,
                        content="💬 La question du jour est lancée ! Répondez directement sous cette publication.",
                        embeds=[embed],
                    )
                elif isinstance(channel, (discord.TextChannel)):
                    # Compatibilité avec un salon textuel si le salon est changé ultérieurement.
                    await channel.send(embed=embed)
                else:
                    print(
                        f"[Community] Le salon configuré pour la question du jour "
                        f"n'est ni un Forum ni un salon textuel (type : {type(channel).__name__})."
                    )
            except discord.Forbidden as exc:
                print(f"[Community] Permissions insuffisantes pour publier la question du jour : {exc}")
            except discord.HTTPException as exc:
                print(f"[Community] Erreur Discord pendant la publication de la question du jour : {exc}")

    @daily_question.before_loop
    async def before_daily_question(self):
        await self.bot.wait_until_ready()
        await wait_for_logo_ready()

async def setup(bot: commands.Bot): await bot.add_cog(Community(bot))

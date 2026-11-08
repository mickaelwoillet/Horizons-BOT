"""Mini-jeux interactifs et progression XP Célestes, séparés des routines quotidiennes."""
from __future__ import annotations
import json, random, re, unicodedata
from datetime import datetime
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks
from cogs.embed_theme import horizons_embed
from cogs.storage import db
from cogs.arcade_games import ArcadeMenuView
from cogs.arcade_progress import ProgressView, record_game_result
from config import LOCAL_TIMEZONE

ROOT = Path(__file__).resolve().parents[1]
ARCADE_QUIZ = [
 {"q":"Quelle planète possède les anneaux les plus visibles ?","a":"saturne","choices":["Mars","Saturne","Vénus","Mercure"]},
 {"q":"Combien de côtés possède un hexagone ?","a":"6","choices":["5","6","7","8"]},
 {"q":"Quel océan est le plus vaste ?","a":"pacifique","choices":["Atlantique","Indien","Pacifique","Arctique"]},
 {"q":"Quel est le symbole chimique de l'or ?","a":"au","choices":["Ag","Or","Au","Fe"]},
 {"q":"Dans quel pays se trouve Kyoto ?","a":"japon","choices":["Chine","Japon","Corée du Sud","Thaïlande"]},
 {"q":"Combien de minutes dure une heure et demie ?","a":"90","choices":["60","75","90","120"]},
 {"q":"Quel instrument possède généralement 88 touches ?","a":"piano","choices":["Violon","Piano","Flûte","Harpe"]},
 {"q":"Quel gaz les plantes absorbent-elles principalement ?","a":"dioxyde de carbone","choices":["Oxygène","Azote","Dioxyde de carbone","Hydrogène"]},
 {"q":"Quelle est la langue officielle du Brésil ?","a":"portugais","choices":["Espagnol","Portugais","Français","Anglais"]},
 {"q":"Combien de couleurs compte traditionnellement l'arc-en-ciel ?","a":"7","choices":["5","6","7","8"]},
]
ANAGRAMS = [("CHIEN","NICHE"),("IMAGE","MAGIE"),("MARIE","AIMER"),("TRACE","CARTE"),("RAME","MARE"),("LAME","MALE"),("GARE","RAGE"),("PARE","RAPE"),("SOIN","IONS"),("NAGE","ANGE")]
RIDDLES = [
 ("Je peux être pleine ou nouvelle, mais je ne suis jamais vide de lumière. Qui suis-je ?","lune"),
 ("Plus je sèche, plus je deviens mouillée. Qui suis-je ?","serviette"),
 ("Je grandis sans être vivant et je disparais quand on me donne à boire. Qui suis-je ?","feu"),
 ("Je voyage autour du monde en restant dans un coin. Qui suis-je ?","timbre"),
 ("On me casse avant de m'utiliser. Qui suis-je ?","oeuf"),
 ("Je suis toujours devant toi, mais tu ne peux jamais me voir. Qui suis-je ?","avenir"),
 ("J'ai des aiguilles mais je ne couds pas. Qui suis-je ?","horloge"),
 ("Je réponds sans parler et je répète sans comprendre. Qui suis-je ?","echo"),
]
DAILY_CAP = 60


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if not unicodedata.combining(c)).strip().replace("’", "'")


def xp_level(xp: int) -> tuple[int, str]:
    level = 1 + xp // 50
    if level >= 30: title = "Maître des horizons"
    elif level >= 20: title = "Gardien des constellations"
    elif level >= 10: title = "Voyageur des étoiles"
    elif level >= 5: title = "Observateur céleste"
    else: title = "Explorateur"
    return level, title


def award_xp(guild_id: int, user_id: int, game_key: str, amount: int = 5) -> int:
    """Attribue une récompense par jeu et par jour, avec plafond journalier global."""
    now = datetime.now(LOCAL_TIMEZONE)
    day = now.date().isoformat()
    stamp = now.isoformat(timespec="seconds")
    with db() as conn:
        # Verrouille la transaction avant lecture pour éviter deux récompenses
        # simultanées si plusieurs interactions arrivent au même instant.
        conn.execute("BEGIN IMMEDIATE")
        exists = conn.execute("SELECT 1 FROM celestial_game_rewards WHERE guild_id=? AND user_id=? AND reward_date=? AND game_key=?", (guild_id,user_id,day,game_key)).fetchone()
        if exists: return 0
        total = conn.execute("SELECT COALESCE(SUM(xp_awarded),0) FROM celestial_game_rewards WHERE guild_id=? AND user_id=? AND reward_date=?", (guild_id,user_id,day)).fetchone()[0]
        awarded = max(0, min(amount, DAILY_CAP - int(total)))
        if awarded <= 0: return 0
        conn.execute("INSERT INTO celestial_game_rewards(guild_id,user_id,reward_date,game_key,xp_awarded,created_at) VALUES(?,?,?,?,?,?)", (guild_id,user_id,day,game_key,awarded,stamp))
        conn.execute("INSERT INTO celestial_game_xp(guild_id,user_id,xp,updated_at) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=xp+excluded.xp, updated_at=excluded.updated_at", (guild_id,user_id,awarded,stamp))
        return awarded


def total_xp(guild_id: int, user_id: int) -> int:
    with db() as conn:
        row = conn.execute("SELECT xp FROM celestial_game_xp WHERE guild_id=? AND user_id=?", (guild_id,user_id)).fetchone()
        return int(row[0]) if row else 0


class AnswerModal(discord.ui.Modal):
    def __init__(self, cog: "HorizonsArcade", owner_id: int, game_key: str, prompt: str, expected: str, reward: int = 10, shared: bool = False, parent_view: "AnswerView | None" = None):
        super().__init__(title="Ta réponse")
        self.cog, self.owner_id, self.game_key = cog, owner_id, game_key
        self.expected, self.reward, self.shared, self.parent_view = normalize(expected), reward, shared, parent_view
        self.answer = discord.ui.TextInput(label=prompt[:45], placeholder="Écris ta réponse ici…", max_length=100, required=True)
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.shared and interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette partie ne t'est pas destinée.", ephemeral=True); return
        if self.parent_view and (self.parent_view.is_finished() or interaction.user.id in self.parent_view.responded):
            await interaction.response.send_message("Tu as déjà répondu ou cette partie est terminée.", ephemeral=True); return
        if self.parent_view:
            self.parent_view.responded.add(interaction.user.id)
        if normalize(str(self.answer.value)) == self.expected:
            points = award_xp(interaction.guild_id, interaction.user.id, self.game_key, self.reward) if interaction.guild_id else 0
            if interaction.guild_id:
                record_game_result(interaction.guild_id, self.game_key, "collectif" if self.shared else "solo", [interaction.user.id], winners=[interaction.user.id], status="completed")
            await interaction.response.send_message(f"🎉 Bonne réponse ! **+{points} XP Célestes**. {self.cog.xp_line(interaction.guild_id, interaction.user.id)}", ephemeral=True)
        else:
            if interaction.guild_id:
                record_game_result(interaction.guild_id, self.game_key, "collectif" if self.shared else "solo", [interaction.user.id], status="loss")
            await interaction.response.send_message("Pas tout à fait ! Cette tentative est enregistrée ; tu pourras rejouer lors d'une prochaine partie. 🌠", ephemeral=True)


class AnswerView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", owner_id: int, game_key: str, prompt: str, expected: str, reward: int = 10, shared: bool = False):
        super().__init__(timeout=300)
        self.cog, self.owner_id, self.game_key, self.prompt, self.expected, self.reward, self.shared = cog, owner_id, game_key, prompt, expected, reward, shared
        self.responded: set[int] = set()

    @discord.ui.button(label="Proposer ma réponse", style=discord.ButtonStyle.primary, emoji="✍️")
    async def answer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.responded:
            await interaction.response.send_message("Tu as déjà répondu à cette partie.", ephemeral=True)
            return
        await interaction.response.send_modal(AnswerModal(self.cog, self.owner_id, self.game_key, self.prompt, self.expected, self.reward, self.shared, self))


class CoinView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(timeout=60); self.cog, self.owner_id = cog, owner_id; self.used = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette pièce est réservée à la personne qui a lancé la partie.", ephemeral=True); return False
        if self.used:
            await interaction.response.send_message("Cette partie est déjà terminée.", ephemeral=True); return False
        return True

    async def flip(self, interaction: discord.Interaction, guess: str):
        self.used = True; result = random.choice(("Pile", "Face")); self.stop()
        won = guess == result
        points = award_xp(interaction.guild_id, interaction.user.id, "pileface", 5) if won and interaction.guild_id else 0
        if interaction.guild_id:
            record_game_result(interaction.guild_id, "pileface", "solo", [interaction.user.id], winners=[interaction.user.id] if won else [], status="completed" if won else "loss")
        for child in self.children: child.disabled = True
        await interaction.response.edit_message(embed=horizons_embed(title="🪙 Résultat du pile ou face", description=f"La pièce tombe sur **{result}**.\n" + (f"Bien joué ! **+{points} XP Célestes** 🌟" if guess == result else "Ce sera pour la prochaine fois !")), view=self)

    @discord.ui.button(label="Pile", style=discord.ButtonStyle.primary, emoji="🪙")
    async def pile(self, interaction: discord.Interaction, button: discord.ui.Button): await self.flip(interaction, "Pile")
    @discord.ui.button(label="Face", style=discord.ButtonStyle.secondary, emoji="✨")
    async def face(self, interaction: discord.Interaction, button: discord.ui.Button): await self.flip(interaction, "Face")


class ReflexView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(timeout=20); self.cog, self.owner_id = cog, owner_id; self.started = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ce défi appartient à la personne qui l'a lancé.", ephemeral=True); return False
        return True

    @discord.ui.button(label="C'est parti !", style=discord.ButtonStyle.success, emoji="⚡")
    async def go(self, interaction: discord.Interaction, button: discord.ui.Button):
        import time
        elapsed = (time.perf_counter() - self.started) * 1000 if self.started else None
        self.stop(); button.disabled = True
        if elapsed is None:
            if interaction.guild_id:
                record_game_result(interaction.guild_id, "reflexe", "solo", [interaction.user.id], status="loss")
            await interaction.response.edit_message(content="Le signal n'était pas prêt. Relance `/reflexe`.", view=self); return
        points = award_xp(interaction.guild_id, interaction.user.id, "reflexe", 5) if elapsed >= 0 and interaction.guild_id else 0
        if interaction.guild_id:
            record_game_result(interaction.guild_id, "reflexe", "solo", [interaction.user.id], winners=[interaction.user.id], status="completed")
        await interaction.response.edit_message(embed=horizons_embed(title="⚡ Ton temps de réaction", description=f"**{elapsed:.0f} ms**\n**+{points} XP Célestes**"), view=self)

    async def arm(self, message: discord.Message):
        import asyncio, time
        await asyncio.sleep(random.uniform(2.0, 5.0))
        self.started = time.perf_counter()
        self.children[0].label = "MAINTENANT !"
        await message.edit(embed=horizons_embed(title="⚡ Réflexe !", description="Clique maintenant, le plus vite possible !"), view=self)


class CollectiveAnswerModal(discord.ui.Modal):
    def __init__(self, session: "CollectiveGameView", user_id: int):
        super().__init__(title="Participer au défi collectif")
        self.session, self.user_id = session, user_id
        label = "Ton nombre (1 à 10)" if session.game == "nombre" else "Ta réponse"
        self.answer = discord.ui.TextInput(label=label, placeholder="Écris ta réponse…", max_length=100)
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Cette réponse ne t'est pas destinée.", ephemeral=True); return
        await self.session.submit_answer(interaction, str(self.answer.value))


class CollectiveGameView(discord.ui.View):
    """Une partie publique : chaque membre participe une fois, avec score partagé."""
    def __init__(self, cog: "HorizonsArcade", game: str, creator_id: int, expected: str = "", reward: int = 10):
        super().__init__(timeout=600)
        self.cog, self.game, self.creator_id, self.expected, self.reward = cog, game, creator_id, normalize(expected), reward
        self.players: dict[int, str] = {}
        self.message: discord.Message | None = None
        self.started_at: float | None = None
        self.finished = False
        if game in ("quiz", "anagramme", "enigme", "nombre"):
            self.add_item(self._button("Proposer ma réponse", "answer", discord.ButtonStyle.primary, "✍️"))
        elif game == "de":
            self.add_item(self._button("Lancer le dé", "roll", discord.ButtonStyle.primary, "🎲"))
        elif game == "pileface":
            self.add_item(self._button("Pile", "pile", discord.ButtonStyle.primary, "🪙"))
            self.add_item(self._button("Face", "face", discord.ButtonStyle.secondary, "✨"))
        elif game == "reflexe":
            self.add_item(self._button("Attendre le signal…", "reflex", discord.ButtonStyle.success, "⚡"))
        self.add_item(self._button("Terminer le défi", "stop", discord.ButtonStyle.danger, "⏹️"))

    def _button(self, label: str, action: str, style: discord.ButtonStyle, emoji: str):
        button = discord.ui.Button(label=label, style=style, emoji=emoji, custom_id=f"horizons_collective_{action}")
        async def callback(interaction: discord.Interaction):
            if self.finished:
                await interaction.response.send_message("Ce défi est terminé.", ephemeral=True); return
            if action == "stop":
                if interaction.user.id != self.creator_id:
                    await interaction.response.send_message("Seule la personne qui a lancé ce défi peut le terminer.", ephemeral=True); return
                self.finished = True
                for child in self.children: child.disabled = True
                await interaction.response.edit_message(embed=self.cog.collective_summary(self), view=self)
                self.stop()
                self.cog.release_collective_session(interaction.guild_id, interaction.channel_id)
                return
            if interaction.user.id in self.players:
                await interaction.response.send_message("Tu as déjà participé à ce défi !", ephemeral=True); return
            if action == "answer":
                await interaction.response.send_modal(CollectiveAnswerModal(self, interaction.user.id)); return
            if action == "reflex":
                if self.started_at is None:
                    await interaction.response.send_message("Le signal n'est pas encore apparu. Patiente !", ephemeral=True); return
                import time
                elapsed = (time.perf_counter() - self.started_at) * 1000
                await self._record(interaction, f"{elapsed:.0f} ms", 5)
                return
            if action == "roll":
                result = random.randint(1, 6)
                await self._record(interaction, f"🎲 {result}", 5)
            elif action in ("pile", "face"):
                outcome = random.choice(("pile", "face"))
                won = action == outcome
                await self._record(interaction, f"{action.title()} — " + ("bonne prédiction" if won else f"la pièce est tombée sur {outcome}"), 5 if won else 0)
        button.callback = callback
        return button

    async def submit_answer(self, interaction: discord.Interaction, answer: str):
        if self.finished or interaction.user.id in self.players:
            await interaction.response.send_message("Tu as déjà participé ou le défi est terminé.", ephemeral=True); return
        normalized = normalize(answer)
        if self.game == "nombre":
            try: correct = int(normalized) == int(self.expected)
            except ValueError: correct = False
        else:
            correct = normalized == self.expected
        if correct:
            await self._record(interaction, "Bonne réponse !", self.reward)
            await interaction.followup.send("🎉 Bravo, tu as trouvé !", ephemeral=True)
        else:
            self.players[interaction.user.id] = "Réponse à retenter"
            game_keys = {"nombre": "nombre_mystere", "quiz": "quizjeu", "anagramme": "anagramme", "enigme": "enigme"}
            if interaction.guild_id:
                record_game_result(interaction.guild_id, game_keys[self.game], "collectif", [interaction.user.id], status="loss")
            await interaction.response.send_message("Pas tout à fait ! Ta participation est enregistrée pour ce défi.", ephemeral=True)
            await self.refresh_message()

    async def _record(self, interaction: discord.Interaction, result: str, reward: int):
        self.players[interaction.user.id] = result
        game_keys = {"de":"de", "pileface":"pileface", "nombre":"nombre_mystere", "quiz":"quizjeu", "anagramme":"anagramme", "enigme":"enigme", "reflexe":"reflexe"}
        points = award_xp(interaction.guild_id, interaction.user.id, game_keys[self.game], reward) if interaction.guild_id and reward else 0
        if interaction.guild_id:
            if self.game == "de":
                record_game_result(interaction.guild_id, game_keys[self.game], "collectif", [interaction.user.id], status="completed")
            else:
                won = reward > 0
                record_game_result(interaction.guild_id, game_keys[self.game], "collectif", [interaction.user.id], winners=[interaction.user.id] if won else [], status="completed" if won else "loss")
        if reward:
            self.players[interaction.user.id] = f"{result} · +{points} XP"
        await interaction.response.send_message(f"Participation enregistrée ! {result} · **+{points} XP Célestes**", ephemeral=True)
        await self.refresh_message()

    async def refresh_message(self):
        if not self.message: return
        lines = [f"• <@{uid}> — {result}" for uid, result in list(self.players.items())[-15:]]
        description = (f"Défi ouvert à tous les membres. Une participation par personne.\n\n"
                       f"**Participants : {len(self.players)}**\n" + ("\n".join(lines) if lines else "À toi d'ouvrir le bal !"))
        if self.game == "reflexe" and self.started_at is None:
            description += "\n\nLe signal apparaîtra automatiquement après quelques secondes."
        await self.message.edit(embed=horizons_embed(title="🤝 Défi collectif HORIZONS", description=description), view=self)

    async def on_timeout(self):
        self.finished = True
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=self.cog.collective_summary(self), view=self)
            except discord.HTTPException:
                pass
            self.cog.release_collective_session(self.message.guild.id if self.message.guild else None, self.message.channel.id)

    async def arm_reflex(self):
        import asyncio, time
        await asyncio.sleep(random.uniform(3.0, 6.0))
        if self.is_finished(): return
        self.started_at = time.perf_counter()
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.custom_id and item.custom_id.endswith("reflex"):
                item.label = "⚡ MAINTENANT !"
        await self.refresh_message()


class HorizonsArcade(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_collective_sessions: dict[tuple[int, int], discord.ui.View] = {}
        self.refresh_arcade_info.start()

    def release_collective_session(self, guild_id: int | None, channel_id: int | None):
        if guild_id is not None and channel_id is not None:
            self.active_collective_sessions.pop((guild_id, channel_id), None)

    def collective_summary(self, view: CollectiveGameView) -> discord.Embed:
        lines = [f"• <@{uid}> — {result}" for uid, result in list(view.players.items())[-20:]]
        details = f"Défi terminé. **{len(view.players)} participation(s)** enregistrée(s)."
        if lines: details += "\n\n" + "\n".join(lines)
        else: details += "\n\nPersonne n'a participé cette fois."
        return horizons_embed(title="🏁 Résultat du défi collectif", description=details)

    def cog_unload(self):
        self.refresh_arcade_info.cancel()

    def build_arcade_embed(self) -> discord.Embed:
        embed = horizons_embed(title="🎮 L'Arcade HORIZONS", description="Choisis un jeu avec `/jeux` et lance une partie grâce aux menus interactifs. Les blagues, devinettes et quiz quotidiens restent dans leurs salons habituels : ils ne font pas partie de cette progression.")
        embed.add_field(name="🕹️ Jeux interactifs", value="⭕ **Morpion** — solo contre l'IA (3 niveaux) ou duel.\n🔴 **Puissance 4** — duel au tour par tour.\n🧠 **Memory** — retrouver les huit paires en solo.\n🔐 **Code secret** — déchiffrer une combinaison en solo.\n📝 **Petit Bac** — partie collective chronométrée et vote sur les réponses ambiguës.\n🚢 **Bataille navale** — duel avec grilles privées en messages directs.", inline=False)
        embed.add_field(name="🎲 Jeux historiques", value="Les commandes existantes `/de`, `/pileface`, `/nombre_mystere`, `/quizjeu`, `/anagramme`, `/enigme`, `/reflexe` et `/arcade_collectif` restent disponibles pendant la transition.", inline=False)
        embed.add_field(name="🌠 Soirées Arcade", value="Ouvre un salon d'attente depuis `/jeux`, rassemble jusqu'à douze membres et lance trois manches collectives chronométrées.", inline=False)
        embed.add_field(name="🌟 XP Célestes", value="Les parties et bonnes réponses rapportent des XP. Une récompense par mini-jeu et par jour, avec un plafond de **60 XP par jour** pour préserver l'équité.", inline=False)
        embed.set_footer(text="HORIZONS • Les routines quotidiennes restent indépendantes")
        return embed

    def arcade_channel_id(self, guild: discord.Guild) -> int | None:
        """Récupère le salon Arcade depuis SQLite ou le détecte sans modifier Discord."""
        setting_key = f"ludic:{guild.id}:arcade_channel_id"
        with db() as conn:
            row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (setting_key,)).fetchone()
        if row:
            try:
                channel_id = int(json.loads(row[0]))
                channel = guild.get_channel(channel_id)
                if isinstance(channel, discord.TextChannel):
                    return channel_id
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        candidates = [channel for channel in guild.text_channels if channel.name == "🎮・arcade-horizons"]
        if not candidates:
            candidates = [channel for channel in guild.text_channels if "arcade-horizons" in channel.name]
        if not candidates:
            return None
        channel_id = candidates[0].id
        with db() as conn:
            conn.execute(
                "INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (setting_key, json.dumps(channel_id)),
            )
        return channel_id

    def award_game_xp(self, guild_id: int | None, user_id: int, game_key: str, amount: int = 10) -> int:
        return award_xp(guild_id, user_id, game_key, amount) if guild_id else 0

    @tasks.loop(hours=2)
    async def refresh_arcade_info(self):
        for guild in self.bot.guilds:
            channel_id = self.arcade_channel_id(guild)
            with db() as conn:
                msg_row = conn.execute("SELECT value FROM bot_settings WHERE key=?", (f"ludic:{guild.id}:arcade_info_message_id",)).fetchone()
            if not channel_id:
                continue
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue
            # Republier le panneau pour qu'il revienne en bas du salon, au-dessus
            # des échanges récents. Seul notre ancien panneau est supprimé.
            try:
                if msg_row:
                    try:
                        old_message = await channel.fetch_message(int(json.loads(msg_row[0])))
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                        pass
                message = await channel.send(embed=self.build_arcade_embed())
                with db() as conn:
                    conn.execute("INSERT INTO bot_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (f"ludic:{guild.id}:arcade_info_message_id", json.dumps(message.id)))
            except (discord.Forbidden, discord.HTTPException):
                pass

    @refresh_arcade_info.before_loop
    async def before_refresh_arcade_info(self):
        await self.bot.wait_until_ready()

    def xp_line(self, guild_id: int | None, user_id: int) -> str:
        if not guild_id: return ""
        xp = total_xp(guild_id,user_id); level,title = xp_level(xp)
        return f"Tu possèdes **{xp} XP** · niveau **{level} — {title}**."

    async def require_arcade_channel(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild_id:
            await interaction.response.send_message("Cette commande est disponible sur le serveur HORIZONS.", ephemeral=True); return False
        channel_id = self.arcade_channel_id(interaction.guild)
        if not channel_id:
            await interaction.response.send_message("Je ne trouve pas le salon `🎮・arcade-horizons`. L'équipe doit vérifier son nom et mes accès.", ephemeral=True)
            return False
        if interaction.channel_id != channel_id:
            channel = interaction.guild.get_channel(channel_id) if interaction.guild else None
            mention = channel.mention if channel else "le salon Arcade HORIZONS"
            await interaction.response.send_message(f"Les mini-jeux se jouent dans {mention} !", ephemeral=True); return False
        return True

    @app_commands.command(name="jeux", description="Découvrir les mini-jeux interactifs HORIZONS.")
    async def jeux(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction):
            return
        view = ArcadeMenuView(self, interaction.user.id)
        await interaction.response.send_message(embed=view.menu_embed(), view=view, ephemeral=True)

    @app_commands.command(name="xpjeux", description="Consulter ta progression et tes XP Célestes.")
    async def xpjeux(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("Ton passeport céleste est disponible sur le serveur HORIZONS.", ephemeral=True)
            return
        xp = total_xp(interaction.guild_id, interaction.user.id)
        level, title = xp_level(xp)
        view = ProgressView(interaction.guild_id, interaction.user.id, xp, level, title)
        await interaction.response.send_message(embed=view.overview_embed(), view=view, ephemeral=True)

    @app_commands.command(name="de", description="Lancer un dé à six faces et gagner des XP Célestes.")
    async def de(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        result = random.randint(1,6); points = award_xp(interaction.guild_id,interaction.user.id,"de",5) if interaction.guild_id else 0
        if interaction.guild_id:
            record_game_result(interaction.guild_id, "de", "solo", [interaction.user.id], status="completed", scores={interaction.user.id: result})
        await interaction.response.send_message(embed=horizons_embed(title="🎲 Le dé HORIZONS", description=f"Le dé affiche **{result}** !\n**+{points} XP Célestes**"))

    @app_commands.command(name="pileface", description="Tenter ta chance au pile ou face.")
    async def pileface(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        await interaction.response.send_message(embed=horizons_embed(title="🪙 Pile ou face", description="Choisis le côté de la pièce. Bonne chance !"), view=CoinView(self,interaction.user.id), ephemeral=True)

    @app_commands.command(name="nombre_mystere", description="Trouver le nombre mystère entre 1 et 10.")
    @app_commands.describe(proposition="Ton nombre, entre 1 et 10")
    async def nombre_mystere(self, interaction: discord.Interaction, proposition: app_commands.Range[int,1,10]):
        if not await self.require_arcade_channel(interaction): return
        secret = random.randint(1,10)
        if proposition == secret:
            points = award_xp(interaction.guild_id,interaction.user.id,"nombre_mystere",10) if interaction.guild_id else 0
            if interaction.guild_id:
                record_game_result(interaction.guild_id, "nombre_mystere", "solo", [interaction.user.id], winners=[interaction.user.id], status="completed")
            text = f"🎉 Exact ! Le nombre était **{secret}**. **+{points} XP Célestes**."
        else:
            if interaction.guild_id:
                record_game_result(interaction.guild_id, "nombre_mystere", "solo", [interaction.user.id], status="loss")
            text = f"Le nombre mystère était **{secret}**. Tu avais proposé **{proposition}**. Retente demain !"
        await interaction.response.send_message(embed=horizons_embed(title="🔢 Le nombre mystère", description=text), ephemeral=True)

    @app_commands.command(name="quizjeu", description="Lancer un quiz interactif ouvert aux membres présents.")
    async def quizjeu(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        item = random.choice(ARCADE_QUIZ)
        embed = horizons_embed(title="🧠 Quiz de l'Arcade", description=f"{item['q']}\n\n" + "\n".join(f"**{i+1}.** {v}" for i,v in enumerate(item['choices'])) + "\n\nChaque membre peut tenter sa chance : une bonne réponse rapporte des XP Célestes.")
        await interaction.response.send_message(embed=embed, view=AnswerView(self,interaction.user.id,"quizjeu", "Ta réponse",item['a'],10,True))

    @app_commands.command(name="anagramme", description="Retrouver le mot caché dans une anagramme.")
    async def anagramme(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        _, solution = random.choice(ANAGRAMS)
        letters = list(solution.upper()); random.shuffle(letters)
        while "".join(letters) == solution.upper(): random.shuffle(letters)
        embed = horizons_embed(title="🔤 L'anagramme", description=f"Remets ces lettres dans l'ordre :\n\n# {' · '.join(letters)}")
        await interaction.response.send_message(embed=embed, view=AnswerView(self,interaction.user.id,"anagramme","Quel est le mot ?",solution,10),ephemeral=True)

    @app_commands.command(name="enigme", description="Résoudre une énigme inédite de l'Arcade HORIZONS.")
    async def enigme(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        question, solution = random.choice(RIDDLES)
        await interaction.response.send_message(embed=horizons_embed(title="🧩 Énigme de l'Arcade", description=question), view=AnswerView(self,interaction.user.id,"enigme","Ta réponse",solution,10),ephemeral=True)

    @app_commands.command(name="reflexe", description="Mesurer ton temps de réaction dans un défi éclair.")
    async def reflexe(self, interaction: discord.Interaction):
        if not await self.require_arcade_channel(interaction): return
        view = ReflexView(self,interaction.user.id)
        await interaction.response.send_message(embed=horizons_embed(title="⚡ Prépare-toi…", description="Un signal va apparaître dans quelques secondes. Ne clique pas avant !"), view=view, ephemeral=True)
        message = await interaction.original_response()
        await view.arm(message)


    @app_commands.command(name="arcade_collectif", description="Lancer un mini-jeu ouvert à tous les membres présents.")
    @app_commands.describe(jeu="Choisis le jeu auquel tout le monde pourra participer")
    @app_commands.choices(jeu=[
        app_commands.Choice(name="Dé", value="de"),
        app_commands.Choice(name="Pile ou face", value="pileface"),
        app_commands.Choice(name="Nombre mystère", value="nombre"),
        app_commands.Choice(name="Quiz", value="quiz"),
        app_commands.Choice(name="Anagramme", value="anagramme"),
        app_commands.Choice(name="Énigme", value="enigme"),
        app_commands.Choice(name="Réflexe", value="reflexe"),
    ])
    async def defi_collectif(self, interaction: discord.Interaction, jeu: app_commands.Choice[str]):
        if not await self.require_arcade_channel(interaction): return
        game = jeu.value
        expected = ""; reward = 10
        if game == "quiz":
            item = random.choice(ARCADE_QUIZ); expected = item["a"]
            details = item["q"] + "\n\n" + "\n".join(f"**{i+1}.** {v}" for i,v in enumerate(item["choices"]))
        elif game == "anagramme":
            _, expected = random.choice(ANAGRAMS); letters = list(expected.upper()); random.shuffle(letters)
            while "".join(letters) == expected.upper(): random.shuffle(letters)
            details = "Remettez ces lettres dans l'ordre :\n\n# " + " · ".join(letters)
        elif game == "enigme":
            details, expected = random.choice(RIDDLES)
        elif game == "nombre":
            expected = str(random.randint(1, 10)); details = "Trouvez le nombre mystère entre **1 et 10**. Chacun propose une réponse."
        elif game == "de": details = "Chaque membre peut lancer le dé une fois. Le résultat est partagé dans le tableau des participants."; reward = 5
        elif game == "pileface": details = "Choisissez **Pile** ou **Face**. Chaque membre tente sa prédiction une fois."; reward = 5
        else: details = "Attendez le signal lumineux, puis cliquez le plus vite possible. Chaque membre peut tenter sa chance une fois."; reward = 5
        session_key = (interaction.guild_id, interaction.channel_id)
        current = self.active_collective_sessions.get(session_key)
        if current and not current.is_finished():
            await interaction.response.send_message("Un défi collectif est déjà en cours dans ce salon. Terminez-le ou attendez sa clôture avant d'en lancer un autre.", ephemeral=True)
            return
        view = CollectiveGameView(self, game, interaction.user.id, expected, reward)
        embed = horizons_embed(title="🤝 Défi collectif HORIZONS", description=f"**{details}**\n\nParticipez grâce au bouton ci-dessous. Une participation par membre ; les résultats s'affichent ici.\n\nLa personne qui lance le défi peut le terminer avec le bouton ⏹️. Durée maximale : 10 minutes.")
        # Réserve le salon avant le premier await : deux commandes lancées
        # presque simultanément ne peuvent pas ouvrir deux défis concurrents.
        self.active_collective_sessions[session_key] = view
        try:
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except (discord.HTTPException, discord.InteractionResponded):
            self.release_collective_session(*session_key)
            raise
        if game == "reflexe": await view.arm_reflex()

async def setup(bot: commands.Bot): await bot.add_cog(HorizonsArcade(bot))

"""Interfaces interactives des six jeux de l'Arcade HORIZONS.

Les parties sont gérées en mémoire pendant la session du bot. Les récompenses
utilisent le système XP Célestes existant et son plafond journalier.
"""
from __future__ import annotations

import asyncio
import random
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING

import discord

from cogs.embed_theme import horizons_embed
from cogs.arcade_progress import ACHIEVEMENTS, record_game_result
from config import LOCAL_TIMEZONE

if TYPE_CHECKING:
    from cogs.horizons_arcade import HorizonsArcade


GAMES = {
    "morpion": "⭕ Morpion",
    "puissance4": "🔴 Puissance 4",
    "memory": "🧠 Memory",
    "code_secret": "🔐 Code secret",
    "petit_bac": "📝 Petit Bac",
    "bataille": "🚢 Bataille navale",
}


def _winner(board: list[str], size: int, win_length: int, empty: str = "·") -> str | None:
    """Retourne le symbole gagnant d'une grille carrée ou rectangulaire aplatie."""
    rows = len(board) // size
    for r in range(rows):
        for c in range(size):
            token = board[r * size + c]
            if token == empty:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r = r + (win_length - 1) * dr
                end_c = c + (win_length - 1) * dc
                if not (0 <= end_r < rows and 0 <= end_c < size):
                    continue
                if all(board[(r + k * dr) * size + (c + k * dc)] == token for k in range(win_length)):
                    return token
    return None


def _minimax(board: list[str], maximizing: bool, depth: int = 0) -> int:
    winner = _winner(board, 3, 3)
    if winner == "O":
        return 10 - depth
    if winner == "X":
        return depth - 10
    if "·" not in board:
        return 0
    scores = []
    token = "O" if maximizing else "X"
    for index, value in enumerate(board):
        if value == "·":
            board[index] = token
            scores.append(_minimax(board, not maximizing, depth + 1))
            board[index] = "·"
    return max(scores) if maximizing else min(scores)


def _ai_move(board: list[str], difficulty: str) -> int:
    available = [i for i, value in enumerate(board) if value == "·"]
    if not available:
        return -1
    if difficulty == "facile":
        return random.choice(available)
    # En difficulté moyenne, l'IA gagne si possible puis bloque une victoire.
    for token in ("O", "X"):
        for index in available:
            board[index] = token
            wins = _winner(board, 3, 3) == token
            board[index] = "·"
            if wins:
                return index
    if difficulty == "difficile":
        scored = []
        for index in available:
            board[index] = "O"
            scored.append((_minimax(board, False), index))
            board[index] = "·"
        best = max(score for score, _ in scored)
        return random.choice([index for score, index in scored if score == best])
    # Préférence simple pour le centre puis les coins en difficulté moyenne.
    for index in (4, 0, 2, 6, 8):
        if index in available:
            return index
    return random.choice(available)


class ArcadeMenuView(discord.ui.View):
    """Menu privé de sélection des jeux et de leur mode."""

    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = owner_id
        self.game = "morpion"
        self.add_item(GameSelect(self))
        self.add_item(LaunchSoloButton(self))
        self.add_item(ChallengeButton(self))
        self.add_item(CollectivePetitBacButton(self))
        self.add_item(ArcadeNightButton(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ce menu appartient à la personne qui l'a ouvert.", ephemeral=True)
            return False
        return True

    def menu_embed(self) -> discord.Embed:
        if self.game == "morpion":
            details = (
                "Aligne trois symboles pour gagner.\n\n"
                "**Mode solo :** affronte l'IA avec trois niveaux de difficulté.\n"
                "**Mode duel :** défie un autre membre."
            )
        elif self.game == "puissance4":
            details = "Aligne quatre jetons horizontalement, verticalement ou en diagonale.\n\n**Mode duel :** défie un autre membre dans une partie au tour par tour."
        elif self.game == "memory":
            details = "Retrouve les huit paires en retournant deux cartes à la fois. **Mode solo** avec un plateau de 16 cartes."
        elif self.game == "code_secret":
            details = "Déduis une combinaison secrète de quatre chiffres parmi six, avec les indices de bonne position et de bonne valeur. **Mode solo**."
        elif self.game == "petit_bac":
            details = "Une lettre, quatre catégories et un temps limité. Les participants pourront signaler les réponses ambiguës et voter. **Partie collective**."
        else:
            details = "Place tes navires sur une grille privée et tente de couler la flotte adverse. **Mode duel**, tirs alternés et grilles privées envoyées en message direct."
        return horizons_embed(title="🎮 Arcade HORIZONS", description=f"**Jeu sélectionné : {GAMES[self.game]}**\n\n{details}")


class GameSelect(discord.ui.Select):
    def __init__(self, parent: ArcadeMenuView):
        self.parent_view = parent
        super().__init__(
            placeholder="Choisir un jeu…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Morpion", value="morpion", emoji="⭕", description="Solo contre l'IA ou duel"),
                discord.SelectOption(label="Puissance 4", value="puissance4", emoji="🔴", description="Duel au tour par tour"),
                discord.SelectOption(label="Memory", value="memory", emoji="🧠", description="Retrouver les huit paires en solo"),
                discord.SelectOption(label="Code secret", value="code_secret", emoji="🔐", description="Déchiffrer une combinaison en solo"),
                discord.SelectOption(label="Petit Bac", value="petit_bac", emoji="📝", description="Partie collective chronométrée"),
                discord.SelectOption(label="Bataille navale", value="bataille", emoji="🚢", description="Duel avec grilles privées en messages directs"),
            ],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.game = self.values[0]
        self.parent_view.children[1].disabled = self.parent_view.game not in {"morpion", "memory", "code_secret"}
        self.parent_view.children[2].disabled = self.parent_view.game not in {"morpion", "puissance4", "bataille"}
        self.parent_view.children[3].disabled = self.parent_view.game != "petit_bac"
        await interaction.response.edit_message(embed=self.parent_view.menu_embed(), view=self.parent_view)


class LaunchSoloButton(discord.ui.Button):
    def __init__(self, parent: ArcadeMenuView):
        self.parent_view = parent
        super().__init__(label="Jouer en solo", style=discord.ButtonStyle.success, emoji="🤖", row=1)

    async def callback(self, interaction: discord.Interaction):
        game = self.parent_view.game
        if game == "morpion":
            view = DifficultyView(self.parent_view.cog, interaction.user.id)
            await interaction.response.edit_message(
                embed=horizons_embed(title="⭕ Morpion solo", description="Choisis le niveau de l'intelligence artificielle."),
                view=view,
            )
        elif game == "memory":
            view = MemoryView(self.parent_view.cog, interaction.user.id)
            view.guild_id = interaction.guild_id
            view.message = interaction.message
            await interaction.response.edit_message(embed=view.make_embed(), view=view)
        elif game == "code_secret":
            view = CodeSecretView(self.parent_view.cog, interaction.user.id)
            view.guild_id = interaction.guild_id
            view.message = interaction.message
            await interaction.response.edit_message(embed=view.make_embed(), view=view)
        else:
            await interaction.response.send_message("Ce jeu ne propose pas de mode solo.", ephemeral=True)


class ChallengeButton(discord.ui.Button):
    def __init__(self, parent: ArcadeMenuView):
        self.parent_view = parent
        super().__init__(label="Défier un membre", style=discord.ButtonStyle.primary, emoji="⚔️", row=1)

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.game not in {"morpion", "puissance4", "bataille"}:
            await interaction.response.send_message("Ce jeu ne propose pas de défi direct entre deux membres.", ephemeral=True)
            return
        view = ChallengeSetupView(self.parent_view.cog, interaction.user, self.parent_view.game)
        await interaction.response.edit_message(
            embed=horizons_embed(title="⚔️ Préparer un défi", description="Sélectionne le membre que tu souhaites inviter, puis confirme l'envoi du défi."),
            view=view,
        )


class CollectivePetitBacButton(discord.ui.Button):
    def __init__(self, parent: ArcadeMenuView):
        self.parent_view = parent
        super().__init__(label="Lancer en collectif", style=discord.ButtonStyle.success, emoji="👥", row=1)
        self.disabled = True

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.game != "petit_bac":
            await interaction.response.send_message("Sélectionne d'abord le Petit Bac.", ephemeral=True)
            return
        if interaction.channel is None or interaction.guild_id is None:
            await interaction.response.send_message("Le Petit Bac se joue dans un salon du serveur.", ephemeral=True)
            return
        session_key = (interaction.guild_id, interaction.channel.id)
        current = self.parent_view.cog.active_collective_sessions.get(session_key)
        if current and not current.is_finished():
            await interaction.response.send_message("Un défi collectif est déjà en cours dans ce salon. Attendez sa clôture avant d'en lancer un autre.", ephemeral=True)
            return
        view = PetitBacView(self.parent_view.cog, interaction.user.id, interaction.guild_id)
        self.parent_view.cog.active_collective_sessions[session_key] = view
        await interaction.response.edit_message(embed=horizons_embed(title="📝 Petit Bac lancé", description="La partie collective est publiée dans le salon."), view=None)
        try:
            message = await interaction.channel.send(embed=view.make_embed(), view=view)
            view.message = message
            view.start_timer()
        except discord.HTTPException:
            self.parent_view.cog.release_collective_session(*session_key)
            await interaction.followup.send("Je n'ai pas pu publier la partie dans ce salon.", ephemeral=True)


class DifficultyView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(timeout=120)
        self.cog, self.owner_id = cog, owner_id
        self.add_item(DifficultySelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Ce choix ne t'est pas destiné.", ephemeral=True)
            return False
        return True


class DifficultySelect(discord.ui.Select):
    def __init__(self, parent: DifficultyView):
        self.parent_view = parent
        super().__init__(
            placeholder="Niveau de difficulté…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Facile", value="facile", description="L'IA joue au hasard"),
                discord.SelectOption(label="Moyen", value="moyen", description="L'IA sait gagner et bloquer"),
                discord.SelectOption(label="Difficile", value="difficile", description="L'IA utilise une stratégie minimax"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        view = TicTacToeView(self.parent_view.cog, interaction.user.id, difficulty=self.values[0])
        view.guild_id = interaction.guild_id
        view.message = interaction.message
        await interaction.response.edit_message(embed=view.make_embed(), view=view)


class ChallengeSetupView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", challenger: discord.User | discord.Member, game: str):
        super().__init__(timeout=120)
        self.cog, self.challenger, self.game = cog, challenger, game
        self.target: discord.Member | discord.User | None = None
        self.add_item(ChallengeUserSelect(self))
        self.add_item(SendChallengeButton(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.challenger.id:
            await interaction.response.send_message("Seule la personne qui prépare le défi peut utiliser ce menu.", ephemeral=True)
            return False
        return True


class ChallengeUserSelect(discord.ui.UserSelect):
    def __init__(self, parent: ChallengeSetupView):
        self.parent_view = parent
        super().__init__(placeholder="Choisir un membre…", min_values=1, max_values=1, row=0)

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        if target.id == self.parent_view.challenger.id:
            await interaction.response.send_message("Tu ne peux pas te défier toi-même !", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("Les bots ne peuvent pas accepter de défi pour le moment.", ephemeral=True)
            return
        self.parent_view.target = target
        await interaction.response.edit_message(
            embed=horizons_embed(title="⚔️ Défi prêt", description=f"Tu vas inviter **{target.display_name}** pour une partie de **{GAMES[self.parent_view.game]}**."),
            view=self.parent_view,
        )


class SendChallengeButton(discord.ui.Button):
    def __init__(self, parent: ChallengeSetupView):
        self.parent_view = parent
        super().__init__(label="Envoyer le défi", style=discord.ButtonStyle.success, emoji="📨", row=1)

    async def callback(self, interaction: discord.Interaction):
        target = self.parent_view.target
        if target is None:
            await interaction.response.send_message("Choisis d'abord un membre.", ephemeral=True)
            return
        if interaction.guild is None or interaction.channel is None:
            await interaction.response.send_message("Ce défi doit être lancé dans un salon du serveur.", ephemeral=True)
            return
        view = ChallengeInviteView(self.parent_view.cog, self.parent_view.challenger, target, self.parent_view.game)
        await interaction.response.edit_message(embed=horizons_embed(title="📨 Défi envoyé", description=f"Invitation envoyée à {target.mention}."), view=None)
        try:
            message = await interaction.channel.send(
                content=f"{target.mention} — tu as reçu un défi de {self.parent_view.challenger.mention} !",
                embed=view.invite_embed(),
                view=view,
                allowed_mentions=discord.AllowedMentions(users=[target]),
            )
            view.message = message
        except discord.HTTPException:
            await interaction.followup.send("Je n'ai pas pu publier le défi dans ce salon. Vérifie mes permissions d'envoi de messages.", ephemeral=True)


class ChallengeInviteView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", challenger: discord.Member | discord.User, target: discord.Member | discord.User, game: str):
        super().__init__(timeout=120)
        self.cog, self.challenger, self.target, self.game = cog, challenger, target, game
        self.message: discord.Message | None = None
        self.resolved = False

    def invite_embed(self) -> discord.Embed:
        return horizons_embed(title="⚔️ Invitation à un duel", description=f"**{self.challenger.display_name}** te propose une partie de **{GAMES[self.game]}**.\n\nTu as deux minutes pour accepter ou refuser.")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.target.id:
            await interaction.response.send_message("Cette invitation est réservée au membre invité.", ephemeral=True)
            return False
        if self.resolved:
            await interaction.response.send_message("Cette invitation a déjà été traitée.", ephemeral=True)
            return False
        return True

    async def _finish_invite(self, interaction: discord.Interaction, accepted: bool):
        self.resolved = True
        self.stop()
        for item in self.children:
            item.disabled = True
        if not accepted:
            await interaction.response.edit_message(embed=horizons_embed(title="Invitation refusée", description=f"{self.target.mention} a décliné le défi."), view=self)
            return
        await interaction.response.edit_message(embed=horizons_embed(title="Défi accepté !", description="La partie commence. Bonne chance à vous deux !"), view=self)
        if self.game == "bataille":
            game = NavalBattleGame(self.cog, interaction.guild, interaction.channel, self.challenger, self.target)
            await game.start(interaction)
            return
        if self.game == "morpion":
            game_view = TicTacToeView(self.cog, self.challenger.id, opponent_id=self.target.id)
        else:
            game_view = ConnectFourView(self.cog, self.challenger.id, self.target.id)
        game_view.guild_id = interaction.guild_id
        try:
            game_message = await interaction.followup.send(embed=game_view.make_embed(), view=game_view, wait=True)
            game_view.message = game_message
        except discord.HTTPException:
            await interaction.followup.send("Impossible de démarrer la partie. Réessaie dans un autre salon.", ephemeral=True)

    @discord.ui.button(label="Accepter", style=discord.ButtonStyle.success, emoji="🤝")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish_invite(interaction, True)

    @discord.ui.button(label="Refuser", style=discord.ButtonStyle.danger, emoji="✖️")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish_invite(interaction, False)

    async def on_timeout(self):
        if self.resolved:
            return
        self.resolved = True
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=horizons_embed(title="Invitation expirée", description="Le délai de réponse est dépassé."), view=self)
            except discord.HTTPException:
                pass


class BaseGameView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", player_one: int, player_two: int | None = None, timeout: float = 600):
        super().__init__(timeout=timeout)
        self.cog, self.player_one, self.player_two = cog, player_one, player_two
        self.current_player = player_one
        self.finished = False
        self.message: discord.Message | None = None
        self.game_key = ""
        self.xp_reward = 10
        self.mode = "duel" if player_two is not None else "solo"
        self.started_at = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        self.result_recorded = False
        self.guild_id: int | None = None

    def player_name(self, user_id: int) -> str:
        return f"<@{user_id}>"

    def status_line(self) -> str:
        if self.player_two is None:
            return "À toi de jouer : **⭕**"
        return f"Au tour de {self.player_name(self.current_player)} ({'⭕' if self.current_player == self.player_one else '❌'})."

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.finished:
            await interaction.response.send_message("Cette partie est terminée.", ephemeral=True)
            return False
        allowed = {self.player_one} if self.player_two is None else {self.player_one, self.player_two}
        if interaction.user.id not in allowed:
            await interaction.response.send_message("Tu ne participes pas à cette partie.", ephemeral=True)
            return False
        return True

    async def award_winner(self, interaction: discord.Interaction, user_id: int, game_key: str, amount: int = 10):
        points = self.cog.award_game_xp(interaction.guild_id, user_id, game_key, amount)
        return points

    def record_result(self, guild_id: int | None, players=None, winners=(), status="completed", scores=None):
        guild_id = guild_id or self.guild_id
        if self.result_recorded or not guild_id or not self.game_key:
            return []
        self.result_recorded = True
        return record_game_result(
            guild_id, self.game_key, self.mode,
            players if players is not None else ([self.player_one] if self.player_two is None else [self.player_one, self.player_two]),
            winners=winners, status=status, scores=scores, started_at=self.started_at,
        )

    def add_abandon_button(self):
        self.add_item(AbandonGameButton(self))

    async def on_timeout(self):
        if self.finished:
            return
        self.finished = True
        self.record_result(self.guild_id, status="timeout")
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(embed=horizons_embed(title="⏳ Partie terminée", description="La partie a été clôturée après dix minutes sans activité."), view=self)
            except discord.HTTPException:
                pass


class AbandonGameButton(discord.ui.Button):
    def __init__(self, parent: BaseGameView):
        self.parent_view = parent
        super().__init__(label="Abandonner", style=discord.ButtonStyle.danger, emoji="🏳️", row=4)

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.finished = True
        self.parent_view.stop()
        for item in self.parent_view.children:
            item.disabled = True
        if self.parent_view.player_two is None:
            self.parent_view.record_result(interaction.guild_id, status="abandoned")
            ending = f"<@{interaction.user.id}> a abandonné la partie."
        else:
            winner_id = self.parent_view.player_two if interaction.user.id == self.parent_view.player_one else self.parent_view.player_one
            game_key = self.parent_view.game_key or "morpion"
            amount = self.parent_view.xp_reward
            points = await self.parent_view.award_winner(interaction, winner_id, game_key, amount)
            self.parent_view.record_result(interaction.guild_id, winners=[winner_id], status="completed")
            ending = f"<@{interaction.user.id}> a abandonné. 🏆 <@{winner_id}> remporte la partie par forfait et gagne **+{points} XP Célestes**."
        await interaction.response.edit_message(embed=self.parent_view.make_embed(ending), view=self.parent_view)


class TicTacToeView(BaseGameView):
    def __init__(self, cog: "HorizonsArcade", player_one: int, opponent_id: int | None = None, difficulty: str = "moyen"):
        super().__init__(cog, player_one, opponent_id)
        self.board = ["·"] * 9
        self.game_key = "morpion"
        self.xp_reward = 10
        self.difficulty = difficulty
        self.ai_mode = opponent_id is None
        self.mode = "solo_ia" if self.ai_mode else "duel"
        self.add_board_buttons()

    def add_board_buttons(self):
        for index in range(9):
            button = discord.ui.Button(label=str(index + 1), style=discord.ButtonStyle.secondary, row=index // 3)
            async def callback(interaction: discord.Interaction, position=index, item=button):
                await self.play(interaction, position, item)
            button.callback = callback
            self.add_item(button)
        self.add_abandon_button()

    def make_embed(self, ending: str | None = None) -> discord.Embed:
        board_text = "\n".join("　".join(("⭕" if x == "X" else "❌" if x == "O" else "▫️") for x in self.board[r:r+3]) for r in (0, 3, 6))
        if ending:
            description = f"{board_text}\n\n{ending}"
        else:
            opponent = f"contre l'IA ({self.difficulty})" if self.ai_mode else f"contre <@{self.player_two}>"
            description = f"{board_text}\n\n**Morpion** — {opponent}\n{self.status_line()}"
        return horizons_embed(title="⭕ Morpion HORIZONS", description=description)

    def _check_end(self) -> str | None:
        winner = _winner(self.board, 3, 3)
        if winner:
            return winner
        return "draw" if "·" not in self.board else None

    async def play(self, interaction: discord.Interaction, position: int, button: discord.ui.Button):
        if interaction.user.id != self.current_player:
            await interaction.response.send_message("Ce n'est pas ton tour.", ephemeral=True)
            return
        if self.board[position] != "·":
            await interaction.response.send_message("Cette case est déjà occupée.", ephemeral=True)
            return
        token = "X" if interaction.user.id == self.player_one else "O"
        self.board[position] = token
        button.label = "⭕" if token == "X" else "❌"
        button.disabled = True
        result = self._check_end()
        if result is None and self.ai_mode:
            ai_position = _ai_move(self.board, self.difficulty)
            if ai_position >= 0:
                self.board[ai_position] = "O"
                ai_button = self.children[ai_position]
                ai_button.label = "❌"
                ai_button.disabled = True
            result = self._check_end()
        elif result is None:
            self.current_player = self.player_two if self.current_player == self.player_one else self.player_one
        if result == "X":
            self.finished = True
            points = await self.award_winner(interaction, self.player_one, "morpion")
            self.record_result(interaction.guild_id, winners=[self.player_one], status="completed")
            ending = f"🏆 <@{self.player_one}> remporte la partie ! **+{points} XP Célestes**."
        elif result == "O":
            self.finished = True
            if self.ai_mode:
                self.record_result(interaction.guild_id, status="loss")
                ending = "L'IA remporte cette manche. La prochaine sera peut-être la bonne !"
            else:
                points = await self.award_winner(interaction, self.player_two, "morpion")
                self.record_result(interaction.guild_id, winners=[self.player_two], status="completed")
                ending = f"🏆 <@{self.player_two}> remporte la partie ! **+{points} XP Célestes**."
        elif result == "draw":
            self.finished = True
            self.record_result(interaction.guild_id, status="draw")
            ending = "🤝 Match nul ! Bien joué à tous les deux."
        else:
            ending = None
        if self.finished:
            for child in self.children:
                child.disabled = True
            self.stop()
        await interaction.response.edit_message(embed=self.make_embed(ending), view=self)


class ConnectFourView(BaseGameView):
    def __init__(self, cog: "HorizonsArcade", player_one: int, player_two: int):
        super().__init__(cog, player_one, player_two)
        self.board = [["·"] * 7 for _ in range(6)]
        self.game_key = "puissance4"
        self.xp_reward = 12
        self.mode = "duel"
        for column in range(7):
            button = discord.ui.Button(label=f"Colonne {column + 1}", style=discord.ButtonStyle.primary, row=0 if column < 4 else 1)
            async def callback(interaction: discord.Interaction, col=column):
                await self.drop(interaction, col)
            button.callback = callback
            self.add_item(button)
        self.add_abandon_button()

    def status_line(self) -> str:
        if self.current_player == self.player_one:
            return f"Au tour de 🔴 {self.player_name(self.current_player)}."
        return f"Au tour de 🟡 {self.player_name(self.current_player)}."

    def make_embed(self, ending: str | None = None) -> discord.Embed:
        rows = ["　".join("🔴" if value == "R" else "🟡" if value == "Y" else "⚫" for value in row) for row in self.board]
        board_text = "\n".join(rows) + "\n①　②　③　④　⑤　⑥　⑦"
        if ending:
            description = f"{board_text}\n\n{ending}"
        else:
            description = f"{board_text}\n\n🔴 <@{self.player_one}>\n🟡 <@{self.player_two}>\n\n{self.status_line()}"
        return horizons_embed(title="🔴 Puissance 4 HORIZONS", description=description)

    def _winner(self) -> str | None:
        flat = [value for row in self.board for value in row]
        # _winner travaille sur une grille carrée ; le contrôle rectangulaire est fait ici.
        for row in range(6):
            for col in range(7):
                token = self.board[row][col]
                if token == "·":
                    continue
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                    cells = [(row + k * dr, col + k * dc) for k in range(4)]
                    if all(0 <= r < 6 and 0 <= c < 7 for r, c in cells) and all(self.board[r][c] == token for r, c in cells):
                        return token
        return None

    async def drop(self, interaction: discord.Interaction, column: int):
        if interaction.user.id != self.current_player:
            await interaction.response.send_message("Ce n'est pas ton tour.", ephemeral=True)
            return
        row = next((r for r in range(5, -1, -1) if self.board[r][column] == "·"), None)
        if row is None:
            await interaction.response.send_message("Cette colonne est pleine. Choisis-en une autre.", ephemeral=True)
            return
        token = "R" if self.current_player == self.player_one else "Y"
        self.board[row][column] = token
        winner = self._winner()
        draw = winner is None and all(self.board[0][c] != "·" for c in range(7))
        if winner:
            self.finished = True
            winner_id = self.player_one if winner == "R" else self.player_two
            points = await self.award_winner(interaction, winner_id, "puissance4", 12)
            self.record_result(interaction.guild_id, winners=[winner_id], status="completed")
            ending = f"🏆 <@{winner_id}> remporte la partie ! **+{points} XP Célestes**."
        elif draw:
            self.finished = True
            self.record_result(interaction.guild_id, status="draw")
            ending = "🤝 Match nul ! La grille est pleine."
        else:
            self.current_player = self.player_two if self.current_player == self.player_one else self.player_one
            ending = None
        for column_index, child in enumerate(self.children):
            child.disabled = self.finished or self.board[0][column_index] != "·"
        if self.finished:
            self.stop()
        await interaction.response.edit_message(embed=self.make_embed(ending), view=self)


# ---------------------------------------------------------------------------
# Memory — solo
# ---------------------------------------------------------------------------

class MemoryView(BaseGameView):
    PAIRS = ("🌟", "🌙", "☀️", "🌈", "🦋", "🌸", "💎", "🍀")

    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(cog, owner_id, timeout=600)
        self.game_key = "memory"
        self.xp_reward = 10
        self.mode = "solo"
        self.cards = list(self.PAIRS) * 2
        random.shuffle(self.cards)
        self.revealed: list[int] = []
        self.matched: set[int] = set()
        self.flips = 0
        self.resolving = False
        for index in range(16):
            button = discord.ui.Button(label="?", style=discord.ButtonStyle.secondary, row=index // 4)
            async def callback(interaction: discord.Interaction, position=index, item=button):
                await self.flip(interaction, position, item)
            button.callback = callback
            self.add_item(button)
        self.add_abandon_button()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.resolving:
            await interaction.response.send_message("Patiente une seconde : les deux cartes sont en cours de comparaison.", ephemeral=True)
            return False
        return await super().interaction_check(interaction)

    def make_embed(self, ending: str | None = None) -> discord.Embed:
        found = len(self.matched) // 2
        lines = []
        for row in range(4):
            start = row * 4
            lines.append("　".join(self.cards[index] if index in self.matched or index in self.revealed else "❔" for index in range(start, start + 4)))
        description = "\n".join(lines)
        if ending:
            description += f"\n\n{ending}"
        else:
            description += f"\n\n**Paires trouvées :** {found}/8\n**Retournements :** {self.flips}"
        return horizons_embed(title="🧠 Memory HORIZONS", description=description)

    async def flip(self, interaction: discord.Interaction, position: int, button: discord.ui.Button):
        if position in self.matched or position in self.revealed:
            await interaction.response.send_message("Cette carte est déjà visible.", ephemeral=True)
            return
        self.flips += 1
        self.revealed.append(position)
        button.label = self.cards[position]
        button.disabled = True
        if len(self.revealed) < 2:
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
            return
        first, second = self.revealed
        if self.cards[first] == self.cards[second]:
            self.matched.update((first, second))
            self.revealed.clear()
            if len(self.matched) == 16:
                self.finished = True
                points = await self.award_winner(interaction, self.player_one, self.game_key, self.xp_reward)
                self.record_result(interaction.guild_id, winners=[self.player_one], status="completed")
                ending = f"🏆 Toutes les paires sont réunies en **{self.flips} retournements** ! **+{points} XP Célestes**."
                for child in self.children:
                    child.disabled = True
                self.stop()
                await interaction.response.edit_message(embed=self.make_embed(ending), view=self)
                return
            await interaction.response.edit_message(embed=self.make_embed(), view=self)
            return
        self.resolving = True
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
        self.message = interaction.message or self.message
        await asyncio.sleep(1.25)
        for index in (first, second):
            self.children[index].label = "?"
            self.children[index].disabled = False
        self.revealed.clear()
        self.resolving = False
        if self.message:
            try:
                await self.message.edit(embed=self.make_embed(), view=self)
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# Code secret — Mastermind solo
# ---------------------------------------------------------------------------

class CodeSecretModal(discord.ui.Modal):
    def __init__(self, parent: "CodeSecretView"):
        super().__init__(title="Proposer une combinaison")
        self.parent_view = parent
        self.guess = discord.ui.TextInput(
            label="Quatre chiffres distincts de 1 à 6",
            placeholder="Exemple : 1356",
            min_length=4,
            max_length=4,
            required=True,
        )
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.submit_guess(interaction, str(self.guess.value))


class CodeGuessButton(discord.ui.Button):
    def __init__(self, parent: "CodeSecretView"):
        self.parent_view = parent
        super().__init__(label="Proposer une combinaison", style=discord.ButtonStyle.primary, emoji="🔐", row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CodeSecretModal(self.parent_view))


class CodeSecretView(BaseGameView):
    def __init__(self, cog: "HorizonsArcade", owner_id: int):
        super().__init__(cog, owner_id, timeout=600)
        self.game_key = "code_secret"
        self.xp_reward = 12
        self.mode = "solo"
        self.secret = "".join(random.sample("123456", 4))
        self.attempts: list[tuple[str, int, int]] = []
        self.add_item(CodeGuessButton(self))
        self.add_abandon_button()

    def make_embed(self, ending: str | None = None) -> discord.Embed:
        lines = [f"**{index}.** `{guess}` — {good} bien placé(s), {misplaced} mal placé(s)" for index, (guess, good, misplaced) in enumerate(self.attempts, 1)]
        description = "Trouve le code secret de **4 chiffres distincts**, choisis parmi 1, 2, 3, 4, 5 et 6.\n\nChaque proposition indique le nombre de chiffres bien placés et de chiffres présents mais mal placés.\n\n**10 tentatives maximum.**"
        if lines:
            description += "\n\n" + "\n".join(lines[-10:])
        if ending:
            description += f"\n\n{ending}"
        else:
            description += f"\n\nTentatives utilisées : **{len(self.attempts)}/10**"
        return horizons_embed(title="🔐 Code secret HORIZONS", description=description)

    async def submit_guess(self, interaction: discord.Interaction, guess: str):
        if interaction.user.id != self.player_one or self.finished:
            await interaction.response.send_message("Cette partie ne t'est pas destinée ou elle est terminée.", ephemeral=True)
            return
        if len(guess) != 4 or not guess.isdigit() or any(char not in "123456" for char in guess) or len(set(guess)) != 4:
            await interaction.response.send_message("La combinaison doit contenir quatre chiffres différents compris entre 1 et 6.", ephemeral=True)
            return
        well = sum(a == b for a, b in zip(guess, self.secret))
        misplaced = sum(char in self.secret for char in guess) - well
        self.attempts.append((guess, well, misplaced))
        if well == 4:
            self.finished = True
            points = await self.award_winner(interaction, self.player_one, self.game_key, self.xp_reward)
            self.record_result(interaction.guild_id, winners=[self.player_one], status="completed")
            ending = f"🏆 Code découvert en **{len(self.attempts)} tentative(s)** ! **+{points} XP Célestes**."
        elif len(self.attempts) >= 10:
            self.finished = True
            self.record_result(interaction.guild_id, status="loss")
            ending = f"Le code était **{self.secret}**. Tu pourras retenter ta chance plus tard."
        else:
            ending = None
        if self.finished:
            for item in self.children:
                item.disabled = True
            self.stop()
        await interaction.response.send_message(
            "Combinaison enregistrée : " + (f"{well} bien placé(s), {misplaced} mal placé(s)." if well != 4 else "code trouvé !"),
            ephemeral=True,
        )
        if self.message:
            try:
                await self.message.edit(embed=self.make_embed(ending), view=self)
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# Petit Bac — collectif, réponses puis vote sur les réponses ambiguës
# ---------------------------------------------------------------------------

PETIT_BAC_CATEGORIES = ("Prénom", "Ville ou pays", "Animal", "Métier")
PETIT_BAC_LETTERS = "ABCDEFGHILMNPRST"


class PetitBacAnswerModal(discord.ui.Modal):
    def __init__(self, parent: "PetitBacView"):
        super().__init__(title=f"Petit Bac — lettre {parent.letter}")
        self.parent_view = parent
        self.fields = []
        for category in PETIT_BAC_CATEGORIES:
            field = discord.ui.TextInput(label=category, max_length=50, required=True)
            self.fields.append(field)
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {category: str(field.value).strip() for category, field in zip(PETIT_BAC_CATEGORIES, self.fields)}
        await self.parent_view.record_answers(interaction, answers)


class PetitBacVoteModal(discord.ui.Modal):
    def __init__(self, parent: "PetitBacView"):
        super().__init__(title="Signaler une réponse ambiguë")
        self.parent_view = parent
        self.answer = discord.ui.TextInput(label="Réponse à examiner", max_length=50, required=True)
        self.reason = discord.ui.TextInput(label="Pourquoi est-elle ambiguë ?", max_length=120, required=True)
        self.add_item(self.answer)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.record_vote(interaction, str(self.answer.value).strip(), str(self.reason.value).strip())


class PetitBacSubmitButton(discord.ui.Button):
    def __init__(self, parent: "PetitBacView"):
        self.parent_view = parent
        super().__init__(label="Soumettre mes réponses", style=discord.ButtonStyle.primary, emoji="✍️", row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.phase != "answers":
            await interaction.response.send_message("La phase de réponses est terminée.", ephemeral=True)
            return
        if interaction.user.id in self.parent_view.participants:
            await interaction.response.send_message("Tu as déjà envoyé tes réponses.", ephemeral=True)
            return
        await interaction.response.send_modal(PetitBacAnswerModal(self.parent_view))


class PetitBacVoteButton(discord.ui.Button):
    def __init__(self, parent: "PetitBacView"):
        self.parent_view = parent
        super().__init__(label="Voter sur une réponse ambiguë", style=discord.ButtonStyle.secondary, emoji="🗳️", row=0)
        self.disabled = True

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.phase != "vote":
            await interaction.response.send_message("La phase de vote n'est pas ouverte.", ephemeral=True)
            return
        await interaction.response.send_modal(PetitBacVoteModal(self.parent_view))


class PetitBacView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", owner_id: int, guild_id: int):
        super().__init__(timeout=180)
        self.cog, self.owner_id, self.guild_id = cog, owner_id, guild_id
        self.letter = random.choice(PETIT_BAC_LETTERS)
        self.phase = "answers"
        self.participants: dict[int, dict[str, str]] = {}
        self.votes: dict[str, dict[int, str]] = {}
        self.message: discord.Message | None = None
        self.timer_task: asyncio.Task | None = None
        self.add_item(PetitBacSubmitButton(self))
        self.add_item(PetitBacVoteButton(self))

    def make_embed(self, finished: bool = False) -> discord.Embed:
        if finished:
            scores = self.calculate_scores()
            ranking = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
            lines = [f"**{index}.** <@{user_id}> — **{score} points**" for index, (user_id, score) in enumerate(ranking, 1)]
            detail = "\n".join(lines) if lines else "Aucune réponse n'a été enregistrée."
            if ranking and ranking[0][1] > 0:
                detail += f"\n\n🏆 Vainqueur : <@{ranking[0][0]}>"
            elif ranking:
                detail += "\n\nAucun point validé cette manche : pas de vainqueur."
            threshold = max(2, (len(self.participants) + 2) // 3)
            contested = [(answer, votes) for answer, votes in self.votes.items() if len(votes) >= threshold]
            if contested:
                contested_lines = []
                for answer, votes in contested[:8]:
                    reasons = "; ".join(list(votes.values())[:2])
                    contested_lines.append(f"• **{answer}** — {len(votes)} vote(s) : {reasons}")
                detail += "\n\n**Réponses jugées ambiguës :**\n" + "\n".join(contested_lines)
            return horizons_embed(title="🏁 Résultats du Petit Bac", description=detail)
        if self.phase == "answers":
            description = f"Lettre tirée au sort :\n\n# {self.letter}\n\nRéponds aux quatre catégories : **Prénom · Ville ou pays · Animal · Métier**.\n\n⏱️ Vous avez **90 secondes**. Une seule participation par membre. Chaque réponse doit commencer par la lettre indiquée.\n\nRéponses reçues : **{len(self.participants)}**"
        else:
            entries = []
            for user_id, answers in self.participants.items():
                entries.extend(f"• <@{user_id}> — **{category} :** {answer}" for category, answer in answers.items())
            description = "La phase de réponses est terminée. Examinez les propositions et signalez celles qui vous semblent ambiguës.\n\n" + ("\n".join(entries[:24]) if entries else "Aucune réponse.")
            description += "\n\n⏱️ Vote ouvert pendant **45 secondes**. Vous ne pouvez pas contester votre propre réponse."
        return horizons_embed(title="📝 Petit Bac HORIZONS", description=description)

    def start_timer(self):
        self.timer_task = asyncio.create_task(self._answer_timer())

    async def _answer_timer(self):
        await asyncio.sleep(90)
        if self.phase != "answers":
            return
        self.phase = "vote"
        self.children[0].disabled = True
        self.children[1].disabled = False
        if self.message:
            await self.message.edit(embed=self.make_embed(), view=self)
        await asyncio.sleep(45)
        if self.phase == "vote":
            await self.finish_round()

    async def record_answers(self, interaction: discord.Interaction, answers: dict[str, str]):
        if self.phase != "answers":
            await interaction.response.send_message("Le temps de réponse est écoulé.", ephemeral=True)
            return
        if interaction.user.id in self.participants:
            await interaction.response.send_message("Tu as déjà participé à cette manche.", ephemeral=True)
            return
        letter = self.letter.casefold()
        def initial(value: str) -> str:
            decomposed = unicodedata.normalize("NFKD", value[0].casefold())
            return next((char for char in decomposed if not unicodedata.combining(char)), "")
        invalid = [category for category, answer in answers.items() if not answer or initial(answer) != letter]
        if invalid:
            await interaction.response.send_message("Chaque réponse doit commencer par **" + self.letter + "**. À corriger : " + ", ".join(invalid) + ".", ephemeral=True)
            return
        self.participants[interaction.user.id] = answers
        await interaction.response.send_message("Tes quatre réponses sont enregistrées. Merci d'avoir joué !", ephemeral=True)
        if self.message:
            await self.message.edit(embed=self.make_embed(), view=self)

    async def record_vote(self, interaction: discord.Interaction, answer: str, reason: str):
        if self.phase != "vote":
            await interaction.response.send_message("La phase de vote est terminée.", ephemeral=True)
            return
        if interaction.user.id not in self.participants:
            await interaction.response.send_message("Seuls les participants peuvent voter.", ephemeral=True)
            return
        key = answer.casefold().strip()
        matches = [(user_id, category) for user_id, values in self.participants.items() for category, value in values.items() if value.casefold().strip() == key]
        if not matches:
            await interaction.response.send_message("Je ne retrouve pas cette réponse dans les propositions. Recopie-la exactement.", ephemeral=True)
            return
        if any(user_id == interaction.user.id for user_id, _ in matches):
            await interaction.response.send_message("Tu ne peux pas voter sur une réponse que tu as toi-même proposée.", ephemeral=True)
            return
        voters = self.votes.setdefault(key, {})
        if interaction.user.id in voters:
            await interaction.response.send_message("Tu as déjà voté sur cette réponse.", ephemeral=True)
            return
        voters[interaction.user.id] = reason
        await interaction.response.send_message("Ton signalement est enregistré. Merci pour ton vote.", ephemeral=True)

    def calculate_scores(self) -> dict[int, int]:
        scores = {user_id: 0 for user_id in self.participants}
        threshold = max(2, (len(self.participants) + 2) // 3)
        all_values: dict[tuple[str, str], int] = {}
        for answers in self.participants.values():
            for category, answer in answers.items():
                key = (category, answer.casefold().strip())
                all_values[key] = all_values.get(key, 0) + 1
        for user_id, answers in self.participants.items():
            for category, answer in answers.items():
                key = answer.casefold().strip()
                contested = len(self.votes.get(key, {})) >= threshold
                if not contested:
                    scores[user_id] += 5 if all_values[(category, key)] > 1 else 10
        return scores

    async def finish_round(self):
        if self.phase == "finished":
            return
        self.phase = "finished"
        self.stop()
        for item in self.children:
            item.disabled = True
        scores = self.calculate_scores()
        winners = []
        if scores:
            high = max(scores.values())
            winners = [user_id for user_id, score in scores.items() if score == high] if high > 0 else []
            for user_id in scores:
                amount = 10 if user_id in winners else 5
                self.cog.award_game_xp(self.guild_id, user_id, "petit_bac", amount)
            record_game_result(
                self.guild_id, "petit_bac", "collectif", list(scores),
                winners=winners, status="completed" if winners else "draw",
                scores=scores, started_at=self.started_at,
            )
        if self.message:
            try:
                await self.message.edit(embed=self.make_embed(finished=True), view=self)
            except discord.HTTPException:
                pass
            self.cog.release_collective_session(self.guild_id, self.message.channel.id)

    async def on_timeout(self):
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        await self.finish_round()


# ---------------------------------------------------------------------------
# Bataille navale — duel avec une grille privée par joueur (messages directs)
# ---------------------------------------------------------------------------

NAVAL_ROWS = "ABCDEFGHIJ"
NAVAL_SHIPS = (5, 4, 3, 3, 2)


class NavalRowSelect(discord.ui.Select):
    def __init__(self, parent: "NavalPrivateView"):
        self.parent_view = parent
        super().__init__(
            placeholder="Ligne de tir…",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=row, value=str(index)) for index, row in enumerate(NAVAL_ROWS)],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_row = int(self.values[0])
        self.parent_view.game.reset_inactivity_timer()
        await interaction.response.edit_message(embed=self.parent_view.make_embed(), view=self.parent_view)


class NavalColumnSelect(discord.ui.Select):
    def __init__(self, parent: "NavalPrivateView"):
        self.parent_view = parent
        super().__init__(
            placeholder="Colonne de tir…",
            min_values=1,
            max_values=1,
            options=[discord.SelectOption(label=str(index + 1), value=str(index)) for index in range(10)],
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_col = int(self.values[0])
        self.parent_view.game.reset_inactivity_timer()
        await interaction.response.edit_message(embed=self.parent_view.make_embed(), view=self.parent_view)


class NavalFireButton(discord.ui.Button):
    def __init__(self, parent: "NavalPrivateView"):
        self.parent_view = parent
        super().__init__(label="Tirer", style=discord.ButtonStyle.primary, emoji="🎯", row=2)

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.game.fire(interaction, self.parent_view)


class NavalAbandonButton(discord.ui.Button):
    def __init__(self, parent: "NavalPrivateView"):
        self.parent_view = parent
        super().__init__(label="Abandonner", style=discord.ButtonStyle.danger, emoji="🏳️", row=2)

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.game.abandon(interaction, self.parent_view)


class NavalPrivateView(discord.ui.View):
    def __init__(self, game: "NavalBattleGame", owner_id: int):
        super().__init__(timeout=3600)
        self.game, self.owner_id = game, owner_id
        self.selected_row: int | None = None
        self.selected_col: int | None = None
        self.message: discord.Message | None = None
        self.add_item(NavalRowSelect(self))
        self.add_item(NavalColumnSelect(self))
        self.add_item(NavalFireButton(self))
        self.add_item(NavalAbandonButton(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Cette grille privée ne t'appartient pas.", ephemeral=True)
            return False
        if self.game.finished:
            await interaction.response.send_message("Cette bataille est terminée.", ephemeral=True)
            return False
        return True

    def make_embed(self, ending: str | None = None) -> discord.Embed:
        opponent_id = self.game.other_player(self.owner_id)
        own_shots = self.game.shots[opponent_id]
        target_shots = self.game.shots[self.owner_id]
        own_rows = []
        target_rows = []
        for row in range(10):
            own_cells = []
            target_cells = []
            for col in range(10):
                coord = (row, col)
                if coord in self.game.hits[self.owner_id]:
                    own_cells.append("💥")
                elif coord in own_shots:
                    own_cells.append("⚪")
                elif coord in self.game.ships[self.owner_id]:
                    own_cells.append("🚢")
                else:
                    own_cells.append("▫️")
                if coord not in target_shots:
                    target_cells.append("❔")
                elif target_shots[coord]:
                    target_cells.append("💥")
                else:
                    target_cells.append("⚪")
            own_rows.append(f"{NAVAL_ROWS[row]}  " + "".join(own_cells))
            target_rows.append(f"{NAVAL_ROWS[row]}  " + "".join(target_cells))
        embed = horizons_embed(title="🚢 Bataille navale — ta grille privée")
        embed.add_field(name="Ta flotte", value="```\n" + "\n".join(own_rows) + "\n```", inline=True)
        embed.add_field(name="Grille adverse", value="```\n" + "\n".join(target_rows) + "\n```", inline=True)
        if ending:
            status = ending
        elif self.game.current_player == self.owner_id:
            status = "🎯 **C'est ton tour !** Choisis une ligne et une colonne, puis tire."
        else:
            status = f"⏳ En attente de <@{self.game.current_player}>."
        if self.selected_row is not None and self.selected_col is not None and not ending:
            status += f"\nCible sélectionnée : **{NAVAL_ROWS[self.selected_row]}{self.selected_col + 1}**."
        embed.add_field(name="État de la partie", value=status, inline=False)
        embed.set_footer(text="🚢 = navire · 💥 = touché · ⚪ = tir manqué · ❔ = case inconnue")
        return embed

    async def on_timeout(self):
        if not self.game.finished:
            await self.game.end_by_timeout()


class NavalBattleGame:
    def __init__(self, cog: "HorizonsArcade", guild: discord.Guild, channel: discord.abc.Messageable, player_one: discord.Member | discord.User, player_two: discord.Member | discord.User):
        self.cog, self.guild, self.channel = cog, guild, channel
        self.guild_id = guild.id
        self.started_at = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        self.players = {player_one.id: player_one, player_two.id: player_two}
        self.player_ids = (player_one.id, player_two.id)
        self.current_player = player_one.id
        self.ships = {player_one.id: self._place_fleet(), player_two.id: self._place_fleet()}
        self.hits = {player_one.id: set(), player_two.id: set()}
        self.shots: dict[int, dict[tuple[int, int], bool]] = {player_one.id: {}, player_two.id: {}}
        self.views: dict[int, NavalPrivateView] = {}
        self.public_message: discord.Message | None = None
        self.finished = False
        self.result_recorded = False
        self.last_result = "La partie commence."
        self.timer_task: asyncio.Task | None = None

    @staticmethod
    def _place_fleet() -> set[tuple[int, int]]:
        occupied: set[tuple[int, int]] = set()
        for length in NAVAL_SHIPS:
            while True:
                horizontal = random.choice((True, False))
                row = random.randrange(10)
                col = random.randrange(10)
                cells = {(row, col + offset) if horizontal else (row + offset, col) for offset in range(length)}
                if all(0 <= r < 10 and 0 <= c < 10 for r, c in cells) and not (cells & occupied):
                    occupied.update(cells)
                    break
        return occupied

    def other_player(self, user_id: int) -> int:
        return self.player_ids[1] if user_id == self.player_ids[0] else self.player_ids[0]

    def public_embed(self, ending: str | None = None) -> discord.Embed:
        if ending:
            description = ending
        else:
            description = (
                "Les deux grilles sont privées et accessibles uniquement dans les messages directs des joueurs.\n\n"
                f"Dernier tir : {self.last_result}\n\n🎯 Au tour de <@{self.current_player}>."
            )
        return horizons_embed(title="🚢 Bataille navale HORIZONS", description=description)

    def record_result(self, winners=(), status="completed"):
        if self.result_recorded:
            return []
        self.result_recorded = True
        return record_game_result(
            self.guild_id, "bataille_navale", "duel", list(self.player_ids),
            winners=winners, status=status, started_at=self.started_at,
        )

    def reset_inactivity_timer(self):
        if self.finished:
            return
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        self.timer_task = asyncio.create_task(self._inactivity_timer())

    async def _inactivity_timer(self):
        await asyncio.sleep(600)
        if not self.finished:
            await self.end_by_timeout()

    async def start(self, interaction: discord.Interaction):
        try:
            self.public_message = await interaction.followup.send(embed=self.public_embed(), wait=True)
            for user_id in self.player_ids:
                view = NavalPrivateView(self, user_id)
                message = await self.players[user_id].send(embed=view.make_embed(), view=view)
                view.message = message
                self.views[user_id] = view
            self.reset_inactivity_timer()
        except (discord.Forbidden, discord.HTTPException):
            self.finished = True
            for view in self.views.values():
                for item in view.children:
                    item.disabled = True
                if view.message:
                    try:
                        await view.message.edit(embed=view.make_embed("Partie annulée : les messages privés n'ont pas pu être ouverts pour les deux joueurs."), view=view)
                    except discord.HTTPException:
                        pass
            if self.public_message:
                try:
                    await self.public_message.edit(embed=self.public_embed("Partie annulée : active les messages privés du serveur pour jouer à la Bataille navale."))
                except discord.HTTPException:
                    pass
            try:
                await interaction.followup.send("La Bataille navale n'a pas pu démarrer. Vérifiez que vos messages privés du serveur sont ouverts.", ephemeral=True)
            except discord.HTTPException:
                pass

    async def fire(self, interaction: discord.Interaction, view: NavalPrivateView):
        if self.finished:
            await interaction.response.send_message("Cette bataille est terminée.", ephemeral=True)
            return
        if interaction.user.id != self.current_player:
            await interaction.response.send_message("Ce n'est pas ton tour. Tu peux consulter ta grille privée, mais attends le prochain tir.", ephemeral=True)
            return
        if view.selected_row is None or view.selected_col is None:
            await interaction.response.send_message("Choisis d'abord une ligne et une colonne.", ephemeral=True)
            return
        coordinate = (view.selected_row, view.selected_col)
        if coordinate in self.shots[view.owner_id]:
            await interaction.response.send_message("Tu as déjà tiré sur cette case. Choisis une autre coordonnée.", ephemeral=True)
            return
        opponent_id = self.other_player(view.owner_id)
        hit = coordinate in self.ships[opponent_id]
        self.shots[view.owner_id][coordinate] = hit
        if hit:
            self.hits[opponent_id].add(coordinate)
            self.last_result = f"💥 <@{view.owner_id}> touche un navire en **{NAVAL_ROWS[coordinate[0]]}{coordinate[1] + 1}**."
        else:
            self.last_result = f"⚪ <@{view.owner_id}> manque sa cible en **{NAVAL_ROWS[coordinate[0]]}{coordinate[1] + 1}**."
        view.selected_row = None
        view.selected_col = None
        self.current_player = opponent_id
        winner_id = view.owner_id if len(self.hits[opponent_id]) == len(self.ships[opponent_id]) else None
        if winner_id:
            self.finished = True
            points = self.cog.award_game_xp(self.guild_id, winner_id, "bataille_navale", 15)
            self.record_result(winners=[winner_id], status="completed")
            ending = f"🏆 <@{winner_id}> a coulé toute la flotte adverse et remporte la bataille ! **+{points} XP Célestes**."
        else:
            ending = None
        if self.finished:
            for item in view.children:
                item.disabled = True
        self.reset_inactivity_timer()
        await interaction.response.edit_message(embed=view.make_embed(ending), view=view)
        if self.public_message:
            await self.public_message.edit(embed=self.public_embed(ending), allowed_mentions=discord.AllowedMentions.none())
        for user_id, other_view in self.views.items():
            if user_id == view.owner_id or not other_view.message:
                continue
            for item in other_view.children:
                if self.finished:
                    item.disabled = True
            try:
                await other_view.message.edit(embed=other_view.make_embed(ending), view=other_view)
            except discord.HTTPException:
                pass
        if self.finished and self.timer_task:
            self.timer_task.cancel()

    async def abandon(self, interaction: discord.Interaction, view: NavalPrivateView):
        if self.finished:
            await interaction.response.send_message("Cette bataille est déjà terminée.", ephemeral=True)
            return
        winner_id = self.other_player(view.owner_id)
        self.finished = True
        points = self.cog.award_game_xp(self.guild_id, winner_id, "bataille_navale", 15)
        self.record_result(winners=[winner_id], status="completed")
        ending = f"<@{view.owner_id}> abandonne. 🏆 <@{winner_id}> remporte la bataille par forfait et gagne **+{points} XP Célestes**."
        if self.timer_task:
            self.timer_task.cancel()
        for item in view.children:
            item.disabled = True
        await interaction.response.edit_message(embed=view.make_embed(ending), view=view)
        if self.public_message:
            await self.public_message.edit(embed=self.public_embed(ending), allowed_mentions=discord.AllowedMentions.none())
        for user_id, other_view in self.views.items():
            if user_id == view.owner_id or not other_view.message:
                continue
            for item in other_view.children:
                item.disabled = True
            try:
                await other_view.message.edit(embed=other_view.make_embed(ending), view=other_view)
            except discord.HTTPException:
                pass

    async def end_by_timeout(self):
        if self.finished:
            return
        self.finished = True
        self.record_result(status="timeout")
        ending = "⏳ La bataille est terminée après dix minutes sans tir. Aucun gagnant n'est désigné."
        if self.public_message:
            try:
                await self.public_message.edit(embed=self.public_embed(ending), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                pass
        for view in self.views.values():
            for item in view.children:
                item.disabled = True
            if view.message:
                try:
                    await view.message.edit(embed=view.make_embed(ending), view=view)
                except discord.HTTPException:
                    pass


# ---------------------------------------------------------------------------
# Soirée Arcade — lobby puis trois manches collectives chronométrées
# ---------------------------------------------------------------------------

ARCADE_NIGHT_QUESTIONS = (
    ("🧠 Culture générale", "Quel est le plus grand océan du monde ?", ("pacifique",), "L'océan Pacifique."),
    ("🔤 Anagramme", "Remets ces lettres dans l'ordre : **N O C R E**", ("corne",), "CORNE."),
    ("🧩 Énigme", "Je peux être tenue, faite ou brisée, sans être un objet. Qui suis-je ?", ("promesse",), "Une promesse."),
    ("🔢 Calcul", "Combien font **12 × 8** ?", ("96",), "96."),
    ("🌍 Géographie", "Quelle est la capitale du Canada ?", ("ottawa",), "Ottawa."),
    ("🧮 Logique", "Je suis un nombre pair, supérieur à 20 et inférieur à 30. Je suis le double de 14. Qui suis-je ?", ("28",), "28."),
)


def _normalize_night_answer(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold().strip())
    return "".join(char for char in decomposed if not unicodedata.combining(char) and char.isalnum())


class ArcadeNightAnswerModal(discord.ui.Modal):
    def __init__(self, parent: "ArcadeNightView"):
        super().__init__(title=f"Soirée Arcade — manche {parent.round_index + 1}")
        self.parent_view = parent
        self.answer = discord.ui.TextInput(label="Ta réponse", placeholder="Écris ta réponse…", max_length=100, required=True)
        self.add_item(self.answer)

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.submit_answer(interaction, str(self.answer.value))


class ArcadeNightAnswerButton(discord.ui.Button):
    def __init__(self, parent: "ArcadeNightView"):
        self.parent_view = parent
        super().__init__(label="Répondre à la manche", style=discord.ButtonStyle.primary, emoji="✍️", row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.phase != "round":
            await interaction.response.send_message("La manche n'accepte plus de réponses.", ephemeral=True)
            return
        if interaction.user.id not in self.parent_view.players:
            await interaction.response.send_message("Tu dois rejoindre la soirée avant de participer.", ephemeral=True)
            return
        if interaction.user.id in self.parent_view.round_answers:
            await interaction.response.send_message("Tu as déjà répondu à cette manche.", ephemeral=True)
            return
        await interaction.response.send_modal(ArcadeNightAnswerModal(self.parent_view))


class ArcadeNightJoinButton(discord.ui.Button):
    def __init__(self, parent: "ArcadeNightView"):
        self.parent_view = parent
        super().__init__(label="Rejoindre", style=discord.ButtonStyle.success, emoji="🙌", row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.phase != "lobby":
            await interaction.response.send_message("La soirée a déjà commencé.", ephemeral=True)
            return
        if interaction.user.id in self.parent_view.players:
            await interaction.response.send_message("Tu es déjà inscrit à cette soirée.", ephemeral=True)
            return
        if len(self.parent_view.players) >= 12:
            await interaction.response.send_message("La soirée est complète : douze joueurs maximum.", ephemeral=True)
            return
        self.parent_view.players.add(interaction.user.id)
        self.parent_view.scores[interaction.user.id] = 0
        await interaction.response.edit_message(embed=self.parent_view.make_embed(), view=self.parent_view)


class ArcadeNightLeaveButton(discord.ui.Button):
    def __init__(self, parent: "ArcadeNightView"):
        self.parent_view = parent
        super().__init__(label="Quitter", style=discord.ButtonStyle.secondary, emoji="🚪", row=0)

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.phase != "lobby":
            await interaction.response.send_message("La soirée a déjà commencé : les inscriptions sont closes.", ephemeral=True)
            return
        if interaction.user.id == self.parent_view.host_id:
            await interaction.response.send_message("L'organisateur ne peut pas quitter le salon d'attente. Il peut annuler la soirée.", ephemeral=True)
            return
        if interaction.user.id not in self.parent_view.players:
            await interaction.response.send_message("Tu n'es pas inscrit à cette soirée.", ephemeral=True)
            return
        self.parent_view.players.remove(interaction.user.id)
        self.parent_view.scores.pop(interaction.user.id, None)
        await interaction.response.edit_message(embed=self.parent_view.make_embed(), view=self.parent_view)


class ArcadeNightStartButton(discord.ui.Button):
    def __init__(self, parent: "ArcadeNightView"):
        self.parent_view = parent
        super().__init__(label="Démarrer la soirée", style=discord.ButtonStyle.primary, emoji="🚀", row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.host_id:
            await interaction.response.send_message("Seul l'organisateur peut démarrer la soirée.", ephemeral=True)
            return
        if len(self.parent_view.players) < 2:
            await interaction.response.send_message("Il faut au moins deux joueurs inscrits pour démarrer.", ephemeral=True)
            return
        await self.parent_view.start_night(interaction)


class ArcadeNightCancelButton(discord.ui.Button):
    def __init__(self, parent: "ArcadeNightView"):
        self.parent_view = parent
        super().__init__(label="Annuler", style=discord.ButtonStyle.danger, emoji="✖️", row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.host_id:
            await interaction.response.send_message("Seul l'organisateur peut annuler la soirée.", ephemeral=True)
            return
        await self.parent_view.cancel_night(interaction)


class ArcadeNightView(discord.ui.View):
    def __init__(self, cog: "HorizonsArcade", host_id: int, guild_id: int, channel_id: int):
        super().__init__(timeout=600)
        self.cog, self.host_id = cog, host_id
        self.guild_id, self.channel_id = guild_id, channel_id
        self.players: set[int] = {host_id}
        self.scores: dict[int, int] = {host_id: 0}
        self.questions = random.sample(ARCADE_NIGHT_QUESTIONS, 3)
        self.round_index = 0
        self.round_answers: dict[int, str] = {}
        self.correct_this_round: list[int] = []
        self.phase = "lobby"
        self.message: discord.Message | None = None
        self.started_at = datetime.now(LOCAL_TIMEZONE).isoformat(timespec="seconds")
        self.timer_task: asyncio.Task | None = None
        self.advance_lock = asyncio.Lock()
        self.add_item(ArcadeNightJoinButton(self))
        self.add_item(ArcadeNightLeaveButton(self))
        self.add_item(ArcadeNightStartButton(self))
        self.add_item(ArcadeNightCancelButton(self))

    def make_embed(self) -> discord.Embed:
        if self.phase == "lobby":
            members = "\n".join(f"• <@{user_id}>" for user_id in sorted(self.players))
            description = (
                f"Une soirée conviviale de **trois manches** attend les joueurs !\n\n"
                f"**Organisateur :** <@{self.host_id}>\n**Inscrits : {len(self.players)}/12**\n\n"
                f"{members}\n\nIl faut au moins deux joueurs. L'organisateur démarre la soirée lorsqu'elle est prête."
            )
            return horizons_embed(title="🌠 Soirée Arcade HORIZONS", description=description)
        if self.phase == "round":
            category, question, _, _ = self.questions[self.round_index]
            leaderboard = sorted(self.scores.items(), key=lambda item: (-item[1], item[0]))
            ranking = "\n".join(f"{index}. <@{uid}> — **{score} pts**" for index, (uid, score) in enumerate(leaderboard[:5], 1))
            description = (
                f"**Manche {self.round_index + 1}/3 — {category}**\n\n{question}\n\n"
                f"⏱️ **30 secondes** · Réponses reçues : **{len(self.round_answers)}/{len(self.players)}**\n\n"
                f"**Classement provisoire**\n{ranking}"
            )
            return horizons_embed(title="🌠 Soirée Arcade HORIZONS", description=description)
        if self.phase == "round_result":
            category, _, accepted, explanation = self.questions[self.round_index]
            correct = ", ".join(f"<@{uid}>" for uid in self.correct_this_round) or "Personne cette fois"
            return horizons_embed(
                title=f"🌠 Manche {self.round_index + 1}/3 — résultats",
                description=f"**{category}**\nRéponse attendue : **{explanation}**\n\nRéponses correctes : {correct}\n\nLe classement va continuer à évoluer !",
            )
        leaderboard = sorted(self.scores.items(), key=lambda item: (-item[1], item[0]))
        lines = [f"**{index}.** <@{uid}> — **{score} points**" for index, (uid, score) in enumerate(leaderboard, 1)]
        high = leaderboard[0][1] if leaderboard else 0
        winners = [uid for uid, score in leaderboard if score == high] if high > 0 else []
        winner_text = "\n\n🏆 Vainqueur(s) : " + ", ".join(f"<@{uid}>" for uid in winners) if winners else "\n\nAucun point marqué : soirée sans vainqueur."
        return horizons_embed(title="🏁 Fin de la Soirée Arcade", description=("\n".join(lines) if lines else "Aucun résultat.") + winner_text)

    async def start_night(self, interaction: discord.Interaction):
        if self.phase != "lobby":
            await interaction.response.send_message("La soirée a déjà commencé.", ephemeral=True)
            return
        self.phase = "round"
        self.clear_items()
        self.add_item(ArcadeNightAnswerButton(self))
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
        self.start_round_timer()

    def start_round_timer(self):
        current = asyncio.current_task()
        if self.timer_task and self.timer_task is not current and not self.timer_task.done():
            self.timer_task.cancel()
        self.timer_task = asyncio.create_task(self._round_timer())

    async def _round_timer(self):
        await asyncio.sleep(30)
        await self.advance_round()

    async def submit_answer(self, interaction: discord.Interaction, answer: str):
        if self.phase != "round" or interaction.user.id not in self.players:
            await interaction.response.send_message("Cette manche n'accepte plus ta réponse.", ephemeral=True)
            return
        if interaction.user.id in self.round_answers:
            await interaction.response.send_message("Tu as déjà répondu à cette manche.", ephemeral=True)
            return
        normalized = _normalize_night_answer(answer)
        self.round_answers[interaction.user.id] = normalized
        accepted = {_normalize_night_answer(value) for value in self.questions[self.round_index][2]}
        correct = normalized in accepted
        if correct:
            self.scores[interaction.user.id] += 10
            self.correct_this_round.append(interaction.user.id)
        await interaction.response.send_message("🎉 Bonne réponse : **+10 points** !" if correct else "Réponse enregistrée. La solution sera révélée à la fin de la manche.", ephemeral=True)
        if self.message:
            await self.message.edit(embed=self.make_embed(), view=self)
        if len(self.round_answers) >= len(self.players):
            await self.advance_round()

    async def advance_round(self):
        async with self.advance_lock:
            if self.phase != "round":
                return
            if self.timer_task and self.timer_task is not asyncio.current_task() and not self.timer_task.done():
                self.timer_task.cancel()
            self.phase = "round_result"
            self.clear_items()
            if self.message:
                await self.message.edit(embed=self.make_embed(), view=self)
            await asyncio.sleep(2.5)
            if self.round_index >= 2:
                await self.finish_night()
                return
            self.round_index += 1
            self.round_answers.clear()
            self.correct_this_round.clear()
            self.phase = "round"
            self.add_item(ArcadeNightAnswerButton(self))
            if self.message:
                await self.message.edit(embed=self.make_embed(), view=self)
            self.start_round_timer()

    async def finish_night(self):
        if self.phase == "finished":
            return
        self.phase = "finished"
        self.stop()
        self.clear_items()
        high = max(self.scores.values()) if self.scores else 0
        winners = [uid for uid, score in self.scores.items() if score == high] if high > 0 else []
        for user_id in self.players:
            self.cog.award_game_xp(self.guild_id, user_id, "arcade_night", 10 if user_id in winners else 5)
        record_game_result(
            self.guild_id, "arcade_night", "collectif", list(self.players),
            winners=winners, status="completed" if winners else "draw",
            scores=self.scores, started_at=self.started_at,
        )
        if self.message:
            await self.message.edit(embed=self.make_embed(), view=self)
        self.cog.release_collective_session(self.guild_id, self.channel_id)

    async def cancel_night(self, interaction: discord.Interaction):
        if self.phase != "lobby":
            await interaction.response.send_message("Une soirée déjà commencée ne peut plus être annulée depuis le salon d'attente.", ephemeral=True)
            return
        self.phase = "finished"
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=horizons_embed(title="Soirée Arcade annulée", description="L'organisateur a annulé cette soirée."), view=self)
        self.cog.release_collective_session(self.guild_id, self.channel_id)

    async def on_timeout(self):
        if self.phase == "lobby":
            self.phase = "finished"
            for item in self.children:
                item.disabled = True
            if self.message:
                try:
                    await self.message.edit(embed=horizons_embed(title="Soirée Arcade expirée", description="Le salon d'attente a expiré faute de démarrage."), view=self)
                except discord.HTTPException:
                    pass
            self.cog.release_collective_session(self.guild_id, self.channel_id)
        elif self.phase == "round":
            await self.advance_round()


class ArcadeNightButton(discord.ui.Button):
    def __init__(self, parent: ArcadeMenuView):
        self.parent_view = parent
        super().__init__(label="Soirée Arcade", style=discord.ButtonStyle.success, emoji="🌠", row=1)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.channel:
            await interaction.response.send_message("La Soirée Arcade se lance dans un salon du serveur.", ephemeral=True)
            return
        session_key = (interaction.guild_id, interaction.channel.id)
        current = self.parent_view.cog.active_collective_sessions.get(session_key)
        if current and not current.is_finished():
            await interaction.response.send_message("Une activité collective est déjà en cours dans ce salon.", ephemeral=True)
            return
        view = ArcadeNightView(self.parent_view.cog, interaction.user.id, interaction.guild_id, interaction.channel.id)
        self.parent_view.cog.active_collective_sessions[session_key] = view
        await interaction.response.edit_message(embed=horizons_embed(title="🌠 Soirée Arcade créée", description="Le salon d'attente est ouvert dans le salon."), view=None)
        try:
            message = await interaction.channel.send(embed=view.make_embed(), view=view)
            view.message = message
        except discord.HTTPException:
            self.parent_view.cog.release_collective_session(*session_key)
            await interaction.followup.send("Je n'ai pas pu ouvrir le salon d'attente dans ce canal.", ephemeral=True)

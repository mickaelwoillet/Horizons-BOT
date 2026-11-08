"""Tests locaux de logique et de construction des interfaces Arcade.

Exécution : py tests/test_arcade_games.py
Aucune connexion Discord ni aucun token ne sont nécessaires.
"""
from __future__ import annotations

import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cogs.arcade_games import (
    ArcadeMenuView,
    ArcadeNightView,
    CodeSecretView,
    ConnectFourView,
    MemoryView,
    NavalBattleGame,
    NavalPrivateView,
    PetitBacView,
    TicTacToeView,
    _ai_move,
    _winner,
)


class FakeCog:
    def __init__(self):
        self.awards = []
        self.active_collective_sessions = {}

    def award_game_xp(self, guild_id, user_id, game_key, amount=10):
        self.awards.append((guild_id, user_id, game_key, amount))
        return amount

    def release_collective_session(self, guild_id, channel_id):
        self.active_collective_sessions.pop((guild_id, channel_id), None)


class FakeUser:
    def __init__(self, user_id: int):
        self.id = user_id
        self.display_name = f"Membre {user_id}"


class ArcadeGamesTests(unittest.TestCase):
    def setUp(self):
        self.cog = FakeCog()

    def test_menu_contains_six_games(self):
        view = ArcadeMenuView(self.cog, 100)
        self.assertEqual(len(view.children[0].options), 6)
        self.assertLessEqual(len(view.to_components()), 5)


    def test_arcade_night_lobby_has_three_rounds_and_four_controls(self):
        view = ArcadeNightView(self.cog, 100, 123, 456)
        self.assertEqual(len(view.questions), 3)
        self.assertEqual(view.players, {100})
        self.assertEqual(len(view.children), 4)
        self.assertIn("Soirée Arcade", view.make_embed().title)
        self.assertLessEqual(len(view.to_components()), 5)

    def test_tictactoe_ai_wins_and_blocks(self):
        board = ["O", "O", "·", "X", "X", "·", "·", "·", "·"]
        self.assertEqual(_ai_move(board, "difficile"), 2)
        board = ["X", "X", "·", "O", "·", "·", "·", "O", "·"]
        self.assertEqual(_ai_move(board, "moyen"), 2)
        self.assertEqual(_winner(["X", "X", "X", "·", "·", "·", "·", "·", "·"], 3, 3), "X")

    def test_connect_four_detects_horizontal_vertical_diagonal(self):
        view = ConnectFourView(self.cog, 100, 200)
        view.board[5] = ["R", "R", "R", "R", "·", "·", "·"]
        self.assertEqual(view._winner(), "R")
        view.board = [["·"] * 7 for _ in range(6)]
        for row in (2, 3, 4, 5):
            view.board[row][0] = "Y"
        self.assertEqual(view._winner(), "Y")
        view.board = [["·"] * 7 for _ in range(6)]
        for row, col in ((5, 0), (4, 1), (3, 2), (2, 3)):
            view.board[row][col] = "R"
        self.assertEqual(view._winner(), "R")

    def test_memory_has_eight_pairs(self):
        view = MemoryView(self.cog, 100)
        self.assertEqual(len(view.cards), 16)
        self.assertEqual(set(view.cards), set(MemoryView.PAIRS))
        self.assertTrue(all(view.cards.count(card) == 2 for card in MemoryView.PAIRS))

    def test_code_secret_has_four_distinct_digits(self):
        view = CodeSecretView(self.cog, 100)
        self.assertEqual(len(view.secret), 4)
        self.assertEqual(len(set(view.secret)), 4)
        self.assertTrue(set(view.secret).issubset(set("123456")))

    def test_petit_bac_scoring_and_vote_threshold(self):
        view = PetitBacView(self.cog, 100, 999)
        view.participants = {
            100: {"Prénom": "Alice", "Ville ou pays": "Amiens", "Animal": "Aigle", "Métier": "Architecte"},
            200: {"Prénom": "Arthur", "Ville ou pays": "Angers", "Animal": "Abeille", "Métier": "Artisan"},
            300: {"Prénom": "Alain", "Ville ou pays": "Annecy", "Animal": "Antilope", "Métier": "Astronome"},
        }
        scores = view.calculate_scores()
        self.assertEqual(scores, {100: 40, 200: 40, 300: 40})
        view.votes["alice"] = {200: "réponse à vérifier", 300: "réponse à vérifier"}
        scores = view.calculate_scores()
        self.assertEqual(scores[100], 30)

    def test_naval_fleets_are_private_valid_seventeen_cell_grids(self):
        game = NavalBattleGame(self.cog, SimpleNamespace(id=999), None, FakeUser(100), FakeUser(200))
        for user_id in (100, 200):
            fleet = game.ships[user_id]
            self.assertEqual(len(fleet), 17)
            self.assertTrue(all(0 <= row < 10 and 0 <= col < 10 for row, col in fleet))
            view = NavalPrivateView(game, user_id)
            self.assertEqual(len(view.children), 4)
            self.assertEqual(len(view.make_embed().fields), 3)

    def test_all_interactive_views_fit_discord_component_limits(self):
        views = (
            ArcadeMenuView(self.cog, 100),
            TicTacToeView(self.cog, 100),
            TicTacToeView(self.cog, 100, 200),
            ConnectFourView(self.cog, 100, 200),
            MemoryView(self.cog, 100),
            CodeSecretView(self.cog, 100),
            PetitBacView(self.cog, 100, 999),
        )
        for view in views:
            self.assertLessEqual(len(view.to_components()), 5)
            self.assertLessEqual(len(view.children), 25)




class FakeMessage:
    async def edit(self, **kwargs):
        self.last_edit = kwargs


class FakeResponse:
    async def edit_message(self, **kwargs):
        self.last_edit = kwargs

    async def send_message(self, *args, **kwargs):
        self.last_send = (args, kwargs)


class FakeInteraction:
    def __init__(self, user_id: int):
        self.user = FakeUser(user_id)
        self.response = FakeResponse()
        self.guild_id = None


class ArcadeAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_arcade_night_records_correct_answer_and_points(self):
        view = ArcadeNightView(FakeCog(), 100, 999, 456)
        view.players.add(200)
        view.scores[200] = 0
        view.phase = "round"
        view.message = FakeMessage()
        expected = view.questions[0][2][0]
        interaction = FakeInteraction(100)
        await view.submit_answer(interaction, expected)
        self.assertEqual(view.scores[100], 10)
        self.assertIn(100, view.correct_this_round)
        self.assertIn(100, view.round_answers)

    async def test_arcade_night_finish_awards_and_releases_lobby(self):
        from unittest.mock import patch
        cog = FakeCog()
        view = ArcadeNightView(cog, 100, 999, 456)
        view.players.add(200)
        view.scores[100] = 20
        view.scores[200] = 10
        view.message = FakeMessage()
        cog.active_collective_sessions[(999, 456)] = view
        with patch("cogs.arcade_games.record_game_result", return_value=[]):
            await view.finish_night()
        self.assertEqual(view.phase, "finished")
        self.assertIn((999, 100, "arcade_night", 10), cog.awards)
        self.assertIn((999, 200, "arcade_night", 5), cog.awards)
        self.assertNotIn((999, 456), cog.active_collective_sessions)

    async def test_naval_turns_record_hit_and_miss(self):
        cog = FakeCog()
        game = NavalBattleGame(cog, SimpleNamespace(id=999), None, FakeUser(100), FakeUser(200))
        for user_id in (100, 200):
            view = NavalPrivateView(game, user_id)
            view.message = FakeMessage()
            game.views[user_id] = view
        game.public_message = FakeMessage()

        hit = next(iter(game.ships[200]))
        view_one = game.views[100]
        view_one.selected_row, view_one.selected_col = hit
        await game.fire(FakeInteraction(100), view_one)
        self.assertTrue(game.shots[100][hit])
        self.assertEqual(game.current_player, 200)

        miss = next((row, col) for row in range(10) for col in range(10) if (row, col) not in game.ships[100])
        view_two = game.views[200]
        view_two.selected_row, view_two.selected_col = miss
        await game.fire(FakeInteraction(200), view_two)
        self.assertFalse(game.shots[200][miss])
        self.assertEqual(game.current_player, 100)

    async def test_naval_abandonment_awards_other_player(self):
        cog = FakeCog()
        game = NavalBattleGame(cog, SimpleNamespace(id=999), None, FakeUser(100), FakeUser(200))
        view = NavalPrivateView(game, 100)
        view.message = FakeMessage()
        other = NavalPrivateView(game, 200)
        other.message = FakeMessage()
        game.views = {100: view, 200: other}
        game.public_message = FakeMessage()
        from unittest.mock import patch
        with patch("cogs.arcade_games.record_game_result", return_value=[]):
            await game.abandon(FakeInteraction(100), view)
        self.assertTrue(game.finished)
        self.assertEqual(cog.awards[-1], (999, 200, "bataille_navale", 15))


if __name__ == "__main__":
    unittest.main(verbosity=2)

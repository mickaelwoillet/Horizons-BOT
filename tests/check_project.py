"""Contrôles locaux sans connexion Discord ni token."""
from __future__ import annotations
import ast
import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    errors = []
    py_files = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts and ".venv" not in p.parts]
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        if path.name != "check_project.py" and ("discord." + "NewsChannel") in source:
            raise SystemExit(f"Type discord.NewsChannel non pris en charge dans {path.relative_to(ROOT)}.")

    json_files = [p for p in ROOT.rglob("*.json") if ".venv" not in p.parts and "__pycache__" not in p.parts]
    for path in json_files:
        json.loads(path.read_text(encoding="utf-8"))
    # Les banques de blagues sont stockées sous la forme {categorie: [textes]}.
    joke_count = 0
    for path in (ROOT / "data" / "blagues").glob("*.json"):
        if path.stem == "devinettes":
            continue  # banque structurée distincte des blagues textuelles
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get(path.stem, []) if isinstance(payload, dict) else payload
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
            raise SystemExit(f"Format invalide pour la catégorie de blagues {path.stem}.")
        if len(values) != len(set(values)):
            raise SystemExit(f"Doublons détectés dans la catégorie de blagues {path.stem}.")
        joke_count += len(values)
    riddles = json.loads((ROOT / "data" / "devinettes.json").read_text(encoding="utf-8"))
    if not isinstance(riddles, list) or len(riddles) < 20 or any(not q.get("question") or not q.get("reponse") for q in riddles if isinstance(q, dict)):
        raise SystemExit("La banque doit contenir au moins 20 devinettes question/réponse.")
    quiz = json.loads((ROOT / "data" / "quiz_culturel.json").read_text(encoding="utf-8"))
    if not isinstance(quiz, list) or not quiz or any(not isinstance(q, dict) or not q.get("question") or not q.get("reponse") for q in quiz):
        raise SystemExit("La banque du quiz culturel est vide ou invalide.")
    questions = json.loads((ROOT / "data" / "questions_du_jour.json").read_text(encoding="utf-8"))
    compliments = json.loads((ROOT / "data" / "compliments.json").read_text(encoding="utf-8"))
    if not isinstance(questions, list) or not questions or not isinstance(compliments, list) or not compliments:
        raise SystemExit("Les contenus communautaires sont absents ou invalides.")

    # Banques du calendrier éditorial : formats et volumes validés avant déploiement.
    expected_banks = {
        "citations.json": (50, {"id", "texte", "auteur", "theme"}),
        "proverbes.json": (50, {"id", "texte", "origine", "theme"}),
        "evenements.json": (100, {"id", "date", "titre", "description", "categorie", "reference"}),
        "messages.json": (50, {"id", "texte", "categorie"}),
        "quiz.json": (100, {"question", "reponse", "categorie"}),
        "jeux.json": (50, {"id", "nom", "consigne", "categorie", "duree", "materiel"}),
        "questions.json": (100, {"id", "texte", "categorie"}),
    }
    for filename, (expected_count, required_keys) in expected_banks.items():
        payload = json.loads((ROOT / "data" / filename).read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(payload) != expected_count:
            raise SystemExit(f"{filename} doit contenir exactement {expected_count} entrées.")
        for index, item in enumerate(payload, 1):
            if not isinstance(item, dict) or not required_keys.issubset(item):
                raise SystemExit(f"Entrée {index} invalide dans {filename}.")
            if any(not str(item[key]).strip() for key in required_keys):
                raise SystemExit(f"Champ vide dans {filename}, entrée {index}.")

    weekly = json.loads((ROOT / "data" / "weekly_animations.json").read_text(encoding="utf-8"))
    if not isinstance(weekly, list) or len(weekly) < 20:
        raise SystemExit("La banque des animations hebdomadaires doit contenir au moins 20 activités.")
    weekly_ids = [item.get("id") for item in weekly if isinstance(item, dict)]
    if len(weekly_ids) != len(weekly) or len(weekly_ids) != len(set(weekly_ids)):
        raise SystemExit("Identifiants invalides ou doublons dans weekly_animations.json.")
    for index, item in enumerate(weekly, 1):
        required = {"id", "nom", "description", "consigne", "categorie", "duree", "materiel"}
        if not isinstance(item, dict) or not required.issubset(item) or any(not str(item[k]).strip() for k in required):
            raise SystemExit(f"Animation hebdomadaire incomplète : entrée {index}.")

    calendar_cog = ROOT / "cogs" / "publication_calendar.py"
    if not calendar_cog.is_file():
        raise SystemExit("L’extension du calendrier est absente.")
    if (ROOT / "cogs" / "publication_tests.py").exists():
        raise SystemExit("Le module de test des publications doit rester supprimé.")

    storage = (ROOT / "cogs" / "storage.py").read_text(encoding="utf-8")
    start = storage.index('SCHEMA = """') + len('SCHEMA = """')
    end = storage.index('"""', start)
    connection = sqlite3.connect(":memory:")
    connection.executescript(storage[start:end])
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"warnings", "member_notes", "birthdays", "events", "event_rsvps", "giveaways", "giveaway_entries", "tickets", "activity_days", "passport_completions", "passport_week_announcements", "activity_requests", "activity_request_interests", "collective_challenges", "collective_challenge_members", "role_panels", "bot_settings", "mood_entries", "success_unlocks", "success_activity_days", "affinity_optins", "event_reminders", "community_ideas", "community_idea_votes", "solidarity_thanks", "staff_tasks", "staff_task_history", "staff_shifts", "staff_alerts", "horizons_dashboard_message_daily", "horizons_dashboard_member_daily", "horizons_dashboard_meta", "celestial_game_xp", "celestial_game_rewards", "celestial_game_settings", "celestial_game_history", "celestial_game_player_stats", "celestial_game_achievements", "celestial_weekly_missions", "celestial_stars", "celestial_dust", "celestial_fragments", "celestial_daily_cards", "celestial_gift_cards", "celestial_gift_history", "celestial_star_progress"}
    if required - tables:
        raise SystemExit(f"Tables manquantes : {sorted(required - tables)}")
    treasures_source = (ROOT / "cogs" / "celestial_treasures.py").read_text(encoding="utf-8")
    if "STAR_PITY_LIMIT = 12" not in treasures_source:
        raise SystemExit("La protection contre les séries de doublons doit être réglée à 12 tirages.")
    if "REWARD_WEIGHTS = {\"thought\": 40, \"dust\": 25, \"xp\": 15, \"star\": 12, \"fragment\": 7, \"surprise\": 1}" not in treasures_source:
        raise SystemExit("La pondération des cartes à gratter est absente ou modifiée.")
    if "choose_star_key" not in treasures_source or "consecutive_duplicates" not in treasures_source:
        raise SystemExit("La protection de progression des étoiles est incomplète.")

    bot_tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
    extensions = []
    for node in bot_tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "EXTENSIONS":
            extensions = [item.value for item in node.value.elts]
    for extension in extensions:
        module_path = ROOT.joinpath(*extension.split(".")).with_suffix(".py")
        if not module_path.is_file():
            raise SystemExit(f"Extension absente : {extension}")

    # Vérifie que chaque symbole importé depuis config.py est réellement défini.
    config_tree = ast.parse((ROOT / "config.py").read_text(encoding="utf-8"))
    config_names = set()
    for node in ast.walk(config_tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            config_names.update(target.id for target in targets if isinstance(target, ast.Name))
    for source_path in [ROOT / "bot.py", *((ROOT / "cogs").glob("*.py"))]:
        source_tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(source_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "config":
                missing_names = [item.name for item in node.names if item.name not in config_names]
                if missing_names:
                    raise SystemExit(f"Import(s) config.py manquant(s) dans {source_path.name} : {missing_names}")

    commands = []
    for path in py_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "command":
                keywords = {item.arg: item.value for item in node.keywords}
                name_node = keywords.get("name")
                desc_node = keywords.get("description")
                if isinstance(name_node, ast.Constant):
                    name = name_node.value
                    description = desc_node.value if isinstance(desc_node, ast.Constant) else ""
                    if not re.fullmatch(r"[a-z0-9_-]{1,32}", name):
                        raise SystemExit(f"Nom de commande invalide : {name}")
                    if len(description) > 100:
                        raise SystemExit(f"Description trop longue : {name}")
                    commands.append(name)
    if len(commands) != len(set(commands)):
        raise SystemExit("Des noms de commandes slash sont dupliqués.")

    # Progression communautaire : contributions, entraide, missions et parcours
    # doivent alimenter le même registre de succès, sans système de points/classement.
    progression_sources = {
        "cogs/horizons_features.py": ("ACHIEVEMENTS", "first_day", "seven_days", "thirty_days", "passport_week", "check_achievements"),
        "cogs/community_hub.py": ("check_achievements", "solidarity_thanks", "community_ideas"),
        "cogs/experiences.py": ("check_achievements", "passport_completions", "collective_challenge_members"),
        "cogs/horizons_path.py": ("check_achievements", "horizons_path_progress"),
        "cogs/community_ranks.py": ("name=\"mon_parcours\"", "datetime.now(timezone.utc)", "activity_days"),
    }
    for filename, markers in progression_sources.items():
        source = (ROOT / filename).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in source:
                raise SystemExit(f"Intégration de progression manquante : {filename} / {marker}")

    dashboard_path = ROOT / "cogs" / "horizons_dashboard.py"
    if not dashboard_path.is_file():
        raise SystemExit("Le tableau de bord analytique HORIZONS est absent.")
    dashboard_source = dashboard_path.read_text(encoding="utf-8")
    for marker in (
        'name="horizons_dashboard"', "access_level(interaction.user)",
        "horizons_dashboard_message_daily", "activity_days",
        "Aucune statistique individuelle", "ephemeral=True",
    ):
        if marker not in dashboard_source:
            raise SystemExit(f"Protection ou indicateur manquant dans le tableau de bord : {marker}")

    theme = (ROOT / "cogs" / "embed_theme.py").read_text(encoding="utf-8")
    if "def horizons_embed(" not in theme or not (ROOT / "data" / "assets" / "logo_horizons.png").is_file():
        raise SystemExit("Le système d'identité visuelle HORIZONS ou son logo est absent.")
    for path in (ROOT / "cogs").glob("*.py"):
        if path.name != "embed_theme.py" and "discord.Embed(" in path.read_text(encoding="utf-8"):
            raise SystemExit(f"Embed non centralisé détecté dans {path.name}.")

    if not (ROOT / ".env.example").is_file():
        raise SystemExit("Le modèle .env.example est absent.")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    config_source = (ROOT / "config.py").read_text(encoding="utf-8")
    if "RIDDLE_DAILY_CHANNEL_ID = env_int(\"RIDDLE_DAILY_CHANNEL_ID\", 1567198113318568158)" not in config_source:
        raise SystemExit("L'identifiant par défaut du salon des devinettes est incorrect.")
    if "RIDDLE_DAILY_CHANNEL_ID=1567198113318568158" not in env_example:
        raise SystemExit("Le salon des devinettes n'est pas corrigé dans .env.example.")

    calendar_source = (ROOT / "cogs" / "publication_calendar.py").read_text(encoding="utf-8")
    for schedule in (
        "time(hour=8, minute=0", "time(hour=13, minute=30", "time(hour=19, minute=30",
        "time(hour=21, minute=30",
    ):
        if schedule not in calendar_source:
            raise SystemExit(f"Horaire quotidien manquant dans le calendrier : {schedule}")
    schedule_sources = {
        "cogs/community.py": "time(hour=11,minute=30",
        "cogs/jokes.py": "time(hour=15, minute=30",
        "cogs/riddles.py": "time(hour=17, minute=30",
        "cogs/horizons_daily.py": "time(hour=9, minute=30",
        "cogs/birthdays.py": "time(hour=9, minute=0",
        "cogs/weekly_animations.py": "time(hour=19, minute=30",
    }
    for filename, marker in schedule_sources.items():
        if marker not in (ROOT / filename).read_text(encoding="utf-8"):
            raise SystemExit(f"Horaire éditorial manquant dans {filename}: {marker}")
    for required_extension in ("cogs.horizons_daily", "cogs.publication_calendar", "cogs.weekly_animations"):
        if required_extension not in extensions:
            raise SystemExit(f"Extension attendue non chargée : {required_extension}")
    for required_extension in ("cogs.horizons_arcade", "cogs.celestial_treasures"):
        if required_extension not in extensions:
            raise SystemExit(f"Extension ludique non chargée : {required_extension}")
    if "cogs.ludic_structure" in extensions:
        raise SystemExit("L'ancienne extension de création de structure ne doit plus être chargée.")
    retired_structure = (ROOT / "cogs" / "ludic_structure.py").read_text(encoding="utf-8")
    if 'name="ajoutstructure"' in retired_structure or "@app_commands.command" in retired_structure:
        raise SystemExit("La commande historique /ajoutstructure doit être retirée.")
    arcade_source = (ROOT / "cogs" / "horizons_arcade.py").read_text(encoding="utf-8")
    for marker in ("async def quizjeu", "async def anagramme", "async def enigme", "async def defi_collectif", "CollectiveGameView", "active_collective_sessions", "Terminer le défi", "BEGIN IMMEDIATE", "DAILY_CAP = 60", "celestial_game_rewards", "refresh_arcade_info", "ArcadeMenuView", "arcade_channel_id", "self.arcade_channel_id(interaction.guild)"):
        if marker not in arcade_source:
            raise SystemExit(f"Système Arcade incomplet : {marker}")
    arcade_games_path = ROOT / "cogs" / "arcade_games.py"
    if not arcade_games_path.is_file():
        raise SystemExit("Le module des nouveaux jeux interactifs est absent.")
    if not (ROOT / "tests" / "test_arcade_games.py").is_file():
        raise SystemExit("Les tests locaux de logique Arcade sont absents.")
    arcade_games_source = arcade_games_path.read_text(encoding="utf-8")
    for marker in ("class ArcadeMenuView", "class QuickGameButton", "class CollectiveGameSelect", "class TicTacToeView", "class ConnectFourView", "class MemoryView", "class CodeSecretView", "class PetitBacView", "class NavalBattleGame", "class NavalPrivateView", "class ArcadeNightView", "class ArcadeNightButton", "class ChallengeInviteView", "class AbandonGameButton", "_minimax", "difficile", "puissance4", "PETIT_BAC_CATEGORIES", "NAVAL_SHIPS"):
        if marker not in arcade_games_source:
            raise SystemExit(f"Nouveau jeu interactif incomplet : {marker}")
    if 'name="jeux"' not in arcade_source or "view=view" not in arcade_source:
        raise SystemExit("/jeux doit ouvrir le nouveau menu interactif.")
    progress_source = (ROOT / "cogs" / "arcade_progress.py").read_text(encoding="utf-8")
    for marker in ("def record_game_result", "def get_game_stats", "def get_game_history", "def get_achievements", "def get_weekly_missions", "def get_pending_weekly_missions", "def claim_all_weekly_missions", "class ProgressView", "premiere_victoire", "bataille_navale_5", "WEEKLY_MISSIONS"):
        if marker not in progress_source:
            raise SystemExit(f"Progression Arcade incomplète : {marker}")
    if 'name="xpjeux"' not in arcade_source or "ProgressView" not in arcade_source:
        raise SystemExit("/xpjeux doit ouvrir le passeport interactif.")
    if not (ROOT / "tests" / "test_arcade_progress.py").is_file():
        raise SystemExit("Les tests de statistiques et de succès Arcade sont absents.")
    treasures_source = (ROOT / "cogs" / "celestial_treasures.py").read_text(encoding="utf-8")
    if "def treasures_channel_id" not in treasures_source:
        raise SystemExit("La détection du salon Trésors du Ciel est absente.")
    for marker in ("BEGIN IMMEDIATE", "recompense_thought.png", "recompense_star.png", "recompense_dust.png", "missing_assets"):
        if marker not in treasures_source:
            errors.append(f"Sécurité / visuels Trésors du Ciel : marqueur absent {marker}")
    for asset in ("carte_celeste.png", "recompense_thought.png", "recompense_star.png", "recompense_dust.png", "recompense_xp.png", "recompense_fragment.png", "recompense_surprise.png", "souvenir_origines.png", "souvenir_liens.png", "souvenir_forces.png", "souvenir_lumieres.png", "souvenir_infini.png", "souvenir_complet.png"):
        if not (ROOT / "data" / "assets" / "celestial" / asset).is_file():
            errors.append(f"Visuel céleste manquant : {asset}")
    for marker in ("class TreasurePanelView", "name=\"givegratte\"", "10 fragments", 'REWARD_WEIGHTS = {"thought": 40, "dust": 25, "xp": 15, "star": 12, "fragment": 7, "surprise": 1}', "refresh_treasures_info", "Gardien des 20 étoiles", "STAR_PITY_LIMIT = 12", "sync_collection_unlocks"):
        if marker not in treasures_source:
            raise SystemExit(f"Système Trésors du Ciel incomplet : {marker}")
    if "CREATE TABLE IF NOT EXISTS celestial_collection_unlocks" not in (ROOT / "cogs" / "storage.py").read_text(encoding="utf-8"):
        raise SystemExit("La persistance des souvenirs de collection est absente du schéma SQLite.")
    if "async def on_member_join" not in treasures_source or "award_star_roles(member.guild, member)" not in treasures_source:
        raise SystemExit("La restauration automatique des rôles célestes à la reconnexion est absente.")
    for asset in ("carte_celeste.png", "recompense_thought.png", "recompense_star.png", "recompense_dust.png", "recompense_xp.png", "recompense_fragment.png", "recompense_surprise.png", "souvenir_origines.png", "souvenir_liens.png", "souvenir_forces.png", "souvenir_lumieres.png", "souvenir_infini.png", "souvenir_complet.png"):
        if not (ROOT / "data" / "assets" / "celestial" / asset).is_file():
            raise SystemExit(f"Illustration céleste absente : {asset}")
    for filename in ("jokes.py", "riddles.py", "quizzes.py", "horizons_daily.py"):
        if not (ROOT / "cogs" / filename).is_file():
            raise SystemExit(f"Routine quotidienne existante absente : {filename}")
    if "build_treasures_embed" not in treasures_source or "refresh_treasures_info" not in treasures_source:
        raise SystemExit("Le panneau d'information du salon Trésors du Ciel est absent.")
    if "build_arcade_embed" not in arcade_source or "refresh_arcade_info" not in arcade_source:
        raise SystemExit("Le panneau d'information du salon Arcade HORIZONS est absent.")
    if 'SUGGESTION_CHANNEL_ID = env_int("IDEAS_CHANNEL_ID", 1567300011165880451)' not in config_source:
        raise SystemExit("Le regroupement Suggestions vers Boîte à idées est incorrect.")

    if errors:
        raise SystemExit("\n".join(errors))

    for setting in (
        'HORIZON_DAILY_CHANNEL_ID = env_int("HORIZON_DAILY_CHANNEL_ID", 1567844795307532308)',
        'DEBATE_CHANNEL_ID = env_int("DEBATE_CHANNEL_ID", 1566850089761382553)',
        'INSPIRATION_CHANNEL_ID = env_int("INSPIRATION_CHANNEL_ID", 1568958163875528754)',
    ):
        if setting not in config_source:
            raise SystemExit(f"Configuration de publication manquante : {setting}")
    if "cogs.server_reorganization" in extensions or (ROOT / "cogs" / "server_reorganization.py").exists():
        raise SystemExit("Les commandes de restructuration doivent être retirées du bot.")

    general_source = (ROOT / "cogs" / "general.py").read_text(encoding="utf-8")
    if "isinstance(channel, discord.ForumChannel)" not in general_source or "channel.create_thread" not in general_source:
        raise SystemExit("La commande /proposer doit prendre en charge le salon Suggestions de type Forum.")

    audit_cog = ROOT / "cogs" / "server_audit_export.py"
    if not audit_cog.is_file():
        raise SystemExit("La commande /export_structure est absente.")
    audit_source = audit_cog.read_text(encoding="utf-8")
    if "@app_commands.checks.has_permissions(administrator=True)" not in audit_source or "ephemeral=True" not in audit_source:
        raise SystemExit("/export_structure doit être réservée aux administrateurs et répondre en privé.")
    if "cogs.server_audit_export" not in extensions:
        raise SystemExit("L'extension /export_structure n'est pas chargée par bot.py.")
    required_settings = {
        "INSPIRATION_CHANNEL_ID", "TEMP_VOICE_TRIGGER_ID", "TEMP_VOICE_CATEGORY_ID",
        "TICKET_REQUEST_CHANNEL_ID", "TICKET_CATEGORY_ID",
        "ANONYMOUS_CHANNEL_ID", "RANK_ROLE_IDS", "EXPERIENCES_CATEGORY_ID", "MISSIONS_CHANNEL_ID", "FIND_PARTNER_CHANNEL_ID", "COLLECTIVE_CHALLENGES_CHANNEL_ID", "MOOD_CHANNEL_ID", "SUCCESS_CHANNEL_ID", "AGENDA_CHANNEL_ID", "AFFINITY_CHANNEL_ID", "HORIZON_DAILY_CHANNEL_ID", "DEBATE_CHANNEL_ID",
    }
    present_settings = {
        line.split("=", 1)[0].strip()
        for line in env_example.splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }
    if required_settings - present_settings:
        raise SystemExit(f"Paramètres manquants dans .env.example : {sorted(required_settings - present_settings)}")
    rank_line = next(line for line in env_example.splitlines() if line.startswith("RANK_ROLE_IDS="))
    # Décoder la syntaxe .env (guillemets externes et échappement JSON).
    from dotenv import dotenv_values
    rank_mapping = json.loads(dotenv_values(ROOT / ".env.example")["RANK_ROLE_IDS"])
    expected_ranks = {
        "Nouveau regard", "Premier pas", "Voix familière", "Esprit ouvert",
        "Lien vivant", "Éclaireur", "Bâtisseur d'horizons",
    }
    if set(rank_mapping) != expected_ranks:
        raise SystemExit("Les sept noms de rangs ne correspondent pas à la configuration attendue.")

    if (ROOT / ".env").exists():
        raise SystemExit("Un fichier .env réel ne doit pas être distribué dans l'archive.")

    print(f"Contrôles réussis : {len(py_files)} fichiers Python, {len(json_files)} fichiers JSON, {len(extensions)} extensions et {len(commands)} commandes slash.")
    print(f"Contenus vérifiés : {joke_count} blagues, {len(riddles)} devinettes, {len(quiz)} questions de quiz, {len(questions)} questions du jour et {len(compliments)} compliments.")
    print("Syntaxe, données JSON, banques quotidiennes/hebdomadaires, noms de commandes et schéma SQLite vérifiés.")
    print("Ce contrôle ne se connecte pas à Discord et ne remplace pas un test avec le bot en ligne.")


if __name__ == "__main__":
    main()

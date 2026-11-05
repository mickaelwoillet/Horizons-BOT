"""Contrôles locaux sans connexion Discord ni token."""
from __future__ import annotations
import ast
import json
import pathlib
import re
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> None:
    py_files = [p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts]
    for path in py_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    json_files = list(ROOT.rglob("*.json"))
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

    storage = (ROOT / "cogs" / "storage.py").read_text(encoding="utf-8")
    start = storage.index('SCHEMA = """') + len('SCHEMA = """')
    end = storage.index('"""', start)
    connection = sqlite3.connect(":memory:")
    connection.executescript(storage[start:end])
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {"warnings", "member_notes", "birthdays", "events", "event_rsvps", "giveaways", "giveaway_entries", "tickets", "activity_days", "passport_completions", "passport_week_announcements", "activity_requests", "activity_request_interests", "collective_challenges", "collective_challenge_members", "role_panels", "bot_settings", "mood_entries", "success_unlocks", "success_activity_days", "affinity_optins", "event_reminders", "community_ideas", "community_idea_votes", "solidarity_thanks", "staff_tasks", "staff_task_history", "staff_shifts", "staff_alerts"}
    if required - tables:
        raise SystemExit(f"Tables manquantes : {sorted(required - tables)}")

    bot_tree = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
    extensions = []
    for node in bot_tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "EXTENSIONS":
            extensions = [item.value for item in node.value.elts]
    for extension in extensions:
        module_path = ROOT.joinpath(*extension.split(".")).with_suffix(".py")
        if not module_path.is_file():
            raise SystemExit(f"Extension absente : {extension}")

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

    theme = (ROOT / "cogs" / "embed_theme.py").read_text(encoding="utf-8")
    if "def horizons_embed(" not in theme or not (ROOT / "data" / "assets" / "logo_horizons.png").is_file():
        raise SystemExit("Le système d'identité visuelle HORIZONS ou son logo est absent.")
    for path in (ROOT / "cogs").glob("*.py"):
        if path.name != "embed_theme.py" and "discord.Embed(" in path.read_text(encoding="utf-8"):
            raise SystemExit(f"Embed non centralisé détecté dans {path.name}.")

    if not (ROOT / ".env.example").is_file():
        raise SystemExit("Le modèle .env.example est absent.")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    required_settings = {
        "TEMP_VOICE_TRIGGER_ID", "TEMP_VOICE_CATEGORY_ID",
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
    rank_mapping = json.loads(rank_line.split("=", 1)[1])
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
    print("Syntaxe, données JSON, noms de commandes et schéma SQLite vérifiés.")
    print("Ce contrôle ne se connecte pas à Discord et ne remplace pas un test avec le bot en ligne.")


if __name__ == "__main__":
    main()

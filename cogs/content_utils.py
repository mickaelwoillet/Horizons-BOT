"""Utilitaires communs pour les blagues et les devinettes."""
from __future__ import annotations
import json
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BLAGUES = DATA / "blagues"
STATE = DATA / "content_history.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def categories() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    if not BLAGUES.exists():
        return result
    for path in sorted(BLAGUES.glob("*.json")):
        # Ce fichier contient des devinettes structurées question/réponse,
        # pas des blagues textuelles à afficher dans /blague.
        if path.stem == "devinettes":
            continue
        raw = load_json(path, [])
        # Les banques historiques utilisent { "categorie": [ ... ] }.
        # On accepte aussi les listes simples pour faciliter les ajouts futurs.
        if isinstance(raw, dict):
            values = raw.get(path.stem, [])
            if not values and len(raw) == 1:
                values = next(iter(raw.values()))
        elif isinstance(raw, list):
            values = raw
        else:
            values = []
        jokes = [x.strip() for x in values if isinstance(x, str) and x.strip()] if isinstance(values, list) else []
        if jokes:
            result[path.stem] = jokes
    return result


def pick_joke(category: str | None = None) -> tuple[str, str]:
    all_categories = categories()
    if not all_categories:
        return "quotidien", "Pourquoi les plongeurs plongent-ils toujours en arrière ? Parce que sinon ils tombent dans le bateau !"
    if category and category in all_categories:
        choices = {category: all_categories[category]}
    else:
        choices = all_categories
    state = load_json(STATE, {"jokes": [], "riddles": []})
    history = set(state.get("jokes", []))
    candidates = [(cat, joke) for cat, jokes in choices.items() for joke in jokes if f"{cat}|{joke}" not in history]
    if not candidates:
        # Toutes les blagues ont été vues : on repart sur un nouveau cycle.
        state["jokes"] = []
        candidates = [(cat, joke) for cat, jokes in choices.items() for joke in jokes]
    cat, joke = random.choice(candidates)
    state.setdefault("jokes", []).append(f"{cat}|{joke}")
    state["jokes"] = state["jokes"][-500:]
    save_json(STATE, state)
    return cat, joke


def riddles() -> list[dict[str, str]]:
    raw = load_json(DATA / "devinettes.json", [])
    result = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                q = str(item.get("question", "")).strip()
                a = str(item.get("reponse", item.get("réponse", ""))).strip()
                if q and a:
                    result.append({"question": q, "reponse": a})
    return result


def pick_riddle() -> dict[str, str] | None:
    items = riddles()
    if not items:
        return None
    state = load_json(STATE, {"jokes": [], "riddles": []})
    seen = set(state.get("riddles", []))
    remaining = [i for i, item in enumerate(items) if str(i) not in seen]
    if not remaining:
        seen.clear()
        remaining = list(range(len(items)))
    index = random.choice(remaining)
    seen.add(str(index))
    state["riddles"] = sorted(seen, key=lambda x: int(x))[-500:]
    save_json(STATE, state)
    return items[index]

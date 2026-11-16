"""Audit statique de l’aventure HORIZONS (aucune donnée utilisateur modifiée)."""
import json
from pathlib import Path

def audit(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    rooms=data["rooms"]
    assert len(rooms)==13, "Nombre de salles inattendu"
    assert sum(len(r["puzzles"]) for r in rooms)==87, "Nombre d'énigmes inattendu"
    all_ids={r["id"] for r in rooms}
    produced=set()
    for r in rooms:
        for p in r["puzzles"]: produced.update(p.get("rewards",[]))
        for h in r.get("hotspots",[]): produced.update(h.get("rewards",[]))
        for recipe in r.get("recipes",[]): produced.add(recipe["result"])
    errors=[]
    for r in rooms:
        ids={p["id"] for p in r["puzzles"]}
        if len(ids)!=len(r["puzzles"]): errors.append(f"{r['id']}: doublon d'énigme")
        for p in r["puzzles"]:
            if not p.get("answers"): errors.append(f"{p['id']}: réponses absentes")
            if not p.get("hints"): errors.append(f"{p['id']}: indices absents")
            if not set(p.get("requires_solved",[])).issubset(ids-{p["id"]}): errors.append(f"{p['id']}: prérequis incohérents")
            if p.get("next_room") and p["next_room"] not in all_ids: errors.append(f"{p['id']}: destination absente")
            for item in p.get("requires",[]):
                if item not in produced: errors.append(f"{p['id']}: objet inconnu {item}")
        for rec in r.get("recipes",[]):
            for item in rec["ingredients"]:
                if item not in produced: errors.append(f"{r['id']}: ingrédient inconnu {item}")
    if errors: raise AssertionError("\n".join(errors))
    print(f"Audit statique OK : {len(rooms)} salles, 87 énigmes, {len(produced)} objets possibles")

if __name__=="__main__":
    audit(Path(__file__).resolve().parents[1]/"escape_content"/"fractures.json")

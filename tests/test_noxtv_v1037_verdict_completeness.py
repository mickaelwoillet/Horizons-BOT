import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_every_scene_has_three_specific_verdicts():
    tree = ast.parse((ROOT / "cogs/nox_tv.py").read_text(encoding="utf-8"))
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCENE_VERDICTS" for t in node.targets))
    verdicts = ast.literal_eval(assignment.value)
    catalogue = json.loads((ROOT / "data/nox_tv/catalogue.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in catalogue}
    assert len(ids) == 30
    assert ids <= verdicts.keys(), sorted(ids - verdicts.keys())
    for scene_id in ids:
        outcomes = verdicts[scene_id]
        assert len(outcomes) == 3, scene_id
        assert all(isinstance(t, str) and t.strip() for t in outcomes), scene_id

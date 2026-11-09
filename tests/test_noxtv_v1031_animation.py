import json
from pathlib import Path
from PIL import Image, ImageChops
ROOT=Path(__file__).resolve().parents[1]/"data/nox_tv"
def test_animated_duck_and_hungry_nox():
    for name in ("canard_matraque_anime.gif", "nox_faim_anime.gif"):
        with Image.open(ROOT/name) as im:
            assert im.n_frames >= 8
            im.seek(0); first=im.convert("RGB")
            im.seek(im.n_frames//2); middle=im.convert("RGB")
            assert ImageChops.difference(first,middle).getbbox()
def test_catalogue_unique_files_exist():
    entries=json.loads((ROOT/"catalogue.json").read_text(encoding="utf-8"))
    ids=[e["id"] for e in entries]
    assert len(ids)==len(set(ids)) and len(ids)>=25
    assert all((ROOT/e["file"]).is_file() for e in entries)
    assert next(e for e in entries if e["id"]=="nox_faim_anime")["kind"]=="nox"

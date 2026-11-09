from pathlib import Path
import ast
import json

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "cogs/nox_tv.py").read_text(encoding="utf-8")

def test_source_compiles():
    ast.parse(SRC)

def test_media_path_guard():
    assert "asset.parent != root" in SRC
    assert "not asset.is_file()" in SRC

def test_chronicle_permissions_guard():
    assert "channel.guild.id != guild.id" in SRC
    assert "perms.embed_links" in SRC

def test_catalog_assets_exist():
    items=json.loads((ROOT / "data/nox_tv/catalogue.json").read_text(encoding="utf-8"))
    assert len(items) >= 16
    for item in items:
        assert (ROOT / "data/nox_tv" / item["file"]).is_file()

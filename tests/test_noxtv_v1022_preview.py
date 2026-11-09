from pathlib import Path
import ast

SOURCE = Path(__file__).resolve().parents[1] / "cogs" / "nox_tv.py"

def test_preview_does_not_reference_publish_locals():
    module = ast.parse(SOURCE.read_text(encoding="utf-8"))
    cog = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "NoxTV")
    method = next(n for n in cog.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "apercu")
    text = ast.get_source_segment(SOURCE.read_text(encoding="utf-8"), method)
    assert "self._release_reservation(guild.id, day, manual)" not in text
    assert "await i.followup.send('Média manquant ou chemin non autorisé.'" in text
    assert "except (discord.Forbidden, discord.HTTPException, OSError)" in text

def test_verdict_does_not_fallback_to_arbitrary_channel():
    source = SOURCE.read_text(encoding="utf-8")
    assert "destination_id=chronicle_channel() or channel_id" not in source
    assert "destination_id=chronicle_channel()" in source

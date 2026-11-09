"""Identité visuelle centralisée des embeds HORIZONS — noir & or."""
from __future__ import annotations

from typing import Any
import asyncio
import discord

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "data" / "assets"
LOGO_PATH = ASSET_DIR / "logo_horizons.png"
LOGO_STATE_PATH = ASSET_DIR / "logo_url.json"

# Palette volontairement sobre : l'or reste la signature, les autres teintes
# sont désaturées et réservées aux statuts (succès, alerte, information).
GOLD = discord.Color.from_rgb(198, 153, 63)
PALETTE = {
    "gold": discord.Color.from_rgb(198, 153, 63),
    "info": discord.Color.from_rgb(105, 123, 143),
    "success": discord.Color.from_rgb(112, 137, 103),
    "warning": discord.Color.from_rgb(181, 125, 57),
    "danger": discord.Color.from_rgb(166, 83, 75),
    "community": discord.Color.from_rgb(158, 125, 91),
    "neutral": discord.Color.from_rgb(76, 76, 76),
}
_logo_url: str | None = None
_logo_ready = asyncio.Event()

def begin_logo_loading() -> None:
    """Réinitialise la barrière avant une nouvelle vérification du dépôt Discord."""
    _logo_ready.clear()

def set_logo_url(url: str | None) -> None:
    """Définit l'URL CDN Discord utilisée comme miniature officielle."""
    global _logo_url
    _logo_url = url if isinstance(url, str) and url.startswith(("https://", "http://")) else None
    # Réveille les publications différées, même si le dépôt du logo a échoué.
    _logo_ready.set()

async def wait_for_logo_ready() -> str | None:
    """Attend la tentative de chargement du logo avant de construire un embed.

    Le délai évite de bloquer le bot si Discord refuse temporairement le dépôt.
    """
    try:
        await asyncio.wait_for(_logo_ready.wait(), timeout=20)
    except asyncio.TimeoutError:
        return None
    return _logo_url

def get_logo_url() -> str | None:
    return _logo_url

def _semantic_color(value: Any) -> discord.Color:
    """La signature de marque reste or ; les statuts peuvent être indiqués dans le texte."""
    return GOLD

def horizons_embed(*args: Any, **kwargs: Any) -> discord.Embed:
    """Construit un embed harmonisé : accent or, logo en haut à droite, signature."""
    kwargs["color"] = GOLD
    embed = discord.Embed(*args, **kwargs)
    if _logo_url and not embed.thumbnail.url:
        # Miniature officielle en haut à droite : ne remplace jamais l'image du contenu.
        embed.set_thumbnail(url=_logo_url)
    footer_text = embed.footer.text or ""
    if "horizons" not in footer_text.lower():
        footer_text = f"{footer_text} • HORIZONS" if footer_text else "HORIZONS • Nos différences nous rapprochent"
    elif "nos différences nous rapprochent" not in footer_text.lower():
        footer_text = f"{footer_text} • Nos différences nous rapprochent"
    # Ne transmettre aucun icon_url lorsqu’il n’existe pas : discord.py peut
    # sérialiser la valeur sentinelle MISSING comme une URL invalide.
    embed.set_footer(text=footer_text)
    return embed

"""Sauvegarde SQLite et surveillance discrète du fonctionnement HORIZONS.

Aucune commande slash, aucun nouveau salon. Les sauvegardes sont locales :
une copie hors machine reste nécessaire pour résister à une panne du serveur.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import logging
import json
import os
from pathlib import Path
import sqlite3

import discord
from discord.ext import commands, tasks

from config import DATA_DIR, ADMIN_BOT_LOG_CHANNEL_ID
from cogs.storage import DB_PATH

log = logging.getLogger(__name__)
BACKUP_DIR = DATA_DIR / "backups"
RETENTION_DAYS = 14
CHECK_INTERVAL_HOURS = 1
BACKUP_INTERVAL_HOURS = 24
STATUS_PATH = DATA_DIR / "backup_status.json"


def sqlite_backup(source: Path = DB_PATH, destination_dir: Path = BACKUP_DIR,
                  keep_days: int = RETENTION_DAYS) -> Path:
    """Cohérente avec WAL : sqlite3.backup, jamais une copie brute du .sqlite3."""
    if not source.is_file():
        raise FileNotFoundError(f"Base introuvable : {source}")
    destination_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    target = destination_dir / f"{source.stem}-{now:%Y%m%d-%H%M%S-%f}.sqlite3"
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=15) as origin:
            with sqlite3.connect(target, timeout=15) as copy:
                origin.backup(copy, pages=100, sleep=0.1)
                check = copy.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError("Échec de la vérification SQLite de la sauvegarde")
        target.chmod(0o600)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    # Conserver au moins la sauvegarde que l'on vient de produire.
    cutoff = now - timedelta(days=keep_days)
    for old in destination_dir.glob(f"{source.stem}-*.sqlite3"):
        if old == target:
            continue
        try:
            if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
                old.unlink()
        except OSError:
            log.exception("Impossible de purger une ancienne sauvegarde : %s", old)
    return target



def backup_all_databases(data_dir: Path = DATA_DIR, destination_dir: Path = BACKUP_DIR,
                         keep_days: int = RETENTION_DAYS) -> dict[str, str]:
    """Sauvegarde chaque base active avec l'API SQLite, sans copier les WAL bruts.

    Une erreur sur une base ne masque pas les autres : le résultat détaillé est
    enregistré localement pour le diagnostic staff.
    """
    destination_dir.mkdir(parents=True, exist_ok=True)
    databases = sorted(p for p in data_dir.glob("*.sqlite3") if p.is_file())
    results: dict[str, str] = {}
    for source in databases:
        try:
            target = sqlite_backup(source, destination_dir, keep_days)
            # Vérification indépendante du fichier produit.
            healthy, reason = database_health(target)
            if not healthy:
                target.unlink(missing_ok=True)
                raise RuntimeError(reason)
            results[source.name] = "ok"
        except (OSError, sqlite3.Error, RuntimeError) as exc:
            log.exception("Sauvegarde impossible : %s", source.name)
            results[source.name] = f"erreur : {type(exc).__name__}"
    if not databases:
        results["_global"] = "erreur : aucune base SQLite détectée"
    status = {"updated_at": datetime.now(timezone.utc).isoformat(), "databases": results}
    tmp = STATUS_PATH.with_name(STATUS_PATH.name + ".tmp") if data_dir == DATA_DIR else data_dir / "backup_status.json.tmp"
    dest = STATUS_PATH if data_dir == DATA_DIR else data_dir / "backup_status.json"
    try:
        tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, dest)
    except OSError:
        log.exception("Impossible de consigner le diagnostic des sauvegardes")
        tmp.unlink(missing_ok=True)
    return results


def backup_diagnostic(data_dir: Path = DATA_DIR) -> dict:
    """Lecture seule du dernier état de sauvegarde (aucun secret exposé)."""
    path = data_dir / "backup_status.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("databases"), dict):
            return value
    except (OSError, ValueError):
        pass
    return {"updated_at": None, "databases": {}}


def database_health(source: Path = DB_PATH) -> tuple[bool, str]:
    if not source.exists():
        return False, "Base SQLite absente"
    try:
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=5) as conn:
            result = conn.execute("PRAGMA quick_check").fetchone()
        return (True, "Base SQLite accessible") if result and result[0] == "ok" else (False, "Vérification SQLite en échec")
    except (sqlite3.Error, OSError) as exc:
        return False, f"Base SQLite indisponible ({type(exc).__name__})"


class Continuity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_backup: datetime | None = None
        self.last_alert: dict[str, datetime] = {}
        self.last_status: dict[str, bool] = {}

    async def cog_load(self):
        self.monitor.start()

    def cog_unload(self):
        self.monitor.cancel()

    async def alert(self, key: str, message: str):
        now = datetime.now(timezone.utc)
        previous = self.last_alert.get(key)
        if previous and now - previous < timedelta(hours=12):
            return
        channel = self.bot.get_channel(ADMIN_BOT_LOG_CHANNEL_ID) if ADMIN_BOT_LOG_CHANNEL_ID else None
        if not isinstance(channel, discord.TextChannel):
            log.warning("Alerte technique non transmise sur Discord : %s", message)
            return
        try:
            await channel.send(
                "⚠️ **HORIZONS — Suivi technique**\\n" + message,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            self.last_alert[key] = now
        except (discord.Forbidden, discord.HTTPException):
            log.exception("Échec de transmission de l'alerte technique : %s", key)

    @tasks.loop(hours=CHECK_INTERVAL_HOURS)
    async def monitor(self):
        now = datetime.now(timezone.utc)
        if self.last_backup is None or now - self.last_backup >= timedelta(hours=BACKUP_INTERVAL_HOURS):
            try:
                results = await asyncio.to_thread(backup_all_databases)
                if not results or any(value != "ok" for value in results.values()):
                    raise RuntimeError("Une ou plusieurs sauvegardes sont en échec")
                self.last_backup = now
                log.info("Sauvegardes HORIZONS vérifiées : %s bases", len(results))
            except (OSError, sqlite3.Error, RuntimeError) as exc:
                log.exception("Sauvegarde automatique HORIZONS en échec")
                await self.alert("backup", f"Sauvegarde SQLite en échec ({type(exc).__name__}). Vérifier les journaux et l'espace disque.")

        healthy, detail = await asyncio.to_thread(database_health)
        if not healthy:
            log.error("Surveillance HORIZONS : %s", detail)
            await self.alert("database", detail)
        self.last_status["database"] = healthy

        # Vérifier les extensions critiques déjà chargées au démarrage.
        for extension in ("cogs.today_hub", "cogs.birthdays", "cogs.celestial_treasures", "cogs.staff_dashboard"):
            ok = extension in self.bot.extensions
            if not ok:
                await self.alert("extension:" + extension, f"Extension importante non chargée : `{extension}`.")
            self.last_status[extension] = ok

    @monitor.before_loop
    async def before_monitor(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Continuity(bot))

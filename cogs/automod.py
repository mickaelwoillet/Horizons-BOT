"""AutoMod V2 HORIZONS : filtres, alertes sensibles, infractions et sanctions."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from discord.ext import commands, tasks

from config import (
    AUTOMOD_LOG_CHANNEL_ID, INFRACTION_LOG_CHANNEL_ID, SENSITIVE_LOG_CHANNEL_ID,
    ADMIN_BOT_LOG_CHANNEL_ID, AUTO_MOD_ENABLED, DATA_DIR, STAFF_ROLE_ID, TICKET_CATEGORY_ID,
)
from cogs.embed_theme import horizons_embed
from cogs.storage import db

log = logging.getLogger("horizons.automod")
CONFIG_PATH = DATA_DIR / "automod_v2.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "automod_v2_config.json"
SENSITIVE_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "automod_sensitive_terms.json"

DEFAULT_CONFIG = {
    "version": 2, "enabled": True, "delete_messages": True, "warning_delete_delay": 8,
    "exempt_role_ids": [], "exempt_channel_ids": [],
    "discord_invites": {"enabled": True, "patterns": ["discord.gg/", "discord.com/invite/", "discordapp.com/invite/"], "reason": "Publicité / Invitation Discord"},
    "caps": {"enabled": True, "min_chars": 15, "max_ratio": 0.7, "min_uppercase": 10, "reason": "Majuscules excessives"},
    "emojis": {"enabled": True, "min_emojis": 10, "max_ratio": 0.5, "reason": "Émojis excessifs"},
    "mentions": {"enabled": True, "max_mentions_message": 5, "max_mentions_30s": 5, "window_seconds": 30, "reason": "Mentions excessives"},
    "spam": {"enabled": True, "max_messages": 15, "window_seconds": 30, "reason": "Spam"},
    "repetition": {"enabled": True, "max_repeated": 5, "window_seconds": 30, "reason": "Répétition de message"},
    "forbidden_pings": {"enabled": False, "protected_user_ids": [], "protected_role_ids": [], "reason": "Ping interdit"},
    "forbidden_words": {"enabled": True, "words": [], "reason": "Vocabulaire injurieux interdit"},
    "sensitive_alerts": {"enabled": True, "terms_file": "data/automod_sensitive_terms.json", "ignore_channels": []},
    "predefined_sanctions": {},
    "escalation": [
        {"count": 3, "window_seconds": 172800, "type": "mute", "duration_seconds": 3600, "label": "3 infractions en 48 h"},
        {"count": 5, "window_seconds": 172800, "type": "mute", "duration_seconds": 86400, "label": "5 infractions en 48 h"},
        {"count": 7, "window_seconds": 259200, "type": "tempban", "duration_seconds": 259200, "label": "7 infractions en 72 h"},
        {"count": 10, "window_seconds": 604800, "type": "tempban", "duration_seconds": 604800, "label": "10 infractions en 7 jours"},
    ],
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_json(path: Path, fallback):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value
    except (OSError, json.JSONDecodeError):
        return fallback


def ensure_config() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        seed = load_json(DEFAULT_CONFIG_PATH, DEFAULT_CONFIG)
        CONFIG_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8")
    loaded = load_json(CONFIG_PATH, {})
    # Merge nested settings without overwriting the user's existing values.
    merged = dict(DEFAULT_CONFIG)
    if isinstance(loaded, dict):
        merged.update(loaded)
        for key, defaults in DEFAULT_CONFIG.items():
            if isinstance(defaults, dict):
                nested = dict(defaults)
                if isinstance(loaded.get(key), dict):
                    nested.update(loaded[key])
                merged[key] = nested
    if merged.get("version", 0) < 2:
        merged["version"] = 2
    CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def read_sensitive_terms(cfg: dict) -> list[str]:
    relative = cfg.get("sensitive_alerts", {}).get("terms_file", "data/automod_sensitive_terms.json")
    path = Path(relative)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    raw = load_json(path, {"terms": []})
    terms = raw.get("terms", []) if isinstance(raw, dict) else []
    return [str(x).strip() for x in terms if str(x).strip()]


class AutoModeration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cfg = ensure_config()
        self.messages = defaultdict(deque)
        self.mentions = defaultdict(deque)
        self.repeats = defaultdict(deque)
        self.sensitive_terms = read_sensitive_terms(self.cfg)
        self.sensitive_last_alert: dict[tuple[int, int], float] = {}
        self.expire_tempbans.start()

    def cog_unload(self):
        self.expire_tempbans.cancel()

    def is_ticket_channel(self, channel: discord.abc.GuildChannel) -> bool:
        name = str(getattr(channel, "name", "")).lower()
        if name.startswith(("ticket-", "ferme-ticket-")):
            return True
        return bool(TICKET_CATEGORY_ID and getattr(channel, "category_id", None) == TICKET_CATEGORY_ID)

    def exempt(self, member: discord.Member, channel: discord.abc.GuildChannel) -> bool:
        if member.guild_permissions.administrator or member.id == member.guild.owner_id:
            return True
        role_ids = {int(x) for x in self.cfg.get("exempt_role_ids", []) if str(x).isdigit()}
        if STAFF_ROLE_ID:
            role_ids.add(int(STAFF_ROLE_ID))
        if any(role.id in role_ids for role in member.roles):
            return True
        channel_ids = {int(x) for x in self.cfg.get("exempt_channel_ids", []) if str(x).isdigit()}
        return channel.id in channel_ids

    async def send_log(self, guild: discord.Guild, channel_id: int | None, title: str, description: str, color=discord.Color.orange()):
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.HTTPException, discord.Forbidden):
                return
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            try:
                await channel.send(embed=horizons_embed(title=title, description=description[:3900], color=color, timestamp=now_utc()), allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                log.exception("Échec d'envoi du log AutoMod dans %s", channel_id)

    async def admin_error(self, guild: discord.Guild, detail: str):
        await self.send_log(guild, ADMIN_BOT_LOG_CHANNEL_ID, "⚙️ AutoMod — anomalie technique", detail, discord.Color.red())

    def detect(self, message: discord.Message, include_behavioral: bool = True) -> list[str]:
        cfg = self.cfg
        content = message.content or ""
        lower = content.lower()
        normalized = f" {normalize(content)} "
        found: list[str] = []
        inv = cfg.get("discord_invites", {})
        if inv.get("enabled") and any(str(p).lower() in lower for p in inv.get("patterns", [])):
            found.append(inv.get("reason", "Publicité / Invitation Discord"))
        forbidden = cfg.get("forbidden_words", {})
        if forbidden.get("enabled"):
            words = [normalize(w) for w in forbidden.get("words", []) if normalize(w)]
            if any(f" {w} " in normalized for w in words):
                found.append(forbidden.get("reason", "Vocabulaire injurieux interdit"))
        caps = cfg.get("caps", {})
        letters = [c for c in content if c.isalpha()]
        upper = sum(c.isupper() for c in letters)
        if caps.get("enabled") and len(letters) >= int(caps.get("min_chars", 15)) and upper >= int(caps.get("min_uppercase", 10)) and upper / max(1, len(letters)) >= float(caps.get("max_ratio", .7)):
            found.append(caps.get("reason", "Majuscules excessives"))
        emojis = cfg.get("emojis", {})
        emoji_count = sum(ord(c) >= 0x1F000 for c in content)
        units = max(1, len(content.replace(" ", "")))
        if emojis.get("enabled") and emoji_count >= int(emojis.get("min_emojis", 10)) and emoji_count / units >= float(emojis.get("max_ratio", .5)):
            found.append(emojis.get("reason", "Émojis excessifs"))
        mentions_cfg = cfg.get("mentions", {})
        mention_count = len(message.mentions) + len(message.role_mentions)
        if message.mention_everyone:
            found.append("Ping interdit")
        elif mentions_cfg.get("enabled") and mention_count >= int(mentions_cfg.get("max_mentions_message", 5)):
            found.append(mentions_cfg.get("reason", "Mentions excessives"))
        if include_behavioral and mentions_cfg.get("enabled") and mention_count:
            q = self.mentions[(message.guild.id, message.author.id)]
            for _ in range(mention_count): q.append(message.created_at.timestamp())
            window = int(mentions_cfg.get("window_seconds", 30))
            while q and message.created_at.timestamp() - q[0] > window: q.popleft()
            if len(q) >= int(mentions_cfg.get("max_mentions_30s", 5)):
                found.append(mentions_cfg.get("reason", "Mentions excessives"))
        ping_cfg = cfg.get("forbidden_pings", {})
        if ping_cfg.get("enabled"):
            users = {int(x) for x in ping_cfg.get("protected_user_ids", []) if str(x).isdigit()}
            roles = {int(x) for x in ping_cfg.get("protected_role_ids", []) if str(x).isdigit()}
            if any(u.id in users for u in message.mentions) or any(r.id in roles for r in message.role_mentions):
                found.append(ping_cfg.get("reason", "Ping interdit"))
        now = message.created_at.timestamp()
        spam = cfg.get("spam", {})
        if include_behavioral and spam.get("enabled"):
            q = self.messages[(message.guild.id, message.author.id)]
            q.append(now)
            window = int(spam.get("window_seconds", 30))
            while q and now - q[0] > window: q.popleft()
            if len(q) > int(spam.get("max_messages", 15)):
                found.append(spam.get("reason", "Spam"))
        rep = cfg.get("repetition", {})
        normalized_repeat = normalize(content)
        if include_behavioral and rep.get("enabled") and len(normalized_repeat) >= 8:
            q = self.repeats[(message.guild.id, message.author.id)]
            q.append((now, normalized_repeat))
            window = int(rep.get("window_seconds", 30))
            while q and now - q[0][0] > window: q.popleft()
            if sum(1 for _, txt in q if txt == normalized_repeat) >= int(rep.get("max_repeated", 5)):
                found.append(rep.get("reason", "Répétition de message"))
        # Keep only one infraction per message, even if several filters match.
        return list(dict.fromkeys(found))

    def sensitive_matches(self, content: str) -> list[str]:
        normalized = f" {normalize(content)} "
        if not normalized.strip(): return []
        matches = []
        for term in self.sensitive_terms:
            needle = normalize(term)
            if needle and f" {needle} " in normalized:
                matches.append(term)
        return matches[:12]

    async def log_sensitive(self, message: discord.Message, matches: list[str]):
        if message.channel.id in {int(x) for x in self.cfg.get("sensitive_alerts", {}).get("ignore_channels", []) if str(x).isdigit()}:
            return
        cooldown_key = (message.guild.id, message.author.id)
        now_ts = now_utc().timestamp()
        if now_ts - self.sensitive_last_alert.get(cooldown_key, 0) < 600:
            return
        self.sensitive_last_alert[cooldown_key] = now_ts
        excerpt = discord.utils.escape_markdown((message.content or "[message sans texte]")[:1400])
        description = (f"**Auteur :** {message.author.mention} (`{message.author.id}`)\n"
                       f"**Salon :** {message.channel.mention}\n**Termes repérés :** {', '.join(matches)}\n\n"
                       f"**Extrait :**\n{excerpt}\n\n"
                       "Signalement automatique à examiner avec discernement. Aucun effacement ni sanction n'a été appliqué par cette détection.")
        await self.send_log(message.guild, SENSITIVE_LOG_CHANNEL_ID, "🧭 Message nécessitant une attention", description, discord.Color.gold())

    async def record_infraction(self, guild: discord.Guild, member: discord.Member, reason: str, source: str = "automod", channel_id: int | None = None, message_id: int | None = None):
        stamp = now_utc().isoformat()
        with db() as conn:
            cur = conn.execute("INSERT INTO automod_infractions(guild_id,user_id,channel_id,message_id,reason,source,created_at) VALUES(?,?,?,?,?,?,?)",
                               (guild.id, member.id, channel_id, message_id, reason, source, stamp))
            infraction_id = cur.lastrowid
            rules = sorted(self.cfg.get("escalation", []), key=lambda x: int(x.get("count", 0)))
            triggered = []
            for rule in rules:
                count = int(rule.get("count", 0)); window = int(rule.get("window_seconds", 0))
                if count <= 0 or window <= 0: continue
                since = (now_utc() - timedelta(seconds=window)).isoformat()
                total = conn.execute("SELECT COUNT(*) FROM automod_infractions WHERE guild_id=? AND user_id=? AND created_at>=?", (guild.id, member.id, since)).fetchone()[0]
                if total == count:
                    triggered.append(rule)
        # If several thresholds are crossed together after a config edit, use the highest one only.
        return infraction_id, (max(triggered, key=lambda x: int(x.get("count", 0))) if triggered else None)

    async def register_manual_infraction(self, guild: discord.Guild, member: discord.Member, reason: str, moderator: discord.Member):
        infraction_id, escalation = await self.record_infraction(guild, member, reason, source="manual")
        await self.send_log(guild, INFRACTION_LOG_CHANNEL_ID, "⚠️ Avertissement manuel", f"**Membre :** {member.mention} (`{member.id}`)\n**Modérateur :** {moderator.mention}\n**Motif :** {reason}\n**Référence :** `#{infraction_id}`", discord.Color.orange())
        if escalation:
            action = str(escalation.get("type", "mute"))
            label = f"Escalade automatique : {escalation.get('label', escalation.get('count'))}"
            status = await self.apply_action(guild, member, action, label, int(escalation.get("duration_seconds", 0)), "escalation", infraction_id)
            await self.send_log(guild, INFRACTION_LOG_CHANNEL_ID, "⚖️ Seuil d'escalade atteint", f"{member.mention}\n**Seuil :** {label}\n**Action :** {action} ({status})", discord.Color.red())

    async def apply_action(self, guild: discord.Guild, member: discord.Member, action: str, reason: str, duration: int, source: str, infraction_id: int | None = None):
        action = (action or "warn").lower()
        status = "applied"
        expiry = None
        try:
            if action == "warn":
                pass
            elif action == "mute":
                if duration <= 0: duration = 3600
                await member.timeout(now_utc() + timedelta(seconds=duration), reason=f"HORIZONS AutoMod : {reason}")
                expiry = (now_utc() + timedelta(seconds=duration)).isoformat()
            elif action == "tempban":
                if duration <= 0: duration = 86400
                if not hasattr(self.bot, "moderation_ban_ids"): self.bot.moderation_ban_ids = set()
                self.bot.moderation_ban_ids.add(member.id)
                await guild.ban(member, reason=f"HORIZONS AutoMod : {reason}", delete_message_seconds=0)
                expiry = (now_utc() + timedelta(seconds=duration)).isoformat()
            elif action == "kick":
                await member.kick(reason=f"HORIZONS AutoMod : {reason}")
            elif action == "ban":
                if not hasattr(self.bot, "moderation_ban_ids"): self.bot.moderation_ban_ids = set()
                self.bot.moderation_ban_ids.add(member.id)
                await guild.ban(member, reason=f"HORIZONS AutoMod : {reason}", delete_message_seconds=0)
            else:
                action = "warn"
        except (discord.Forbidden, discord.HTTPException) as exc:
            status = "failed"
            if action in {"ban", "tempban"}:
                getattr(self.bot, "moderation_ban_ids", set()).discard(member.id)
            await self.admin_error(guild, f"Action **{action}** impossible pour `{member.id}`. Motif : {reason}\nErreur : `{type(exc).__name__}: {exc}`")
        with db() as conn:
            conn.execute("INSERT INTO automod_sanctions(guild_id,user_id,infraction_id,action,reason,duration_seconds,source,status,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (guild.id, member.id, infraction_id, action, reason, duration, source, status, now_utc().isoformat(), expiry))
            if status == "applied" and action == "tempban" and expiry:
                conn.execute("INSERT INTO automod_tempbans(guild_id,user_id,reason,expires_at,status) VALUES(?,?,?,?, 'active') ON CONFLICT(guild_id,user_id) DO UPDATE SET reason=excluded.reason, expires_at=excluded.expires_at, status='active'",
                             (guild.id, member.id, reason, expiry))
        return status

    async def handle_violation(self, message: discord.Message, reason: str):
        # Les autres cogs de progression consultent ce marqueur avant de comptabiliser le message.
        if not hasattr(self.bot, "automod_blocked_message_ids"):
            self.bot.automod_blocked_message_ids = set()
        self.bot.automod_blocked_message_ids.add(message.id)
        if len(self.bot.automod_blocked_message_ids) > 5000:
            for _ in range(1000):
                self.bot.automod_blocked_message_ids.pop()
        deleted = False
        if self.cfg.get("delete_messages", True):
            try:
                if not hasattr(self.bot, "automod_deleted_ids"):
                    self.bot.automod_deleted_ids = set()
                self.bot.automod_deleted_ids.add(message.id)
                await message.delete(reason=f"HORIZONS AutoMod V2 : {reason}")
                deleted = True
            except (discord.Forbidden, discord.HTTPException) as exc:
                getattr(self.bot, "automod_deleted_ids", set()).discard(message.id)
                await self.admin_error(message.guild, f"Impossible de supprimer un message AutoMod dans {message.channel.mention}. Vérifier **Gérer les messages**.\nErreur : `{type(exc).__name__}`")
        if deleted:
            try:
                warning = await message.channel.send(f"⚠️ {message.author.mention}, ton message a été retiré : **{reason}**. Merci de respecter le cadre bienveillant de HORIZONS.", allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
                delay = max(3, min(30, int(self.cfg.get("warning_delete_delay", 8))))
                await warning.delete(delay=delay)
            except discord.HTTPException:
                pass
        member = message.author
        infraction_id, escalation = await self.record_infraction(message.guild, member, reason, channel_id=message.channel.id, message_id=message.id)
        sanction = self.cfg.get("predefined_sanctions", {}).get(reason, {"type": "warn", "duration_seconds": 0})
        action = sanction.get("type", "warn")
        status = await self.apply_action(message.guild, member, action, reason, int(sanction.get("duration_seconds", 0)), "automod", infraction_id)
        details = (f"**Membre :** {member.mention} (`{member.id}`)\n**Salon :** {message.channel.mention}\n"
                   f"**Motif :** {reason}\n**Action :** {action} ({status})\n**Infraction :** `#{infraction_id}`\n"
                   f"**Message supprimé :** {'oui' if deleted else 'non / échec'}")
        await self.send_log(message.guild, AUTOMOD_LOG_CHANNEL_ID, "🛡️ Détection AutoMod V2", details, discord.Color.orange())
        await self.send_log(message.guild, INFRACTION_LOG_CHANNEL_ID, "⚠️ Nouvelle infraction", details, discord.Color.orange())
        if escalation:
            escal_reason = f"Escalade automatique : {escalation.get('label', escalation.get('count'))}"
            escal_action = str(escalation.get("type", "mute"))
            escal_status = await self.apply_action(message.guild, member, escal_action, escal_reason, int(escalation.get("duration_seconds", 0)), "escalation", infraction_id)
            await self.send_log(message.guild, INFRACTION_LOG_CHANNEL_ID, "⚖️ Seuil d'escalade atteint", f"{member.mention}\n**Seuil :** {escal_reason}\n**Action :** {escal_action} ({escal_status})", discord.Color.red())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not AUTO_MOD_ENABLED or not self.cfg.get("enabled", True) or not message.guild or not isinstance(message.author, discord.Member) or message.author.bot:
            return
        if self.exempt(message.author, message.channel) or self.is_ticket_channel(message.channel):
            return
        reasons = self.detect(message)
        if reasons:
            await self.handle_violation(message, reasons[0])
            return
        if self.cfg.get("sensitive_alerts", {}).get("enabled", True):
            matches = self.sensitive_matches(message.content)
            if matches:
                await self.log_sensitive(message, matches)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild or not isinstance(after.author, discord.Member) or after.author.bot or before.content == after.content:
            return
        if not AUTO_MOD_ENABLED or not self.cfg.get("enabled", True) or self.exempt(after.author, after.channel) or self.is_ticket_channel(after.channel):
            return
        reasons = self.detect(after, include_behavioral=False)
        if reasons:
            await self.handle_violation(after, reasons[0])
            return
        if self.cfg.get("sensitive_alerts", {}).get("enabled", True):
            matches = self.sensitive_matches(after.content)
            if matches:
                await self.log_sensitive(after, matches)

    @tasks.loop(minutes=1)
    async def expire_tempbans(self):
        await self.bot.wait_until_ready()
        with db() as conn:
            rows = conn.execute("SELECT guild_id,user_id,reason,expires_at FROM automod_tempbans WHERE status='active' AND expires_at<=?", (now_utc().isoformat(),)).fetchall()
        for row in rows:
            guild = self.bot.get_guild(int(row["guild_id"]))
            if not guild: continue
            try:
                user = await self.bot.fetch_user(int(row["user_id"]))
                try:
                    await guild.fetch_ban(user)
                    if not hasattr(self.bot, "moderation_unban_ids"): self.bot.moderation_unban_ids = set()
                    self.bot.moderation_unban_ids.add(user.id)
                    await guild.unban(user, reason="Fin de bannissement temporaire HORIZONS")
                except discord.NotFound:
                    pass
                with db() as conn:
                    conn.execute("UPDATE automod_tempbans SET status='expired' WHERE guild_id=? AND user_id=? AND status='active'", (guild.id, user.id))
                await self.send_log(guild, INFRACTION_LOG_CHANNEL_ID, "✅ Fin de bannissement temporaire", f"Utilisateur : `{user}` (`{user.id}`)\nMotif initial : {row['reason']}", discord.Color.green())
            except (discord.Forbidden, discord.HTTPException) as exc:
                getattr(self.bot, "moderation_unban_ids", set()).discard(int(row["user_id"]))
                await self.admin_error(guild, f"Échec de levée du bannissement temporaire de `{row['user_id']}` : `{type(exc).__name__}: {exc}`")

    @expire_tempbans.before_loop
    async def before_expire_tempbans(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoModeration(bot))

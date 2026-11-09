"""Capsules du Temps personnelles : conservation privée, échéance et suppression."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from .storage import db

DURATIONS = (30, 90, 180)
MAX_ACTIVE = 5

def now_utc():
    return datetime.now(timezone.utc)

def create(guild_id: int, user_id: int, content: str, days: int) -> int:
    content = content.strip()
    if days not in DURATIONS or not 1 <= len(content) <= 1000:
        raise ValueError("Durée ou longueur de capsule invalide.")
    now = now_utc()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) FROM time_capsules WHERE guild_id=? AND user_id=? AND opened_at IS NULL", (guild_id,user_id)).fetchone()[0]
        if count >= MAX_ACTIVE:
            raise ValueError("Tu as déjà cinq capsules non ouvertes. Ouvre ou supprime une capsule avant d'en créer une autre.")
        cur = conn.execute("INSERT INTO time_capsules(guild_id,user_id,content,created_at,due_at) VALUES(?,?,?,?,?)", (guild_id,user_id,content,now.isoformat(),(now+timedelta(days=days)).isoformat()))
        return int(cur.lastrowid)

def list_capsules(guild_id: int, user_id: int):
    with db() as conn:
        return conn.execute("SELECT id,due_at,opened_at FROM time_capsules WHERE guild_id=? AND user_id=? ORDER BY due_at,id", (guild_id,user_id)).fetchall()

def open_capsule(guild_id: int, user_id: int, capsule_id: int) -> str | None:
    now = now_utc().isoformat()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT content,due_at FROM time_capsules WHERE id=? AND guild_id=? AND user_id=?", (capsule_id,guild_id,user_id)).fetchone()
        if row is None or row['due_at'] > now:
            return None
        conn.execute("UPDATE time_capsules SET opened_at=COALESCE(opened_at,?) WHERE id=? AND guild_id=? AND user_id=?", (now,capsule_id,guild_id,user_id))
        return str(row['content'])

def delete_capsule(guild_id: int, user_id: int, capsule_id: int) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM time_capsules WHERE id=? AND guild_id=? AND user_id=?", (capsule_id,guild_id,user_id))
        return cur.rowcount > 0

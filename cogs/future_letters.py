"""Lettres du Futur : conservation privée et consultation à échéance."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from .storage import db

MAX_ACTIVE = 3
DURATIONS = (7, 30, 90)

def now_utc():
    return datetime.now(timezone.utc)

def create(guild_id: int, user_id: int, content: str, days: int) -> int:
    content = content.strip()
    if days not in DURATIONS or not 1 <= len(content) <= 1000:
        raise ValueError("Durée ou longueur de lettre invalide")
    now = now_utc()
    with db() as conn:
        # BEGIN IMMEDIATE évite de dépasser le quota lors de créations simultanées.
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) FROM future_letters WHERE guild_id=? AND user_id=? AND opened_at IS NULL", (guild_id,user_id)).fetchone()[0]
        if count >= MAX_ACTIVE:
            raise ValueError("Tu as déjà trois lettres en attente. Ouvre ou supprime une lettre avant d'en créer une autre.")
        cur = conn.execute("INSERT INTO future_letters(guild_id,user_id,content,created_at,due_at) VALUES(?,?,?,?,?)", (guild_id,user_id,content,now.isoformat(),(now+timedelta(days=days)).isoformat()))
        return cur.lastrowid

def list_letters(guild_id: int, user_id: int):
    with db() as conn:
        return conn.execute("SELECT id,due_at,opened_at FROM future_letters WHERE guild_id=? AND user_id=? ORDER BY due_at,id",(guild_id,user_id)).fetchall()

def open_letter(guild_id: int, user_id: int, letter_id: int) -> str | None:
    now=now_utc().isoformat()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT content,due_at FROM future_letters WHERE id=? AND guild_id=? AND user_id=?",(letter_id,guild_id,user_id)).fetchone()
        if row is None or row['due_at'] > now:
            return None
        conn.execute("UPDATE future_letters SET opened_at=COALESCE(opened_at,?) WHERE id=? AND guild_id=? AND user_id=?",(now,letter_id,guild_id,user_id))
        return row['content']

def delete_letter(guild_id: int, user_id: int, letter_id: int) -> bool:
    with db() as conn:
        cur=conn.execute("DELETE FROM future_letters WHERE id=? AND guild_id=? AND user_id=?",(letter_id,guild_id,user_id))
        return cur.rowcount > 0

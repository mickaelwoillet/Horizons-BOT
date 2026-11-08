"""Stockage SQLite léger et persistant pour HORIZONS."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from config import DATA_DIR

DB_PATH = DATA_DIR / "horizons.sqlite3"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS warnings (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 moderator_id INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS birthdays (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, month INTEGER NOT NULL, day INTEGER NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS birthday_posts (
 guild_id INTEGER NOT NULL, year INTEGER NOT NULL, user_id INTEGER NOT NULL,
 PRIMARY KEY(guild_id,year,user_id)
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
 message_id INTEGER, creator_id INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL,
 starts_at TEXT NOT NULL, location TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_rsvps (
 event_id INTEGER NOT NULL, user_id INTEGER NOT NULL, response TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(event_id,user_id),
 FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS tickets (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL UNIQUE,
 message_id INTEGER, opener_id INTEGER NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 created_at TEXT NOT NULL, closed_at TEXT
);
CREATE TABLE IF NOT EXISTS giveaway_entries (
 giveaway_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(giveaway_id,user_id),
 FOREIGN KEY(giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS giveaways (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
 message_id INTEGER, creator_id INTEGER NOT NULL, prize TEXT NOT NULL, winners_count INTEGER NOT NULL,
 ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS role_panels (
 channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL UNIQUE, category TEXT NOT NULL,
 PRIMARY KEY(channel_id,category)
);
CREATE TABLE IF NOT EXISTS activity_days (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, active_date TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,active_date)
);
CREATE TABLE IF NOT EXISTS member_notes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 moderator_id INTEGER NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings(guild_id,user_id,active);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(guild_id,status,starts_at);

CREATE TABLE IF NOT EXISTS passport_completions (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, week_key TEXT NOT NULL,
 mission_number INTEGER NOT NULL, completed_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,week_key,mission_number)
);
CREATE TABLE IF NOT EXISTS passport_week_announcements (
 guild_id INTEGER NOT NULL, week_key TEXT NOT NULL, posted_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,week_key)
);
CREATE TABLE IF NOT EXISTS activity_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 channel_id INTEGER NOT NULL, message_id INTEGER, thread_id INTEGER, activity TEXT NOT NULL, details TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE IF NOT EXISTS activity_request_interests (
 request_id INTEGER NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(request_id,user_id),
 FOREIGN KEY(request_id) REFERENCES activity_requests(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS collective_challenges (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL, target INTEGER NOT NULL, created_by INTEGER NOT NULL,
 created_at TEXT NOT NULL, ends_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
 announced INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS collective_challenge_members (
 challenge_id INTEGER NOT NULL, user_id INTEGER NOT NULL, joined_at TEXT NOT NULL,
 PRIMARY KEY(challenge_id,user_id),
 FOREIGN KEY(challenge_id) REFERENCES collective_challenges(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_activity_requests_status ON activity_requests(guild_id,status,expires_at);
CREATE INDEX IF NOT EXISTS idx_collective_challenges_status ON collective_challenges(guild_id,status,ends_at);
CREATE TABLE IF NOT EXISTS bot_settings (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mood_entries (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, mood_date TEXT NOT NULL,
 mood TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,mood_date)
);
CREATE TABLE IF NOT EXISTS success_unlocks (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, achievement_key TEXT NOT NULL,
 unlocked_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,achievement_key)
);
CREATE TABLE IF NOT EXISTS success_activity_days (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, active_date TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,active_date)
);
CREATE TABLE IF NOT EXISTS affinity_optins (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, enabled_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS community_ideas (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 message_id INTEGER, thread_id INTEGER, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'received', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS community_idea_votes (
 idea_id INTEGER NOT NULL, user_id INTEGER NOT NULL, vote INTEGER NOT NULL,
 PRIMARY KEY(idea_id,user_id), FOREIGN KEY(idea_id) REFERENCES community_ideas(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS solidarity_thanks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL,
 target_id INTEGER NOT NULL, reason TEXT NOT NULL, message_id INTEGER, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_community_ideas_status ON community_ideas(guild_id,status,created_at);
CREATE INDEX IF NOT EXISTS idx_solidarity_target ON solidarity_thanks(guild_id,target_id,created_at);
CREATE TABLE IF NOT EXISTS event_reminders (
 event_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reminder_type TEXT NOT NULL,
 sent_at TEXT NOT NULL,
 PRIMARY KEY(event_id,user_id,reminder_type),
 FOREIGN KEY(event_id) REFERENCES events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS staff_tasks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL, assignee_id INTEGER NOT NULL, creator_id INTEGER NOT NULL,
 priority TEXT NOT NULL DEFAULT 'normal', status TEXT NOT NULL DEFAULT 'todo',
 due_at TEXT, created_at TEXT NOT NULL, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_staff_tasks_status ON staff_tasks(guild_id,status,assignee_id);
CREATE TABLE IF NOT EXISTS staff_task_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, actor_id INTEGER NOT NULL,
 action TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(task_id) REFERENCES staff_tasks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS staff_shifts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 started_at TEXT NOT NULL, ended_at TEXT, note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_staff_shifts_active ON staff_shifts(guild_id,ended_at);
CREATE TABLE IF NOT EXISTS horizons_path_progress (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, theme_key TEXT NOT NULL,
 step_number INTEGER NOT NULL, completed_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,theme_key,step_number)
);
CREATE INDEX IF NOT EXISTS idx_horizons_path_user ON horizons_path_progress(guild_id,user_id);
CREATE TABLE IF NOT EXISTS staff_alerts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 reporter_id INTEGER NOT NULL, reason TEXT NOT NULL, channel_id INTEGER, message_id TEXT,
 status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS horizons_seasons (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL, starts_at TEXT NOT NULL, ends_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active', created_by INTEGER NOT NULL, created_at TEXT NOT NULL, closed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_horizons_seasons_active ON horizons_seasons(guild_id,status,ends_at);
CREATE TABLE IF NOT EXISTS horizons_season_participants (
 season_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, joined_at TEXT NOT NULL,
 PRIMARY KEY(season_id,user_id), FOREIGN KEY(season_id) REFERENCES horizons_seasons(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS horizons_season_completions (
 season_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 week_number INTEGER NOT NULL, mission_number INTEGER NOT NULL, completed_at TEXT NOT NULL,
 PRIMARY KEY(season_id,user_id,week_number,mission_number),
 FOREIGN KEY(season_id) REFERENCES horizons_seasons(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_horizons_season_completions ON horizons_season_completions(season_id,completed_at);
CREATE TABLE IF NOT EXISTS horizons_season_milestones (
 season_id INTEGER NOT NULL, threshold INTEGER NOT NULL, reached_at TEXT NOT NULL,
 PRIMARY KEY(season_id,threshold), FOREIGN KEY(season_id) REFERENCES horizons_seasons(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS horizons_season_week_announcements (
 season_id INTEGER NOT NULL, week_number INTEGER NOT NULL, posted_at TEXT NOT NULL,
 PRIMARY KEY(season_id,week_number), FOREIGN KEY(season_id) REFERENCES horizons_seasons(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS horizons_season_rewards (
 season_id INTEGER NOT NULL, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 reward_key TEXT NOT NULL, unlocked_at TEXT NOT NULL,
 PRIMARY KEY(season_id,user_id,reward_key),
 FOREIGN KEY(season_id) REFERENCES horizons_seasons(id) ON DELETE CASCADE
);

-- Statistiques agrégées du tableau de bord HORIZONS (aucun contenu de message).
CREATE TABLE IF NOT EXISTS horizons_dashboard_message_daily (
 guild_id INTEGER NOT NULL, activity_date TEXT NOT NULL, channel_id INTEGER NOT NULL,
 message_count INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,activity_date,channel_id)
);
CREATE INDEX IF NOT EXISTS idx_horizons_dashboard_messages_date
 ON horizons_dashboard_message_daily(guild_id,activity_date);
CREATE TABLE IF NOT EXISTS horizons_dashboard_member_daily (
 guild_id INTEGER NOT NULL, activity_date TEXT NOT NULL,
 joins INTEGER NOT NULL DEFAULT 0, leaves INTEGER NOT NULL DEFAULT 0, member_count INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,activity_date)
);
CREATE TABLE IF NOT EXISTS horizons_dashboard_meta (
 key TEXT PRIMARY KEY, value TEXT NOT NULL
);

-- Progression ludique HORIZONS : indépendante des rangs communautaires.
CREATE TABLE IF NOT EXISTS celestial_game_xp (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL, PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS celestial_game_rewards (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, reward_date TEXT NOT NULL,
 game_key TEXT NOT NULL, xp_awarded INTEGER NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,reward_date,game_key)
);
CREATE TABLE IF NOT EXISTS celestial_game_history (
 session_id TEXT PRIMARY KEY, guild_id INTEGER NOT NULL, game_key TEXT NOT NULL,
 mode TEXT NOT NULL, players_json TEXT NOT NULL, winners_json TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL, scores_json TEXT NOT NULL DEFAULT '{}',
 started_at TEXT NOT NULL, ended_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_celestial_game_history_user
 ON celestial_game_history(guild_id,game_key,ended_at);
CREATE TABLE IF NOT EXISTS celestial_game_player_stats (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, game_key TEXT NOT NULL,
 played INTEGER NOT NULL DEFAULT 0, wins INTEGER NOT NULL DEFAULT 0,
 losses INTEGER NOT NULL DEFAULT 0, draws INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,game_key)
);
CREATE TABLE IF NOT EXISTS celestial_game_achievements (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, achievement_key TEXT NOT NULL,
 unlocked_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,achievement_key)
);
CREATE TABLE IF NOT EXISTS celestial_weekly_missions (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, week_key TEXT NOT NULL,
 mission_key TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
 completed_at TEXT, claimed_at TEXT, xp_awarded INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,user_id,week_key,mission_key)
);
CREATE INDEX IF NOT EXISTS idx_celestial_weekly_missions_user
 ON celestial_weekly_missions(guild_id,user_id,week_key);
CREATE TABLE IF NOT EXISTS celestial_game_settings (
 guild_id INTEGER NOT NULL, setting_key TEXT NOT NULL, setting_value TEXT NOT NULL,
 PRIMARY KEY(guild_id,setting_key)
);
-- Trésors du Ciel : inventaire, cartes quotidiennes/offertes et historique des cadeaux.
CREATE TABLE IF NOT EXISTS celestial_stars (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, star_key TEXT NOT NULL,
 obtained_at TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'carte',
 PRIMARY KEY(guild_id,user_id,star_key)
);
CREATE TABLE IF NOT EXISTS celestial_star_progress (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 consecutive_duplicates INTEGER NOT NULL DEFAULT 0,
 total_star_draws INTEGER NOT NULL DEFAULT 0,
 updated_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS celestial_collection_unlocks (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 reward_key TEXT NOT NULL, unlocked_at TEXT NOT NULL,
 PRIMARY KEY(guild_id,user_id,reward_key)
);
CREATE TABLE IF NOT EXISTS celestial_dust (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, dust INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS celestial_fragments (
 guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, fragments INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,user_id)
);
CREATE TABLE IF NOT EXISTS celestial_daily_cards (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 card_date TEXT NOT NULL, used_at TEXT,
 UNIQUE(guild_id,user_id,card_date)
);
CREATE TABLE IF NOT EXISTS celestial_gift_cards (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
 granted_by INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL, used_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_celestial_gift_cards_available
 ON celestial_gift_cards(guild_id,user_id,used_at,id);
CREATE TABLE IF NOT EXISTS celestial_gift_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL, recipient_id INTEGER NOT NULL,
 giver_id INTEGER NOT NULL, quantity INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        # Migrations non destructives pour les bases créées par une version antérieure.
        ticket_columns = {row[1] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
        if "message_id" not in ticket_columns:
            conn.execute("ALTER TABLE tickets ADD COLUMN message_id INTEGER")
        request_columns = {row[1] for row in conn.execute("PRAGMA table_info(activity_requests)").fetchall()}
        if "thread_id" not in request_columns:
            conn.execute("ALTER TABLE activity_requests ADD COLUMN thread_id INTEGER")
        idea_columns = {row[1] for row in conn.execute("PRAGMA table_info(community_ideas)").fetchall()}
        if "thread_id" not in idea_columns:
            conn.execute("ALTER TABLE community_ideas ADD COLUMN thread_id INTEGER")
        giveaway_columns = {row[1] for row in conn.execute("PRAGMA table_info(giveaways)").fetchall()}
        for column, definition in {
            "description": "TEXT NOT NULL DEFAULT ''",
            "image_url": "TEXT",
            "required_role_id": "INTEGER",
            "winners_json": "TEXT NOT NULL DEFAULT '[]'",
        }.items():
            if column not in giveaway_columns:
                conn.execute(f"ALTER TABLE giveaways ADD COLUMN {column} {definition}")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

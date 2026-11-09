"""Contrôles sans connexion Discord pour le panneau Aujourd'hui."""
import sqlite3
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / 'cogs' / 'today_hub.py').read_text(encoding='utf-8')


class TodayHubIntegrityTests(unittest.TestCase):
    def test_menu_without_new_slash_command(self):
        self.assertIn('class TodayChoice(discord.ui.Select)', SOURCE)
        self.assertIn('class ActivityProposalSelect(discord.ui.Select)', SOURCE)
        self.assertNotIn('@app_commands.command', SOURCE)

    def test_panel_only_edited_when_changed(self):
        self.assertIn('msg.embeds[0].description != embed.description', SOURCE)
        self.assertIn('or not msg.components', SOURCE)
        self.assertIn('self.save_setting(MESSAGE_KEY, msg.id)', SOURCE)

    def test_participation_unique_after_restart(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE today_challenge_participation (guild_id INTEGER, day TEXT, user_id INTEGER, joined_at TEXT, PRIMARY KEY(guild_id,day,user_id))')
        for _ in range(2):
            conn.execute('INSERT OR IGNORE INTO today_challenge_participation VALUES (1, "2026-11-09", 5, "now")')
            conn.commit()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM today_challenge_participation').fetchone()[0], 1)
        self.assertIn('INSERT OR IGNORE INTO today_challenge_participation', SOURCE)

    def test_activity_limit_excludes_expired(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE activity_requests (guild_id INTEGER, user_id INTEGER, status TEXT, created_at TEXT, expires_at TEXT)')
        now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        def add(created, expires, status='open'):
            conn.execute('INSERT INTO activity_requests VALUES (1,2,?,?,?)', (status,created.isoformat(),expires.isoformat()))
        add(now-timedelta(hours=1),now+timedelta(hours=5))
        add(now-timedelta(hours=2),now-timedelta(minutes=1))
        add(now-timedelta(hours=7),now+timedelta(hours=1))
        add(now-timedelta(minutes=15),now+timedelta(hours=1), 'closed')
        query = ("SELECT COUNT(*) FROM activity_requests WHERE guild_id=? AND user_id=? "
                 "AND status='open' AND created_at >= ? AND expires_at > ?")
        self.assertEqual(conn.execute(query,(1,2,(now-timedelta(hours=6)).isoformat(),now.isoformat())).fetchone()[0],1)
        self.assertIn("AND status='open' AND created_at >= ? AND expires_at > ?", SOURCE)


if __name__ == '__main__':
    unittest.main()

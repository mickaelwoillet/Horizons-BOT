"""Tests autonomes du rôle de victoire : python -m unittest discover -s tests -p test_escape_v11_rewards.py"""
import asyncio
import importlib.util
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

# Lightweight Discord stub: no network, no token, no live server required.
discord = types.ModuleType('discord')
class DiscordError(Exception): pass
class Color:
    def __init__(self, value): self.value = value
class Permissions:
    @staticmethod
    def none(): return 0
class File:
    def __init__(self, *args, **kwargs): pass
class Embed:
    def __init__(self, **kwargs): self.kwargs = kwargs
    def set_footer(self, **kwargs): pass
    def set_image(self, **kwargs): pass
class Mentions:
    @staticmethod
    def none(): return None
discord.Color, discord.Permissions, discord.File = Color, Permissions, File
discord.Embed, discord.AllowedMentions = Embed, Mentions
discord.Forbidden = discord.HTTPException = discord.NotFound = DiscordError
discord.utils = types.SimpleNamespace(get=lambda roles, name: next((r for r in roles if r.name == name), None))
sys.modules.setdefault('discord', discord)
spec = importlib.util.spec_from_file_location('escape_victory', Path(__file__).resolve().parents[1] / 'escape_victory.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class Member:
    def __init__(self): self.roles = []; self.add_roles = AsyncMock(side_effect=self.add)
    async def add(self, role, **kwargs): self.roles.append(role)

class TestRewards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'test.sqlite3'
        with sqlite3.connect(self.db) as con:
            con.executescript('CREATE TABLE teams (id INTEGER, guild_id INTEGER, adventure TEXT); CREATE TABLE team_members (team_id INTEGER, user_id INTEGER);')
            con.execute('INSERT INTO teams VALUES (7,1,\'fractures\')')
            con.executemany('INSERT INTO team_members VALUES (7,?)', [(11,), (12,)])
        self.members = {11: Member(), 12: Member()}
        self.guild = types.SimpleNamespace(roles=[], get_member=lambda uid: self.members.get(uid))
        async def create_role(**kwargs):
            role = types.SimpleNamespace(name=kwargs['name'])
            self.guild.roles.append(role)
            return role
        self.guild.create_role = AsyncMock(side_effect=create_role)
        self.guild.fetch_member = AsyncMock(side_effect=lambda uid: self.members[uid])
        self.interaction = types.SimpleNamespace(guild=self.guild)

    def test_team_role_creation_and_idempotence(self):
        key = (1, 'fractures', 'team', 7)
        first = asyncio.run(mod.award_role(self.interaction, self.db, key))
        second = asyncio.run(mod.award_role(self.interaction, self.db, key))
        self.assertEqual(first, ([11, 12], []))
        self.assertEqual(second, ([11, 12], []))
        self.assertEqual(self.guild.create_role.await_count, 1)
        self.assertEqual([m.add_roles.await_count for m in self.members.values()], [1, 1])

    def test_missing_manage_roles_is_non_blocking(self):
        self.guild.create_role = AsyncMock(side_effect=DiscordError('Forbidden'))
        awarded, failed = asyncio.run(mod.award_role(self.interaction, self.db, (1, 'fractures', 'team', 7)))
        self.assertEqual(awarded, [])
        self.assertEqual(failed, [11, 12])

    def test_solo_award(self):
        awarded, failed = asyncio.run(mod.award_role(self.interaction, self.db, (1, 'fractures', 'solo', 11)))
        self.assertEqual((awarded, failed), ([11], []))

if __name__ == '__main__': unittest.main()

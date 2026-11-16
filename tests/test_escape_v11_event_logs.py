"""Offline event log tests. Run: python tests/test_escape_v11_event_logs.py"""
import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

fake_discord = types.ModuleType('discord')
class TextChannel: pass
class Forbidden(Exception): pass
class HTTPException(Exception): pass
class AllowedMentions:
    @staticmethod
    def none(): return None
fake_discord.TextChannel = TextChannel
fake_discord.Forbidden = Forbidden
fake_discord.HTTPException = HTTPException
fake_discord.AllowedMentions = AllowedMentions
sys.modules['discord'] = fake_discord
spec = importlib.util.spec_from_file_location('escape_event_logs', Path(__file__).resolve().parents[1] / 'escape_event_logs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Channel(TextChannel):
    def __init__(self, name='logs-evenements', fail=False):
        self.name, self.id, self.fail, self.messages = name, 123, fail, []
    async def send(self, message, **kwargs):
        if self.fail: raise Forbidden('missing permission')
        self.messages.append((message, kwargs))
class Guild:
    def __init__(self, channels): self.id=5; self.text_channels=channels; self.channels=channels
    def get_channel(self, id): return next((c for c in self.channels if c.id == id), None)
class User:
    mention='<@42>'
class Interaction:
    def __init__(self, guild): self.guild=guild; self.user=User()

async def run():
    ch=Channel(); inter=Interaction(Guild([ch]))
    with patch.dict(os.environ, {'ESCAPE_EVENTS_LOG_CHANNEL_ID':''}):
        await module.log_escape_event(inter,'start')
        await module.log_escape_event(inter,'room',room_number=3,room_name='Atelier',mode='team')
        await module.log_escape_event(inter,'finish',mode='solo')
    assert len(ch.messages)==3
    assert 'commencé' in ch.messages[0][0]
    assert 'salle 3' in ch.messages[1][0] and 'en équipe' in ch.messages[1][0]
    assert 'terminé avec succès' in ch.messages[2][0]
    assert all(k['allowed_mentions'] is None for _,k in ch.messages)
    await module.log_escape_event(Interaction(Guild([])),'start')
    await module.log_escape_event(Interaction(Guild([Channel(fail=True)])),'finish')
    await module.log_escape_event(inter,'unknown')
    assert len(ch.messages)==3
    print('OK: start, room, finish, team, missing channel, missing permission, unknown event')

if __name__=='__main__': asyncio.run(run())

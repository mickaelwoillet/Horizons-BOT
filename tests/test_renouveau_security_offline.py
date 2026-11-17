"""Tests hors ligne des contrôles de sécurité du renouveau (sans discord.py)."""
import ast
import pathlib
import types
import unicodedata
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "cogs" / "renouveau_admin.py"
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"normalized", "channel_is_expected"}]
module = ast.Module(body=keep, type_ignores=[])

class FakeTextChannel:
    def __init__(self, guild, name, category_id):
        self.guild = guild
        self.name = name
        self.category_id = category_id

ns = {
    "discord": types.SimpleNamespace(TextChannel=FakeTextChannel),
    "unicodedata": unicodedata,
    "EXPECTED_CATEGORIES": {123: 456},
}
exec(compile(module, str(SOURCE), "exec"), ns)

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.guild = types.SimpleNamespace(id=77)
    def eligible(self, name, category=456, guild=None):
        channel = FakeTextChannel(guild or self.guild, name, category)
        return ns["channel_is_expected"](channel, "missions horizons", 123, self.guild)[0]
    def test_expected(self):
        self.assertTrue(self.eligible("missions-horizons"))
    def test_suffix_rejected(self):
        self.assertFalse(self.eligible("missions-horizons-archive"))
    def test_prefix_rejected(self):
        self.assertFalse(self.eligible("anciennes-missions-horizons"))
    def test_wrong_category(self):
        self.assertFalse(self.eligible("missions-horizons", 999))
    def test_wrong_guild(self):
        self.assertFalse(self.eligible("missions-horizons", guild=types.SimpleNamespace(id=88)))
    def test_accents(self):
        self.assertTrue(self.eligible("Missions HORIZONS"))
    def test_missing(self):
        self.assertFalse(ns["channel_is_expected"](None, "missions horizons", 123, self.guild)[0])

if __name__ == "__main__":
    unittest.main()

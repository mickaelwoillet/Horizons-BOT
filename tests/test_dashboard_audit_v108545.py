"""Régressions statiques pour les trois tableaux de bord HORIZONS."""
import ast
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def method(module, cls, name):
    tree = ast.parse((ROOT / "cogs" / module).read_text(encoding="utf-8"))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)

class DashboardAudit(unittest.TestCase):
    def test_centre_acknowledges_before_database(self):
        node = method("centre_horizons.py", "CentreHorizons", "centre")
        source = ast.unparse(node)
        self.assertLess(source.index("interaction.response.defer"), source.index("visit(interaction.guild_id"))
        self.assertIn("interaction.followup.send", source)
    def test_nox_buttons_have_explicit_row_packing(self):
        tree = ast.parse((ROOT / "cogs/chaos_cosmique.py").read_text())
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NoxCentralView")
        refresh = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "refresh")
        self.assertIn("index // 5", ast.unparse(refresh))
        self.assertIn("len(section_actions) > 20", ast.unparse(refresh))
    def test_staff_dashboard_does_not_lookup_missing_select(self):
        node = method("staff_dashboard.py", "DashboardSelect", "callback")
        self.assertNotIn("next(item for item in view.children", ast.unparse(node))
    def test_centre_owner_guard(self):
        node = method("centre_horizons.py", "CentreView", "interaction_check")
        self.assertIn("self.owner_id", ast.unparse(node))
    def test_staff_owner_and_shift_guard(self):
        node = method("staff_dashboard.py", "DashboardView", "interaction_check")
        source = ast.unparse(node)
        self.assertIn("self.user_id", source)
        self.assertIn("is_on_service", source)

if __name__ == "__main__": unittest.main()

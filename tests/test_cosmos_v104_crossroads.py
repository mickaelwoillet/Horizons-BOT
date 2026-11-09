"""V10.4: validation des choix, idempotence et persistance."""
import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_crossroads_have_three_outcomes():
    from cogs.chaos_cosmique import CROSSROADS
    assert len(CROSSROADS) >= 4
    assert len({arc[0] for arc in CROSSROADS}) == len(CROSSROADS)
    for arc in CROSSROADS:
        assert len(arc[3]) == len(arc[4]) == 3
        assert all(len(outcome) == 5 for outcome in arc[4])


def test_choice_is_idempotent_and_updates_world(tmp_path, monkeypatch):
    from cogs import chaos_cosmique as c
    monkeypatch.setattr(c, 'DB_PATH', tmp_path / 'cosmos.sqlite3')
    monkeypatch.setattr(c, 'DATA_DIR', tmp_path)
    with c.connect() as conn:
        result, first = c.choose_crossroad(conn, 123, 456, '2026-11-09', 0)
        assert first
        state = dict(conn.execute('SELECT * FROM cosmic_world WHERE guild_id=123').fetchone())
        result2, second = c.choose_crossroad(conn, 123, 456, '2026-11-09', 2)
        assert not second and result == result2
        assert dict(conn.execute('SELECT * FROM cosmic_world WHERE guild_id=123').fetchone()) == state
        assert conn.execute('SELECT count(*) FROM cosmic_journal').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM cosmic_crossroads').fetchone()[0] == 1


def test_scene_is_stable():
    from cogs.chaos_cosmique import crossroad_scene
    assert crossroad_scene(123,456,'2026-11-09') == crossroad_scene(123,456,'2026-11-09')

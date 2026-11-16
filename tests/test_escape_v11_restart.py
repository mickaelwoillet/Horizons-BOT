"""V1.1: test de conservation des sessions sur SQLite temporaire, sans Discord."""
import json
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from escape_engine import Engine

DATA = json.loads((ROOT / 'escape_content/fractures.json').read_text(encoding='utf-8'))

def run():
    with tempfile.TemporaryDirectory(prefix='escape_restart_') as tmp:
        path = Path(tmp) / 'sessions.sqlite'
        adventure = DATA['id']
        first = DATA['rooms'][0]['id']
        engine = Engine(path)
        cases = [('solo', 101), ('team', 202)]
        for mode, owner in cases:
            engine.start(1, adventure, mode, owner, first)
            engine.collect(1, adventure, mode, owner, f'test_token_{mode}')
            # Simule une énigme déjà résolue et une salle atteinte, dans la base de test.
            with engine.connect() as con:
                con.execute('INSERT INTO escape_solved VALUES (?,?,?,?,?)', (1, adventure, mode, owner, f'test_puzzle_{mode}'))
                con.execute('UPDATE escape_sessions SET room_id=? WHERE guild_id=? AND adventure=? AND mode=? AND owner_id=?', (DATA['rooms'][1]['id'], 1, adventure, mode, owner))
        del engine
        restarted = Engine(path)
        for mode, owner in cases:
            expected = restarted.status(1, adventure, mode, owner)
            assert expected['room_id'] == DATA['rooms'][1]['id']
            assert f'test_token_{mode}' in expected['items']
            assert f'test_puzzle_{mode}' in expected['solved']
            assert restarted.start(1, adventure, mode, owner, first) == expected, 'start() must not reset progress'
            print(f'OK {mode}: room, items, solved persist across Engine restart')
        assert restarted.status(1, adventure, 'solo', 202) is None, 'sessions must remain separated by mode'
        assert restarted.status(2, adventure, 'solo', 101) is None, 'sessions must remain separated by guild'
        print('OK isolation: guild and mode')

if __name__ == '__main__':
    run()

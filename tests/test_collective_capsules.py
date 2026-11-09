"""Tests locaux des capsules collectives sans connexion Discord."""
import tempfile
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
from cogs import storage, collective_capsules as c

with tempfile.TemporaryDirectory() as folder:
    with patch.object(storage, 'DB_PATH', Path(folder)/'test.sqlite3'):
        storage.init_db()
        c.set_question(1, 99, 'Quel souvenir aimerais-tu garder ?')
        assert c.current_question(1)['question'].startswith('Quel souvenir')
        c.submit(1, 42, 'Un moment chaleureux.')
        assert len(c.pending(1)) == 1
        answer = c.my_answers(1, 42)[0]
        assert not c.revealed(1, c.utcnow().strftime('%Y-%m'))
        assert c.moderate(1,99,answer['id'],True)
        assert not c.moderate(1,99,answer['id'],True)
        assert not c.revealed(1, c.utcnow().strftime('%Y-%m'))
        with storage.db() as db:
            db.execute('UPDATE collective_capsule_questions SET reveal_at=? WHERE guild_id=1', ((c.utcnow()-timedelta(days=1)).isoformat(),))
        assert len(c.revealed(1,c.utcnow().strftime('%Y-%m'))) == 1
        assert not c.withdraw(1,43,answer['id'])
        assert c.withdraw(1,42,answer['id'])
        assert not c.revealed(1,c.utcnow().strftime('%Y-%m'))
print('Tests capsules collectives réussis')

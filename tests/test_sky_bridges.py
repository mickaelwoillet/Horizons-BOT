"""Tests locaux de consentement et de confidentialité des Passerelles."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from cogs import storage, sky_bridges as b

with tempfile.TemporaryDirectory() as folder:
    with patch.object(storage,'DB_PATH',Path(folder)/'test.sqlite3'):
        storage.init_db()
        assert not b.profile(1,10)['enabled']
        assert b.suggestions(1,10)==[]
        b.save(1,10,['jeux','musique'])
        b.save(1,11,['jeux','lecture'])
        b.save(2,12,['jeux'])
        assert b.suggestions(1,10)==[('jeux',1)]
        assert b.suggestions(2,12)==[]
        assert b.profile(1,10)['interests']==['jeux','musique']
        b.save(1,10,['cinema'])
        assert b.suggestions(1,10)==[]
        assert b.disable(1,11)
        assert not b.profile(1,11)['enabled']
        assert not b.profile(1,11)['interests']
        assert not b.disable(1,11)
        try:
            b.save(1,10,['inconnu'])
        except ValueError:
            pass
        else:
            raise AssertionError('Une préférence inconnue doit être refusée')
print('Tests Passerelles réussis')

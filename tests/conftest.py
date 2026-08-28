import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest

from src import db


@pytest.fixture(scope='session', autouse=True)
def test_database(tmp_path_factory):
    """Run the suite against a throwaway database.

    db.DB_PATH otherwise points at watcher.db in the repo root, which does not
    exist on a fresh checkout (it is gitignored), so any test that queries the
    schema fails. Pointing it at a temp file also keeps the suite from writing
    to a real watcher.db when one is present.
    """
    db.DB_PATH = tmp_path_factory.mktemp('watcher') / 'watcher.db'
    db.init_db()
    return db.DB_PATH

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import db


def test_db_search_runs():
    rows = db.search_page_versions('Anthropic', limit=5)
    assert isinstance(rows, list)
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import db


def test_db_search_runs():
    site_id = db.add_site('https://example.org', 'example.org')
    page_id = db.upsert_page(site_id, 'https://example.org', 'example.org')
    vid = db.insert_page_version(site_id, page_id, '2026-01-02T00:00:00', 'AnthropicDbSearchMarker makes Claude', 'cafebabe', [])

    rows = db.search_page_versions('AnthropicDbSearchMarker', limit=5)
    assert isinstance(rows, list) and len(rows) == 1
    row = rows[0]
    assert row['page_version_id'] == vid
    assert row['content_hash'] == 'cafebabe'
    assert '<b>AnthropicDbSearchMarker</b>' in row['snippet']
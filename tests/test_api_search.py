import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import db
from src.ui import app


def test_api_search_no_query():
    client = app.test_client()
    r = client.get('/api/search')
    assert r.status_code == 200
    data = r.get_json()
    assert 'results' in data and isinstance(data['results'], list)


def test_api_search_query_returns_list():
    site_id = db.add_site('https://example.com', 'example.com')
    page_id = db.upsert_page(site_id, 'https://example.com', 'example.com')
    vid = db.insert_page_version(site_id, page_id, '2026-01-01T00:00:00', 'AnthropicApiSearchMarker makes Claude', 'deadbeef', [])

    client = app.test_client()
    r = client.get('/api/search?q=AnthropicApiSearchMarker')
    assert r.status_code == 200
    data = r.get_json()
    results = data.get('results', [])
    assert isinstance(results, list) and len(results) == 1
    row = results[0]
    assert row['page_version_id'] == vid
    assert row['content_hash'] == 'deadbeef'
    assert row['site_id'] == site_id
    assert row['archived_at'] == '2026-01-01T00:00:00'
    assert 'AnthropicApiSearchMarker' in row['snippet']
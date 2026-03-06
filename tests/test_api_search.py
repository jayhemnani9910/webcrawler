import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ui import app


def test_api_search_no_query():
    client = app.test_client()
    r = client.get('/api/search')
    assert r.status_code == 200
    data = r.get_json()
    assert 'results' in data and isinstance(data['results'], list)


def test_api_search_query_returns_list():
    client = app.test_client()
    r = client.get('/api/search?q=Anthropic')
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data.get('results', []), list)
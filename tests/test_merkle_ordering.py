import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ui import app
from src import db
from src.merkle_sync import create_delta, attach_sequence_and_sign


def test_obsolete_delta_rejected():
    # ensure DB and site exist
    db.init_db()
    site_id = db.add_site('http://example.com', 'example.com')
    # create and store a signed delta (this will increment sequence/lamport)
    delta = create_delta(site_id, [{'payload': 'first'}])
    signed = attach_sequence_and_sign(delta)
    client = app.test_client()
    # re-post the same delta (same sequence/lamport) -> should be treated as obsolete
    resp = client.post('/api/merkle/push', json={'delta': signed['delta'], 'signature': signed['signature']})
    assert resp.status_code == 409
    j = resp.get_json()
    assert j is not None
    assert 'obsolete' in (j.get('error') or '')

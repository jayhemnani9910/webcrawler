import time
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import archivebox_interface as abi


def test_archive_and_wait_success(monkeypatch):
    calls = {'count': 0}

    def fake_archive_url(url, archivebox_args=None):
        # simulate a successful trigger
        calls['triggered'] = True
        return {'raw_output': 'ok'}

    def fake_find():
        # first two calls return empty, third returns entry
        calls['count'] += 1
        if calls['count'] < 3:
            return {}
        return {'url': 'https://example.com/page', 'outfile': '/tmp/fake.html', 'timestamp': 123}

    monkeypatch.setattr(abi, 'archive_url', fake_archive_url)
    monkeypatch.setattr(abi, 'find_archive_entry_for_url', lambda url: fake_find())
    # speed up sleep
    monkeypatch.setattr(time, 'sleep', lambda s: None)

    entry = abi.archive_and_wait('https://example.com/page', timeout=5, poll_interval=0)
    assert entry and entry.get('url') == 'https://example.com/page'


def test_archive_and_wait_timeout(monkeypatch):
    monkeypatch.setattr(abi, 'archive_url', lambda url, archivebox_args=None: {'raw_output': 'ok'})
    monkeypatch.setattr(abi, 'find_archive_entry_for_url', lambda url: {})
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    entry = abi.archive_and_wait('https://nope.example/', timeout=0.1, poll_interval=0)
    assert entry == {}

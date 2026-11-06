import pytest

from src import crawler, db


@pytest.mark.parametrize('registered_with_watcher', [True, False])
def test_crawl_archives_homepage(monkeypatch, tmp_path, registered_with_watcher):
    root = 'https://example.test'
    homepage = '<html><p>Unique homepage text.</p><a href="/about">About</a></html>'

    monkeypatch.setattr(db, 'DB_PATH', tmp_path / 'watcher.db')
    monkeypatch.setenv('WPS_ANCHOR_DIR', str(tmp_path / 'anchors'))
    from src import anchor

    monkeypatch.setattr(anchor, 'anchor_hash', lambda *_: (None, None))
    monkeypatch.setattr(crawler, '_HAS_REPPY', False)
    monkeypatch.setattr(crawler, 'fetch_robots', lambda *_: 'User-agent: *\nAllow: /')
    monkeypatch.setattr(crawler, 'parse_sitemap_urls', lambda *_: [])
    monkeypatch.setattr(crawler, 'archive_url', lambda *_: {})
    monkeypatch.setattr(crawler.crypto_asym, 'sign_bytes', lambda *_: None)
    monkeypatch.setattr(crawler.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(
        crawler, 'http_get',
        lambda url, **_: (200, {}, homepage if url == root else '<p>About us.</p>'),
    )

    watcher = crawler.SiteWatcher()
    if registered_with_watcher:
        site_id = watcher.add_site(root)
        with db.get_conn() as conn:
            pages = conn.execute('SELECT url FROM Pages WHERE site_id=?', (site_id,))
            assert {page['url'] for page in pages} == {root, f'{root}/about'}
    else:
        site_id = db.add_site(root, root)
        with db.get_conn() as conn:
            conn.execute(
                'UPDATE Sites SET robots_txt=? WHERE id=?',
                ('User-agent: *\nAllow: /', site_id),
            )

    with db.get_conn() as conn:
        site = conn.execute('SELECT * FROM Sites WHERE id=?', (site_id,)).fetchone()
    watcher.crawl_site(site)

    with db.get_conn() as conn:
        pages = conn.execute('SELECT id, url FROM Pages WHERE site_id=?', (site_id,))
        page_ids = {page['url']: page['id'] for page in pages}
    assert set(page_ids) == {root, f'{root}/about'}
    assert 'Unique homepage text.' in db.latest_page_version(page_ids[root])['content_text']

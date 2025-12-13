import requests
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time
from datetime import datetime
import json
try:
    from reppy.robots import Robots as ReppyRobots
    _HAS_REPPY = True
except Exception:
    from urllib.robotparser import RobotFileParser
    _HAS_REPPY = False

from . import utils
from . import db
from .archivebox_interface import archive_url, get_archived_html
from .http_client import get as http_get
from . import crypto_asym, merkle

USER_AGENT = 'LocalSiteWatcher/1.0 (+https://example.org)'

def fetch_robots(root_url):
    try:
        r = requests.get(urljoin(root_url, '/robots.txt'), timeout=10, headers={'User-Agent': USER_AGENT})
        return r.text
    except Exception:
        return ''

def parse_sitemap_urls(root_url):
    # Try common sitemap locations
    candidates = ['/sitemap.xml', '/sitemap_index.xml']
    found = set()
    for c in candidates:
        try:
            url = urljoin(root_url, c)
            r = requests.get(url, timeout=10, headers={'User-Agent': USER_AGENT})
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.content, 'lxml')
            for loc in soup.find_all('loc'):
                u = loc.text.strip()
                if urlparse(u).netloc.endswith(urlparse(root_url).netloc):
                    found.add(u)
        except Exception:
            continue
    return list(found)

def extract_internal_links(html, base_url, root_netloc, limit=50):
    soup = BeautifulSoup(html, 'lxml')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('mailto:') or href.startswith('tel:'):
            continue
        full = urljoin(base_url, href)
        p = urlparse(full)
        if not p.netloc.endswith(root_netloc):
            continue
        # very basic deny rules
        if any(x in p.path.lower() for x in ['/login', '/admin', '/signup', '/search']):
            continue
        # drop long query strings
        if len(p.query) > 200:
            continue
        links.add(full)
        if len(links) >= limit:
            break
    return list(links)

logger = logging.getLogger(__name__)

class SiteWatcher:
    def __init__(self):
        db.init_db()
        # track last request time per site to respect crawl-delay
        self._last_request_time = {}

    def _get_site_user_agent(self, site_id):
        conn = db.get_conn()
        cur = conn.cursor()
        row = cur.execute('SELECT user_agent FROM Sites WHERE id=?', (site_id,)).fetchone()
        conn.close()
        return row['user_agent'] if row and row['user_agent'] else None

    def add_site(self, url, user_agent=None):
        root = utils.normalize_root(url)
        site_id = db.add_site(url, root, user_agent=user_agent)
        logger.info('Added site %s as id=%s', root, site_id)
        # initial discovery
        sitemap_urls = parse_sitemap_urls(root)
        candidates = set(sitemap_urls)
        # fetch robots.txt and homepage and extract a few internal links
        # prefer using reppy to fetch/parse robots if available
        crawl_delay = 1
        robots_txt = ''
        parser = None
        try:
            if _HAS_REPPY:
                # Reppy can fetch remote robots.txt and parse it
                try:
                    robots_obj = ReppyRobots.fetch(urljoin(root, '/robots.txt'))
                    parser = robots_obj
                    # reppy provides crawl delay via robots_obj.agent(agent).crawl_delay
                except Exception:
                    parser = None
            else:
                robots_txt = fetch_robots(root)
                parser = RobotFileParser()
                parser.parse(robots_txt.splitlines())
                # attempt to read Crawl-delay for our agent
                for line in robots_txt.splitlines():
                    if 'crawl-delay' in line.lower():
                        try:
                            crawl_delay = int(line.split(':', 1)[1].strip())
                        except Exception:
                            pass
        except Exception:
            parser = None
        # update DB with robots and crawl_delay
        conn = db.get_conn()
        conn.execute("UPDATE Sites SET robots_txt=?, crawl_delay=? WHERE id=?", (robots_txt, crawl_delay, site_id))
        conn.commit()
        conn.close()
        try:
            self._maybe_sleep(site_id, crawl_delay)
            # choose user agent: site-specific override or default
            ua = site_id and self._get_site_user_agent(site_id) or USER_AGENT
            logger.info('Fetching homepage %s with UA=%s', root, ua)
            status, resp_headers, body = http_get(root, headers={'User-Agent': ua}, retries=2)
            self._last_request_time[site_id] = time.time()
            if status == 200 and body:
                links = extract_internal_links(body, root, urlparse(root).netloc, limit=30)
                candidates.update(links)
        except Exception as e:
            logger.exception('Error fetching homepage %s: %s', root, e)
        for u in candidates:
            norm = utils.normalize_url(u, urlparse(root).netloc)
            db.upsert_page(site_id, u, norm)
        return site_id

    def crawl_site(self, site_row):
        root = site_row['normalized_root']
        site_id = site_row['id']
        # load robots and crawl_delay
        robots_txt = site_row.get('robots_txt') or ''
        crawl_delay = site_row.get('crawl_delay') or 1
        parser = None
        try:
            if _HAS_REPPY:
                try:
                    parser = ReppyRobots.fetch(urljoin(root, '/robots.txt'))
                except Exception:
                    parser = None
            else:
                parser = RobotFileParser()
                if robots_txt:
                    parser.parse(robots_txt.splitlines())
                else:
                    parser.set_url(urljoin(root, '/robots.txt'))
                    try:
                        parser.read()
                    except Exception:
                        parser = None
        except Exception:
            parser = None
        # refresh candidate list
        sitemap_urls = parse_sitemap_urls(root)
        candidates = set(sitemap_urls)
        try:
            # respect robots and crawl-delay before fetching
            ua = site_row.get('user_agent') or USER_AGENT
            if parser:
                try:
                    if _HAS_REPPY:
                        if not parser.allowed(ua, root):
                            return
                    else:
                        if not parser.can_fetch(ua, root):
                            return
                except Exception:
                    # if robots checking fails, be conservative and proceed
                    pass
            
            self._maybe_sleep(site_id, crawl_delay)
            status, resp_headers, body = http_get(root, headers={'User-Agent': ua}, retries=2)
            self._last_request_time[site_id] = time.time()
            if status == 200 and body:
                links = extract_internal_links(body, root, urlparse(root).netloc, limit=30)
                candidates.update(links)
        except Exception:
            pass
        # upsert pages
        for u in candidates:
            norm = utils.normalize_url(u, urlparse(root).netloc)
            db.upsert_page(site_id, u, norm)
        # archive pending or previously archived pages
        conn = db.get_conn()
        cur = conn.cursor()
        rows = cur.execute("SELECT * FROM Pages WHERE site_id=?", (site_id,)).fetchall()
        for row in rows:
            page_id = row['id']
            url = row['url']
            # check robots for this specific url
            ua = site_row.get('user_agent') or USER_AGENT
            if parser:
                try:
                    if _HAS_REPPY:
                        if not parser.allowed(ua, url):
                            continue
                    else:
                        if not parser.can_fetch(ua, url):
                            continue
                except Exception:
                    pass
            # call ArchiveBox
            try:
                meta = archive_url(url)
            except Exception as e:
                logger.exception('archive_url failed for %s: %s', url, e)
                meta = {}
            # best-effort: get archived time
            archived_at = datetime.utcnow().isoformat()
            # try to locate HTML inside ArchiveBox output if metadata contains path
            # fallback: fetch live content (less ideal)
            html = ''
            # if ArchiveBox returned metadata dict, try to read archived HTML
            if isinstance(meta, dict) and meta:
                try:
                    html, archive_entry = get_archived_html(url)
                except Exception as e:
                    logger.exception('get_archived_html failed for %s: %s', url, e)
                    html, archive_entry = '', {}
            # if no archived HTML available, fall back to conditional live fetch (conservative)
            if not html:
                # try conditional GET using last archived timestamp if available
                lm = None
                if last_ver:
                    lm = last_ver.get('archived_at')
                status, resp_headers, body = http_get(url, headers={'User-Agent': ua}, last_modified=lm, retries=2)
                if status == 200 and body:
                    html = body
                elif status == 304:
                    # not modified
                    db.mark_page_archived(page_id, archived_at)
                    continue
                else:
                    logger.info('No archived HTML and live fetch failed for %s, skipping', url)
                    continue
            try:
                text = utils.extract_readable_text(html)
            except Exception as e:
                logger.exception('Failed to extract readable text for %s: %s', url, e)
                continue
            h = utils.hash_text(text)
            images = utils.extract_image_urls(html, url)
            last_ver = db.latest_page_version(page_id)
            if last_ver and last_ver['content_hash'] == h:
                db.mark_page_archived(page_id, archived_at)
                logger.info('No meaningful change for %s', url)
                continue
            # compute content hash chain (prototype: merkle root of previous and current)
            if last_ver:
                prev_hash = last_ver.get('content_hash') or ''
                chain_root = merkle.merkle_root([prev_hash.encode('utf-8'), h.encode('utf-8')]).hex()
            else:
                chain_root = merkle.merkle_root([h.encode('utf-8')]).hex()
            # sign the content
            try:
                signature = crypto_asym.sign_bytes(text.encode('utf-8'))
            except Exception:
                signature = None
            # include archived entry metadata as provenance if available
            new_vid = db.insert_page_version(site_id, page_id, archived_at, text, h, images, signature=signature, content_hash_chain=chain_root)
            # anchor the content hash and store witness id (best-effort)
            try:
                from .anchor import anchor_hash
                witness, proof_path = anchor_hash(h)
                conn2 = db.get_conn()
                cur2 = conn2.cursor()
                cur2.execute('UPDATE PageVersions SET witness_tx_id=?, proof_path=?, proof_verified=? WHERE id=?', (witness, proof_path, 0, new_vid))
                conn2.commit()
                conn2.close()
            except Exception:
                pass
            # try to store archive provenance (best-effort)
            try:
                if 'archive_entry' in locals() and archive_entry:
                    conn = db.get_conn()
                    cur = conn.cursor()
                    cur.execute('UPDATE PageVersions SET archive_source=? WHERE id=?', (json.dumps(archive_entry), new_vid))
                    conn.commit()
                    conn.close()
            except Exception:
                pass
            logger.info('Stored new PageVersion id=%s for page=%s', new_vid, page_id)
            if last_ver:
                added, removed = utils.compute_diff(last_ver['content_text'], text)
                old_images = []
                try:
                    old_images = json.loads(last_ver['image_urls']) if last_ver['image_urls'] else []
                except Exception:
                    old_images = []
                new_images = [i for i in images if i not in old_images]
                db.insert_change(last_ver['id'], new_vid, added, removed, new_images)
            db.mark_page_archived(page_id, archived_at)
            time.sleep(1)
        conn.close()

    def run_cycle(self):
        conn = db.get_conn()
        cur = conn.cursor()
        sites = cur.execute("SELECT * FROM Sites WHERE active=1").fetchall()
        for s in sites:
            try:
                self.crawl_site(s)
                cur.execute("UPDATE Sites SET last_crawled=? WHERE id=?", (datetime.utcnow().isoformat(), s['id']))
                conn.commit()
            except Exception:
                cur.execute("UPDATE Sites SET status='error' WHERE id=?", (s['id'],))
                conn.commit()
        conn.close()

    def _maybe_sleep(self, site_id, crawl_delay):
        """Ensure we respect per-site crawl_delay by sleeping if needed."""
        last = self._last_request_time.get(site_id)
        if not last:
            return
        elapsed = time.time() - last
        wait = crawl_delay - elapsed
        if wait and wait > 0:
            time.sleep(wait)

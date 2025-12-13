import re
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode
import hashlib
from bs4 import BeautifulSoup
from readability import Document
import json

TRACKING_PARAMS = re.compile(r'^(utm_|fbclid$|gclid$)', re.I)

def normalize_root(url: str) -> str:
    p = urlparse(url)
    scheme = p.scheme or 'https'
    netloc = p.netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    return f"{scheme}://{netloc}"

def normalize_url(url: str, root_netloc: str) -> str:
    p = urlparse(url)
    scheme = p.scheme or 'https'
    netloc = p.netloc.lower()
    path = p.path or '/'
    # drop tracking params
    qs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    query = urlencode(qs)
    # enforce same domain
    if netloc.endswith(root_netloc):
        netloc = root_netloc
    return urlunparse((scheme, netloc, path.rstrip('/') or '/', '', query, ''))

def extract_readable_text(html: str) -> str:
    try:
        doc = Document(html)
        content = doc.summary()
        soup = BeautifulSoup(content, 'lxml')
        text = soup.get_text('\n')
        # collapse whitespace
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        return text
    except Exception:
        # fallback: strip tags
        soup = BeautifulSoup(html, 'lxml')
        text = soup.get_text('\n')
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        return text

def hash_text(text: str) -> str:
    h = hashlib.sha256()
    if isinstance(text, str):
        text = text.encode('utf-8')
    h.update(text)
    return h.hexdigest()

def extract_image_urls(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, 'lxml')
    imgs = []
    for img in soup.find_all('img'):
        src = img.get('src')
        if not src:
            continue
        full = urljoin(base_url, src)
        imgs.append(full)
    # dedupe
    return list(dict.fromkeys(imgs))

def compute_diff(old_text: str, new_text: str) -> (str, str):
    import difflib
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
    added = []
    removed = []
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            added.append(line[1:])
        elif line.startswith('-') and not line.startswith('---'):
            removed.append(line[1:])
    return '\n'.join(added), '\n'.join(removed)

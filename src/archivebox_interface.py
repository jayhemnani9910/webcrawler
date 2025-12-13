import subprocess
import json
import shlex
from typing import Optional
import os
from pathlib import Path
import time

def archive_url(url: str, archivebox_args: Optional[list]=None) -> dict:
    """Call ArchiveBox CLI to archive a single URL. Returns parsed JSON if available, else a minimal dict.

    Requires `archivebox` on PATH. This function uses `archivebox add --json <url>` when available.
    """
    cmd = ["archivebox", "add", "--json", url]
    if archivebox_args:
        cmd = ["archivebox", "add", "--json"] + archivebox_args + [url]
    # run with simple retries to handle transient failures
    last_exc = None
    for attempt in range(3):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, check=True)
            out = p.stdout.strip()
            try:
                return json.loads(out)
            except Exception:
                return {"raw_output": out}
        except subprocess.CalledProcessError as e:
            last_exc = e
            # try without --json as fallback on first failure
            if attempt == 0:
                try:
                    p = subprocess.run(["archivebox", "add", url], capture_output=True, text=True, check=True)
                    return {"raw_output": p.stdout}
                except Exception as e2:
                    last_exc = e2
            # wait briefly before retrying
            import time as _t
            _t.sleep(1 + attempt)
            continue
    return {"error": str(last_exc), "stderr": getattr(last_exc, 'stderr', '')}


def read_archived_html_from_meta(meta: dict, url: str) -> str:
    """Best-effort: given ArchiveBox JSON metadata, try to locate the archived HTML file and return its contents."""
    # Common keys: 'outfile', 'out_path', 'output_path', 'path'
    possible_keys = ['outfile', 'out_path', 'output_path', 'path', 'file', 'output']
    for k in possible_keys:
        v = meta.get(k)
        if not v:
            continue
        p = Path(v)
        if p.is_file():
            try:
                return p.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
    # fallback: try environment variables commonly used with ArchiveBox
    env_dirs = [os.environ.get('ARCHIVEBOX_OUTPUT_DIR'), os.environ.get('ARCHIVEBOX_DIR'), os.environ.get('ARCHIVEBOX')]
    # filter None
    env_dirs = [d for d in env_dirs if d]
    # also check ~/ArchiveBox
    env_dirs.append(str(Path.home() / 'ArchiveBox'))
    for d in env_dirs:
        if not d:
            continue
        pdir = Path(d)
        if not pdir.exists():
            continue
        # search for recent HTML files that include the URL
        for path in pdir.rglob('*.html'):
            try:
                txt = path.read_text(encoding='utf-8', errors='replace')
                if url in txt or url.replace('https://', '').replace('http://', '') in txt:
                    return txt
            except Exception:
                continue
    return ''


def list_archives_json() -> list:
    """Return the list of archive entries as parsed JSON from `archivebox list --json`."""
    # allow user to point to a pre-generated index JSON via env var for deterministic parsing
    # allow config file to provide an index path as well
    idx_path = os.environ.get('ARCHIVEBOX_INDEX_JSON')
    if not idx_path:
        try:
            from .config import get_archive_index
            idx_path = get_archive_index()
        except Exception:
            idx_path = None
    if idx_path:
        try:
            p = Path(idx_path)
            if p.is_file():
                return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    try:
        p = subprocess.run(["archivebox", "list", "--json"], capture_output=True, text=True, check=True)
        out = p.stdout.strip()
        try:
            return json.loads(out)
        except Exception:
            return []
    except Exception:
        return []


def find_archive_entry_for_url(url: str) -> dict:
    """Try to find the best matching archive entry for `url` in ArchiveBox's index."""
    entries = list_archives_json()
    # entries are typically dicts with 'url', 'out_path', 'timestamp' etc.
    # prioritize exact url match, then substring match, then newest
    exact = None
    candidates = []
    for e in entries:
        try:
            u = e.get('url') or e.get('source_url') or ''
            if not u:
                continue
            # normalize slight differences (trailing slash)
            if u.rstrip('/') == url.rstrip('/'):
                exact = e
                break
            if url in u or u in url:
                candidates.append(e)
        except Exception:
            continue
    if exact:
        return exact
    if candidates:
        # pick newest by timestamp if available
        candidates.sort(key=lambda x: x.get('timestamp') or x.get('date') or 0, reverse=True)
        return candidates[0]
    return {}


def get_archived_html(url: str) -> (str, dict):
    """High-level: find an archive entry for url and read its archived HTML if possible.

    Returns (html_text, entry_dict) — entry_dict may be empty if none found.
    """
    entry = find_archive_entry_for_url(url)
    if not entry:
        return '', {}
    # try common fields
    for k in ['outfile', 'out_path', 'output_path', 'path', 'file']:
        v = entry.get(k)
        if v:
            p = Path(v)
            if p.is_file():
                try:
                    return p.read_text(encoding='utf-8', errors='replace'), entry
                except Exception:
                    pass
    # try to get snapshot dir and look for index.html
    out_dir = entry.get('out_dir') or entry.get('output') or entry.get('dir')
    if out_dir:
        pdir = Path(out_dir)
        for candidate in ['index.html', 'out.html', 'snapshot.html']:
            p = pdir / candidate
            if p.is_file():
                try:
                    return p.read_text(encoding='utf-8', errors='replace'), entry
                except Exception:
                    pass
    # fallback to scanning common ArchiveBox output dirs for a file that contains the URL
    html = read_archived_html_from_meta(entry, url)
    return (html, entry) if html else ('', entry)


def archive_and_wait(url: str, timeout: int = 300, poll_interval: int = 5, archivebox_args: Optional[list]=None) -> dict:
    """Request ArchiveBox to archive `url` (best-effort) and poll the ArchiveBox index until an entry appears or timeout.

    Returns the matched archive entry dict on success, or an empty dict on failure/timeout. This function will call
    `archive_url` to request archiving and then repeatedly call `find_archive_entry_for_url` / `list_archives_json` to wait
    for the produced snapshot.
    """
    start = time.time()
    # Attempt to trigger archive (best-effort)
    try:
        archive_url(url, archivebox_args=archivebox_args)
    except Exception:
        # ignore errors from triggering archive; we'll still poll the index in case another process produced it
        pass

    # Poll index until we find an entry or timeout
    while True:
        entry = find_archive_entry_for_url(url)
        if entry:
            return entry
        if time.time() - start > timeout:
            return {}
        time.sleep(poll_interval)

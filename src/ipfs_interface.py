"""IPFS integration wrapper.

Tries in order:
 - HTTP API at http://127.0.0.1:5001 (recommended for daemon)
 - `ipfs` CLI
 - Fallback to local SHA256 placeholder (for tests)
"""
import shutil
import subprocess
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional
import requests
import json

logger = logging.getLogger(__name__)

IPFS_API = (os.environ.get('IPFS_API_HOST', '127.0.0.1'), int(os.environ.get('IPFS_API_PORT', '5001')))


def _has_ipfs_cli() -> bool:
    return shutil.which('ipfs') is not None


def _ipfs_api_url(path: str) -> str:
    host, port = IPFS_API
    return f'http://{host}:{port}{path}'


def add_file(path: str) -> str:
    """Add file to IPFS and return CID. Tries HTTP API, then CLI, then fallback hash."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    # Try HTTP API add
    try:
        url = _ipfs_api_url('/api/v0/add')
        with open(p, 'rb') as fh:
            files = {'file': (p.name, fh)}
            res = requests.post(url, files=files, timeout=10)
        if res.status_code == 200:
            j = res.json()
            return j.get('Hash')
    except Exception:
        pass

    # Try CLI
    if _has_ipfs_cli():
        res = subprocess.run(['ipfs', 'add', '-Q', str(p)], capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()

    # Fallback to hash placeholder. Prefixed so callers can tell this apart from a real CID.
    logger.warning('IPFS daemon/CLI unavailable; add_file(%s) returning a local sha256 placeholder, not a real CID', path)
    data = p.read_bytes()
    return 'sha256-fallback:' + hashlib.sha256(data).hexdigest()


def get_file(cid: str, out_path: Optional[str] = None) -> str:
    """Fetch a file by CID using HTTP API or CLI. Returns path where file is saved.

    If out_path specified, writes file there.
    """
    # Try HTTP API
    try:
        url = _ipfs_api_url(f'/api/v0/cat?arg={cid}')
        res = requests.post(url, timeout=30)
        if res.status_code == 200:
            data = res.content
            if out_path:
                p = Path(out_path)
                p.write_bytes(data)
                return str(p)
            # write to cwd with cid as name
            p = Path(cid)
            p.write_bytes(data)
            return str(p)
    except Exception:
        pass

    # Try CLI
    if _has_ipfs_cli():
        cmd = ['ipfs', 'get', cid]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError('ipfs get failed: ' + res.stderr)
        # ipfs get writes files to cwd; if out_path specified, move it there
        if out_path:
            Path(cid).rename(out_path)
            return out_path
        return cid

    raise RuntimeError('IPFS daemon/CLI not available')


def pin_add(cid: str) -> bool:
    """Pin a CID via HTTP API or CLI. Returns True on success."""
    # HTTP API
    try:
        url = _ipfs_api_url(f'/api/v0/pin/add?arg={cid}')
        res = requests.post(url, timeout=10)
        if res.status_code == 200:
            return True
    except Exception as e:
        logger.debug('pin_add HTTP API unreachable for %s: %s', cid, e)

    if _has_ipfs_cli():
        res = subprocess.run(['ipfs', 'pin', 'add', cid], capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning('pin_add rejected by ipfs CLI for %s: %s', cid, res.stderr)
        return res.returncode == 0

    logger.warning('pin_add(%s) failed: IPFS daemon unreachable and no ipfs CLI available', cid)
    return False

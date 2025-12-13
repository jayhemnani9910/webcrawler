"""OpenTimestamps helper wrapper.

This wrapper tries to use the `ots` CLI (recommended) to stamp a small file
containing the hex hash, and then upgrade/verify it as proofs become available.
The functions are safe to call in environments without the ots tool (they will
return fallback values) so they can be unit-tested.
"""
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import time
import os
import requests
import base64


def _has_ots_cli() -> bool:
    return shutil.which('ots') is not None


def create_temp_file_for_hash(content_hash: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{content_hash}.txt"
    p.write_text(content_hash)
    return p


def stamp_hash(content_hash: str, anchor_dir: Path) -> Optional[str]:
    """Stamp a content hash using the ots CLI. Returns path to .ots file or None.

    This writes a small file containing the hex hash, runs `ots stamp` to produce
    a .ots file and returns its path. If the ots CLI is unavailable, returns None.
    """
    # Prefer local ots CLI if available
    tf = create_temp_file_for_hash(content_hash, anchor_dir)
    if _has_ots_cli():
        try:
            res = subprocess.run(['ots', 'stamp', str(tf)], capture_output=True, text=True)
            if res.returncode == 0:
                ots_path = tf.with_suffix('.ots')
                if ots_path.exists():
                    return str(ots_path)
        except Exception:
            pass

    # If OTSD_URL configured, POST to remote stamping endpoint
    OTSD_URL = os.environ.get('OTSD_URL')
    if OTSD_URL:
        try:
            url = OTSD_URL.rstrip('/') + '/stamp'
            resp = requests.post(url, json={'hash': content_hash}, timeout=10)
            if resp.status_code == 200:
                j = resp.json()
                return j.get('ots_path')
        except Exception:
            pass

    return None


def upgrade_ots(ots_path: str) -> bool:
    """Attempt to upgrade an .ots file to incorporate newly available proofs.
    Returns True on success. Uses ots CLI if present, otherwise will call OTSD_URL /upgrade.
    """
    if _has_ots_cli():
        try:
            res = subprocess.run(['ots', 'upgrade', ots_path], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False

    OTSD_URL = os.environ.get('OTSD_URL')
    if OTSD_URL:
        try:
            url = OTSD_URL.rstrip('/') + '/upgrade'
            resp = requests.post(url, json={'ots_path': ots_path}, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    return False


def fetch_proof(ots_path: str, anchor_dir: Path) -> Optional[bytes]:
    """Fetch proof bytes either from a local path or via OTSD_URL /fetch endpoint.

    Returns raw bytes or None on failure.
    """
    # try local filesystem
    p = Path(ots_path)
    if p.exists():
        try:
            return p.read_bytes()
        except Exception:
            pass

    OTSD_URL = os.environ.get('OTSD_URL')
    if OTSD_URL:
        try:
            url = OTSD_URL.rstrip('/') + '/fetch'
            resp = requests.post(url, json={'ots_path': ots_path}, timeout=10)
            if resp.status_code == 200:
                j = resp.json()
                b64 = j.get('content_b64')
                if b64:
                    return base64.b64decode(b64)
        except Exception:
            pass
    return None


def verify_ots(ots_path: str) -> bool:
    if _has_ots_cli():
        try:
            res = subprocess.run(['ots', 'verify', ots_path], capture_output=True, text=True)
            return res.returncode == 0
        except Exception:
            return False

    OTSD_URL = os.environ.get('OTSD_URL')
    if OTSD_URL:
        try:
            url = OTSD_URL.rstrip('/') + '/verify'
            resp = requests.post(url, json={'ots_path': ots_path}, timeout=10)
            if resp.status_code == 200:
                j = resp.json()
                return j.get('verified', False)
        except Exception:
            return False

    return False

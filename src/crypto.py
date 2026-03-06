"""Lightweight cryptographic helpers (HMAC-based prototype).

This module provides symmetric-key signing/verification to prototype signing and
verification of PageVersion artifacts without requiring heavy native deps.
"""
import os
import hmac
import hashlib
from pathlib import Path

KEY_PATH = Path(os.environ.get('WPS_KEY_PATH', 'keys/hmac.key'))


def ensure_key():
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.exists():
        # generate a 32-byte key
        k = os.urandom(32)
        KEY_PATH.write_bytes(k)
    return KEY_PATH.read_bytes()


def sign_bytes(data: bytes) -> str:
    key = ensure_key()
    sig = hmac.new(key, data, hashlib.sha256).hexdigest()
    return sig


def verify_bytes(data: bytes, sig_hex: str) -> bool:
    key = ensure_key()
    expected = hmac.new(key, data, hashlib.sha256).hexdigest()
    try:
        return hmac.compare_digest(expected, sig_hex)
    except Exception:
        return False

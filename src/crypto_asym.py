"""Asymmetric signing helpers that prefer KMS providers then local keys.

If a KMS provider is available via `src/keys_kms.get_provider()`, use it
for sign/verify operations; otherwise fall back to local Ed25519 keys via
PyNaCl or a file-backed HMAC fallback.
"""
from pathlib import Path
import os
try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import HexEncoder
    _HAS_LIBSODIUM = True
except Exception:
    _HAS_LIBSODIUM = False

KEY_DIR = Path(os.environ.get('WPS_KEY_DIR', 'keys'))
SK_PATH = KEY_DIR / 'ed25519_sk.hex'
VK_PATH = KEY_DIR / 'ed25519_vk.hex'


def ensure_keypair():
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    if _HAS_LIBSODIUM:
        if not SK_PATH.exists() or not VK_PATH.exists():
            sk = SigningKey.generate()
            vk = sk.verify_key
            SK_PATH.write_text(sk.encode(encoder=HexEncoder).decode('utf-8'))
            VK_PATH.write_text(vk.encode(encoder=HexEncoder).decode('utf-8'))
        sk = SigningKey(SK_PATH.read_text().strip(), encoder=HexEncoder)
        vk = sk.verify_key
        return sk, vk
    else:
        # Fallback: use a symmetric HMAC-like key file for signing (not cryptographically the same)
        key_path = KEY_DIR / 'fallback_hmac.key'
        if not key_path.exists():
            key_path.write_bytes(os.urandom(32))
        key = key_path.read_bytes()
        return key


def get_public_key_bytes(key_id: str = None) -> bytes:
    """Return public key bytes for local keypair. If KMS provider is used, this should be adapted to request public key from provider."""
    if _HAS_LIBSODIUM:
        sk, vk = ensure_keypair()
        return vk.encode()
    else:
        # fallback: return a deterministic value derived from HMAC key
        kp = ensure_keypair()
        import hashlib
        return hashlib.sha256(kp).digest()


def verify_with_public_key(data: bytes, sig_hex: str, pub_bytes: bytes) -> bool:
    """Verify a signature against an explicit public key (bytes).

    Supports Ed25519 VerifyKey if libsodium available; otherwise attempts HMAC compare.
    """
    if _HAS_LIBSODIUM:
        try:
            from nacl.signing import VerifyKey
            vk = VerifyKey(pub_bytes)
            vk.verify(data, bytes.fromhex(sig_hex))
            return True
        except Exception:
            return False
    else:
        # fallback: libsodium not available — delegate to verify_bytes which
        # implements the same HMAC-based fallback used for signing.
        try:
            return verify_bytes(data, sig_hex)
        except Exception:
            return False


def _get_kms_provider():
    try:
        from .keys_kms import get_provider
        return get_provider()
    except Exception:
        return None


def sign_bytes(data: bytes) -> str:
    # Prefer KMS provider if available
    provider = _get_kms_provider()
    key_id = os.environ.get('WPS_KMS_KEY_ID') or os.environ.get('AWS_KMS_KEY_ID')
    if provider and key_id:
        try:
            sig = provider.sign(key_id, data)
            # provider.sign may return bytes
            return sig.hex() if isinstance(sig, (bytes, bytearray)) else sig
        except Exception:
            pass
    # local fallback
    kp = ensure_keypair()
    if _HAS_LIBSODIUM:
        sk, vk = kp
        sig = sk.sign(data).signature
        return sig.hex()
    else:
        # fallback: HMAC-SHA256 hex
        import hmac, hashlib
        key = kp
        return hmac.new(key, data, hashlib.sha256).hexdigest()


def verify_bytes(data: bytes, sig_hex: str) -> bool:
    # Prefer KMS provider verify if available
    provider = _get_kms_provider()
    key_id = os.environ.get('WPS_KMS_KEY_ID') or os.environ.get('AWS_KMS_KEY_ID')
    if provider and key_id:
        try:
            # provider.verify should return True/False
            return provider.verify(key_id, data, bytes.fromhex(sig_hex) if isinstance(sig_hex, str) else sig_hex)
        except Exception:
            pass
    kp = ensure_keypair()
    if _HAS_LIBSODIUM:
        sk, vk = kp
        try:
            vk.verify(data, bytes.fromhex(sig_hex))
            return True
        except Exception:
            return False
    else:
        import hmac, hashlib
        key = kp
        expected = hmac.new(key, data, hashlib.sha256).hexdigest()
        try:
            return hmac.compare_digest(expected, sig_hex)
        except Exception:
            return False

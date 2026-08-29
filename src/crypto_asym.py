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


def ensure_keypair(key_id: str = None):
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(KEY_DIR, 0o700)
    # key_id=None keeps using the original default filenames (SK_PATH/VK_PATH)
    # so the node's default identity is unchanged; a given key_id gets its own
    # persisted keypair so distinct key_ids resolve to distinct keys.
    if key_id:
        sk_path = KEY_DIR / f'ed25519_sk_{key_id}.hex'
        vk_path = KEY_DIR / f'ed25519_vk_{key_id}.hex'
        hmac_path = KEY_DIR / f'fallback_hmac_{key_id}.key'
    else:
        sk_path = SK_PATH
        vk_path = VK_PATH
        hmac_path = KEY_DIR / 'fallback_hmac.key'
    if _HAS_LIBSODIUM:
        if not sk_path.exists() or not vk_path.exists():
            sk = SigningKey.generate()
            vk = sk.verify_key
            sk_path.write_text(sk.encode(encoder=HexEncoder).decode('utf-8'))
            vk_path.write_text(vk.encode(encoder=HexEncoder).decode('utf-8'))
        os.chmod(sk_path, 0o600)
        sk = SigningKey(sk_path.read_text().strip(), encoder=HexEncoder)
        vk = sk.verify_key
        return sk, vk
    else:
        # Fallback: use a symmetric HMAC-like key file for signing (not cryptographically the same)
        if not hmac_path.exists():
            hmac_path.write_bytes(os.urandom(32))
        os.chmod(hmac_path, 0o600)
        key = hmac_path.read_bytes()
        return key


def get_public_key_bytes(key_id: str = None) -> bytes:
    """Return public key bytes for local keypair. If KMS provider is used, this should be adapted to request public key from provider."""
    if _HAS_LIBSODIUM:
        sk, vk = ensure_keypair(key_id)
        return vk.encode()
    else:
        # fallback: return a deterministic value derived from HMAC key
        kp = ensure_keypair(key_id)
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
        # fallback: libsodium not available. Signing degrades to symmetric HMAC,
        # and an HMAC cannot be checked against somebody else's public key.
        # Delegating to verify_bytes here checked the signature against OUR OWN
        # key and ignored pub_bytes entirely, so a signature made by any other
        # party verified as valid. Refuse instead of answering wrongly.
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

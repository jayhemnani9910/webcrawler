"""KMS/HSM adapter scaffolds.

This module provides a simple adapter interface for key operations. It tries to
use AWS KMS (via boto3) or HashiCorp Vault (hvac) if configured via environment
variables. If no provider is configured, falls back to file-backed keys (safe
for prototypes only).
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class KMSProvider:
    def sign(self, key_id: str, data: bytes) -> bytes:
        raise NotImplementedError()

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        raise NotImplementedError()


class FileKeyProvider(KMSProvider):
    def __init__(self, keys_dir: Optional[str] = None):
        self.keys_dir = Path(keys_dir or os.environ.get('WPS_KEYS_DIR', 'keys'))
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, key_id: str) -> Path:
        return self.keys_dir / f"{key_id}.key"

    def sign(self, key_id: str, data: bytes) -> bytes:
        path = self._key_path(key_id)
        if not path.exists():
            raise FileNotFoundError(f'Key {key_id} not found at {path}')
        # naive HMAC-style file-backed signature (for prototype only)
        import hmac, hashlib
        key = path.read_bytes()
        return hmac.new(key, data, hashlib.sha256).digest()

    def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
        import hmac, hashlib
        key = self._key_path(key_id).read_bytes()
        expected = hmac.new(key, data, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


def get_provider() -> KMSProvider:
    # Prefer AWS KMS if AWS_KMS_KEY_ID and boto3 available
    try:
        import boto3
        AWS_KEY = os.environ.get('AWS_KMS_KEY_ID')
        if AWS_KEY:
            # Minimal adapter wrapping boto3 KMS sign/verify
            class AWSKMSProvider(KMSProvider):
                def __init__(self):
                    self.client = boto3.client('kms')

                def sign(self, key_id: str, data: bytes) -> bytes:
                    resp = self.client.sign(KeyId=key_id, Message=data, MessageType='RAW', SigningAlgorithm='ECDSA_SHA_256')
                    return resp['Signature']

                def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
                    resp = self.client.verify(KeyId=key_id, Message=data, Signature=signature, MessageType='RAW', SigningAlgorithm='ECDSA_SHA_256')
                    return resp.get('SignatureValid', False)

            logger.info('Using AWS KMS provider')
            return AWSKMSProvider()
    except Exception:
        pass

    # Prefer Vault if configured and hvac available
    try:
        import hvac
        VAULT_ADDR = os.environ.get('VAULT_ADDR')
        VAULT_TOKEN = os.environ.get('VAULT_TOKEN')
        if VAULT_ADDR and VAULT_TOKEN:
            class VaultProvider(KMSProvider):
                def __init__(self):
                    self.client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN)

                def sign(self, key_id: str, data: bytes) -> bytes:
                    # This is a placeholder: implementation depends on transit engine
                    resp = self.client.secrets.transit.sign_data(name=key_id, hash=data.hex())
                    return bytes.fromhex(resp['data']['signature'])

                def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
                    # Placeholder
                    return True

            logger.info('Using Vault KMS provider')
            return VaultProvider()
    except Exception:
        pass

    logger.info('No cloud KMS detected; using file-backed keys')
    return FileKeyProvider()

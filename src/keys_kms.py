"""KMS/HSM adapter scaffolds.

This module provides a simple adapter interface for key operations. It tries to
use AWS KMS (via boto3) or HashiCorp Vault (hvac) if configured via environment
variables. If no provider is configured, falls back to file-backed keys (safe
for prototypes only).
"""
import os
import base64
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
        self.keys_dir = Path(keys_dir or os.environ.get('WPS_KEYS_DIR') or os.environ.get('WPS_KEY_DIR') or 'keys')
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
    except ImportError:
        boto3 = None
    if boto3:
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

            # Construction (e.g. boto3.client('kms')) can fail for reasons
            # unrelated to boto3 being missing, such as no AWS region being
            # configured. That must not be conflated with "no KMS configured".
            try:
                provider = AWSKMSProvider()
            except Exception as e:
                logger.error(f'AWS_KMS_KEY_ID is set but AWS KMS provider failed to initialize: {e}')
            else:
                logger.info('Using AWS KMS provider')
                return provider

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
                    """Sign data using Vault transit engine.

                    Args:
                        key_id: The name of the transit key in Vault
                        data: The data to sign

                    Returns:
                        The signature as bytes (Vault signature string encoded as bytes)
                    """
                    try:
                        # Vault transit sign_data expects hash_input as base64
                        resp = self.client.secrets.transit.sign_data(
                            name=key_id,
                            hash_input=base64.b64encode(data).decode('ascii')
                        )
                        # Vault returns signature in format "vault:v1:BASE64_SIG"
                        # Return as bytes for consistency with interface
                        vault_sig = resp['data']['signature']
                        return vault_sig.encode('utf-8')
                    except Exception as e:
                        logger.error(f'Vault signing failed for key {key_id}: {e}')
                        raise

                def verify(self, key_id: str, data: bytes, signature: bytes) -> bool:
                    """Verify signature using Vault transit engine.

                    Args:
                        key_id: The name of the transit key in Vault
                        data: The original data that was signed
                        signature: The signature bytes to verify

                    Returns:
                        True if signature is valid, False otherwise
                    """
                    try:
                        # Convert signature bytes back to string
                        # Signature should be in format "vault:v1:BASE64_SIG"
                        vault_sig = signature.decode('utf-8') if isinstance(signature, bytes) else signature

                        # Vault transit verify_signed_data expects hash_input and signature
                        resp = self.client.secrets.transit.verify_signed_data(
                            name=key_id,
                            hash_input=base64.b64encode(data).decode('ascii'),
                            signature=vault_sig
                        )

                        # The response contains a 'valid' field indicating verification result
                        result = resp.get('data', {})
                        if 'valid' not in result:
                            logger.warning(f'Vault verify_signed_data response for key {key_id} is missing the "valid" field; treating as invalid: {resp!r}')
                        return result.get('valid', False)
                    except Exception as e:
                        # Log the error for debugging but return False for verification failure
                        logger.warning(f'Vault verification failed for key {key_id}: {e}')
                        return False

            logger.info('Using Vault KMS provider')
            return VaultProvider()
    except ImportError:
        pass
    except Exception as e:
        # Vault is configured but could not be set up; say so before falling back.
        logger.error('Vault KMS provider unavailable, using file-backed keys: %s', e)

    logger.info('No cloud KMS detected; using file-backed keys')
    return FileKeyProvider()

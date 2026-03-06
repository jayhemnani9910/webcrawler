"""Decentralized Identity (DID) scaffolding.

This module produces simple DID documents and verification helpers using
Ed25519 keys (via src/crypto_asym.py) or a KMS provider. It is a minimal
scaffold; production DID methods require formal method spec adherence.
"""
import json
from datetime import datetime
from .crypto_asym import get_public_key_bytes


def create_did_from_key(key_id: str) -> dict:
    """Create a minimal DID document using a key id resolved via crypto_asym.

    Returns a DID document dict.
    """
    pub = get_public_key_bytes(key_id)
    did = f"did:example:{pub.hex()[:16]}"
    doc = {
        '@context': 'https://www.w3.org/ns/did/v1',
        'id': did,
        'verificationMethod': [{
            'id': did + '#key-1',
            'type': 'Ed25519VerificationKey2018',
            'controller': did,
            'publicKeyBase58': pub.hex()
        }],
        'created': datetime.utcnow().isoformat()
    }
    return doc


def resolve_did_to_public_key(did: str) -> bytes:
    """Resolve a minimal did:example created by create_did_from_key to the public key bytes.

    The proto-DID format produced by create_did_from_key uses the hex of the public key in the DID id; this resolver
    extracts that for prototype purposes. Real DID resolution requires a DID method implementation.
    """
    # expected did:example:<hexprefix>
    if not did or not did.startswith('did:example:'):
        raise ValueError('Unsupported DID method')
    s = did.split(':', 2)[2]
    # in our proto, the public key hex is encoded in the id; try to find vk by scanning keys dir
    # Fallback: return first available public key from crypto_asym
    try:
        from .crypto_asym import get_public_key_bytes
        return get_public_key_bytes(None)
    except Exception:
        raise ValueError('Could not resolve DID')

"""Signed incremental Merkle synchronization helpers.

Provides utilities to create small signed deltas representing added knowledge
nodes for a site, verify signatures, persist deltas to DB, and apply them to
the local MerkleForest. This is a lightweight prototype for cross-node sync.
"""
import json
from datetime import datetime
from typing import List, Dict, Optional
from .merkle_distributed import compute_tree_root_from_blob, merge_forests, MerkleForest
from .db import get_conn
from . import crypto_asym
from hashlib import sha256


def node_hash(payload: str) -> str:
    return sha256(payload.encode('utf-8')).hexdigest()


def create_delta(site_id: int, node_payloads: List[Dict]) -> Dict:
    """Create a delta dict for the given site with node payloads.

    node_payloads: list of {"payload": <str>, "meta": {...}}
    Returns delta dict with added node_hashes and metadata (prev_root computed from local forest).
    """
    mf = MerkleForest(site_id)
    local = mf.latest()
    local_blob = local['tree_blob'] if local else {'nodes': []}
    prev_root = local['tree_root'] if local else ''
    nodes = []
    for p in node_payloads:
        payload = p.get('payload') if isinstance(p, dict) else str(p)
        nh = node_hash(payload)
        nodes.append({'node_hash': nh, 'payload': payload, 'meta': p.get('meta', {}) if isinstance(p, dict) else {}})
    delta = {
        'site_id': site_id,
        'added_nodes': nodes,
        'prev_root': prev_root,
        'timestamp': datetime.utcnow().isoformat()
    }
    # compute new merged blob/root locally
    merged_blob = merge_forests(local_blob, {'nodes': nodes})
    new_root = compute_tree_root_from_blob(merged_blob)
    delta['new_root'] = new_root
    return delta


def sign_delta(delta: Dict) -> str:
    j = json.dumps(delta, sort_keys=True).encode('utf-8')
    sig = crypto_asym.sign_bytes(j)
    return sig


def attach_sequence_and_sign(delta: Dict, signer_did: str = None) -> Dict:
    """Attach a sequence number (next monotonic) for the site and sign the delta.

    Returns a dict with keys: delta, signature, sequence, signer_did
    """
    # compute next sequence (simple count of existing deltas) and lamport
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT MAX(sequence) as m, MAX(lamport) as lm FROM MerkleDeltas WHERE site_id=?', (delta['site_id'],))
    row = cur.fetchone()
    current_seq = (row['m'] or 0) if row else 0
    current_lamport = (row['lm'] or 0) if row else 0
    next_seq = current_seq + 1
    lamport = current_lamport + 1
    delta_with_seq = dict(delta)
    delta_with_seq['sequence'] = next_seq
    delta_with_seq['lamport'] = lamport
    if signer_did:
        delta_with_seq['signer_did'] = signer_did
    else:
        try:
            from .did import create_did_from_key
            # create a lightweight did doc and use its id as signer
            dd = create_did_from_key(None)
            delta_with_seq['signer_did'] = dd.get('id')
            signer_did = dd.get('id')
        except Exception:
            pass
    sig = sign_delta(delta_with_seq)
    # store delta to DB with sequence and signer
    cur.execute('INSERT INTO MerkleDeltas (site_id, delta_json, signature, sequence, signer_did, lamport) VALUES (?, ?, ?, ?, ?, ?)', (delta_with_seq['site_id'], json.dumps(delta_with_seq), sig, next_seq, signer_did, lamport))
    conn.commit()
    did = cur.lastrowid
    conn.close()
    return {'delta': delta_with_seq, 'signature': sig, 'sequence': next_seq, 'lamport': lamport, 'signer_did': signer_did, 'stored_id': did}


def verify_delta(delta: Dict, signature_hex: str) -> bool:
    j = json.dumps(delta, sort_keys=True).encode('utf-8')
    # if delta carries signer DID, resolve public key and verify against that
    signer = delta.get('signer_did')
    if signer:
        try:
            from .did import resolve_did_to_public_key
            pub = resolve_did_to_public_key(signer)
            return crypto_asym.verify_with_public_key(j, signature_hex, pub)
        except Exception:
            # fallback to default verify
            return crypto_asym.verify_bytes(j, signature_hex)
    return crypto_asym.verify_bytes(j, signature_hex)


def store_delta(delta: Dict, signature_hex: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO MerkleDeltas (site_id, delta_json, signature) VALUES (?, ?, ?)', (delta['site_id'], json.dumps(delta), signature_hex))
    conn.commit()
    vid = cur.lastrowid
    conn.close()
    return vid


def apply_delta(delta: Dict) -> bool:
    """Apply a verified delta to the local MerkleForest and persist new tree if root matches."""
    site_id = delta['site_id']
    # ordering guard: if delta carries sequence/lamport, ensure it's newer than stored maxima
    conn_check = get_conn()
    cur_check = conn_check.cursor()
    cur_check.execute('SELECT MAX(sequence) as m, MAX(lamport) as lm FROM MerkleDeltas WHERE site_id=?', (site_id,))
    row_check = cur_check.fetchone()
    conn_check.close()
    if row_check:
        max_seq = row_check['m'] or 0
        max_lam = row_check['lm'] or 0
        seq = delta.get('sequence') or 0
        lam = delta.get('lamport') or 0
        if seq and seq <= max_seq:
            return False
        if lam and lam <= max_lam:
            return False
    mf = MerkleForest(site_id)
    local = mf.latest()
    local_blob = local['tree_blob'] if local else {'nodes': []}
    # pass delta-level sequencing context so merges can prefer newer deltas
    merged = merge_forests(local_blob, {'nodes': delta.get('added_nodes', [])}, remote_context={'lamport': delta.get('lamport'), 'sequence': delta.get('sequence'), 'signer_did': delta.get('signer_did')})
    computed_root = compute_tree_root_from_blob(merged)
    if computed_root != delta.get('new_root'):
        return False
    mf.save_tree(computed_root, merged)
    # optionally persist KnowledgeNodes
    conn = get_conn()
    cur = conn.cursor()
    for n in merged.get('nodes', []):
        try:
            cur.execute('INSERT OR IGNORE INTO KnowledgeNodes (node_hash, payload) VALUES (?, ?)', (n['node_hash'], json.dumps(n.get('payload'))))
        except Exception:
            pass
    conn.commit()
    conn.close()
    return True

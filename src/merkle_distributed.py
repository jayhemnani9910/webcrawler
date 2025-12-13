"""Distributed merkle utilities and MerkleForest manager.

This module provides primitives for merging Merkle trees across nodes,
storing per-site merkle forest entries in SQLite (via src/db.get_conn), and
helpers to compute/compare roots for synchronization.

Note: This is a synchronization scaffolding — production-grade conflict
resolution, sharding, and consistency guarantees require a design review.
"""
from hashlib import sha256
import json
from datetime import datetime
from .db import get_conn
from typing import List, Optional


def merkle_hash(data: bytes) -> bytes:
    return sha256(data).digest()


def merkle_root(leaves: List[bytes]) -> bytes:
    if not leaves:
        return merkle_hash(b'')
    nodes = [merkle_hash(l) for l in leaves]
    while len(nodes) > 1:
        next_nodes = []
        for i in range(0, len(nodes), 2):
            a = nodes[i]
            b = nodes[i+1] if i+1 < len(nodes) else a
            next_nodes.append(merkle_hash(a + b))
        nodes = next_nodes
    return nodes[0]


class MerkleForest:
    """Manage a simple per-site Merkle forest stored in SQLite."""
    def __init__(self, site_id: int):
        self.site_id = site_id

    def save_tree(self, root: str, tree_blob: dict):
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute("INSERT INTO MerkleForest (site_id, tree_root, tree_blob, last_updated) VALUES (?, ?, ?, ?)", (self.site_id, root, json.dumps(tree_blob), now))
        conn.commit()
        conn.close()

    def latest(self) -> Optional[dict]:
        conn = get_conn()
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM MerkleForest WHERE site_id=? ORDER BY last_updated DESC LIMIT 1", (self.site_id,)).fetchone()
        conn.close()
        if not row:
            return None
        return {'id': row['id'], 'site_id': row['site_id'], 'tree_root': row['tree_root'], 'tree_blob': json.loads(row['tree_blob']), 'last_updated': row['last_updated']}


def merge_forests(local_blob: dict, remote_blob: dict, remote_context: dict = None) -> dict:
    """Deterministic merge:

    - Deduplicate nodes by `node_hash`.
    - If the same `node_hash` appears with different payloads, record a conflict entry
      in `conflicts` and prefer the local node by default.
    - Return merged blob containing `nodes` (deterministically sorted by node_hash)
      and optional `conflicts` list.
    """
    local_nodes = {n['node_hash']: n for n in local_blob.get('nodes', [])}
    conflicts = []
    for n in remote_blob.get('nodes', []):
        nh = n.get('node_hash')
        if nh in local_nodes:
            # detect payload mismatch for identical node_hash (very unlikely unless hash collision)
            local_payload = local_nodes[nh].get('payload')
            remote_payload = n.get('payload')
            if json.dumps(local_payload) != json.dumps(remote_payload):
                # decide winner using remote_context lamport/sequence if available
                winner = 'local'
                if remote_context:
                    try:
                        r_lam = int(remote_context.get('lamport') or 0)
                    except Exception:
                        r_lam = 0
                    try:
                        l_lam = int(local_nodes[nh].get('meta', {}).get('lamport') or 0)
                    except Exception:
                        l_lam = 0
                    if r_lam > l_lam:
                        winner = 'remote'
                    elif r_lam == l_lam:
                        # tie-breaker: use sequence if provided
                        try:
                            r_seq = int(remote_context.get('sequence') or 0)
                        except Exception:
                            r_seq = 0
                        try:
                            l_seq = int(local_nodes[nh].get('meta', {}).get('sequence') or 0)
                        except Exception:
                            l_seq = 0
                        if r_seq > l_seq:
                            winner = 'remote'
                conflicts.append({'node_hash': nh, 'local_payload': local_payload, 'remote_payload': remote_payload, 'winner': winner})
                if winner == 'remote':
                    # attach remote meta if present
                    local_nodes[nh] = n
            # else payloads identical => nothing to do
        else:
            local_nodes[nh] = n
    # deterministic ordering: sort by node_hash hex
    merged_nodes = [local_nodes[k] for k in sorted(local_nodes.keys())]
    merged_blob = {'nodes': merged_nodes, 'merged_at': datetime.utcnow().isoformat()}
    if conflicts:
        merged_blob['conflicts'] = conflicts
    return merged_blob


def compute_tree_root_from_blob(blob: dict) -> str:
    leaves = [b.encode('utf-8') for b in sorted([n['node_hash'] for n in blob.get('nodes', [])])]
    r = merkle_root(leaves).hex()
    return r

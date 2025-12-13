"""Simple Merkle tree utilities for content-hash registry.

Provides deterministic Merkle root computation and simple proof generation.
"""
import hashlib
from typing import List, Tuple


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def merkle_root(leaves: List[bytes]) -> bytes:
    """Compute Merkle root from list of leaf bytes.

    If no leaves, returns b''.
    """
    if not leaves:
        return b''
    nodes = [sha256(l) for l in leaves]
    while len(nodes) > 1:
        next_nodes = []
        for i in range(0, len(nodes), 2):
            a = nodes[i]
            b = nodes[i+1] if i+1 < len(nodes) else nodes[i]
            next_nodes.append(sha256(a + b))
        nodes = next_nodes
    return nodes[0]


def merkle_proof(leaves: List[bytes], index: int) -> List[bytes]:
    """Return list of sibling hashes required to prove leaf at index.

    Proof order: sibling at each level.
    """
    if not leaves:
        return []
    nodes = [sha256(l) for l in leaves]
    proof = []
    idx = index
    while len(nodes) > 1:
        next_nodes = []
        for i in range(0, len(nodes), 2):
            a = nodes[i]
            b = nodes[i+1] if i+1 < len(nodes) else nodes[i]
            next_nodes.append(sha256(a + b))
            if i == idx ^ 1 or (i+1 == idx):
                pass
        # sibling selection
        sibling_index = idx ^ 1
        if sibling_index < len(nodes):
            proof.append(nodes[sibling_index])
        else:
            proof.append(nodes[idx])
        idx = idx // 2
        nodes = next_nodes
    return proof


def verify_proof(leaf: bytes, proof: List[bytes], root: bytes, index: int) -> bool:
    h = sha256(leaf)
    idx = index
    for sib in proof:
        if idx % 2 == 0:
            h = sha256(h + sib)
        else:
            h = sha256(sib + h)
        idx = idx // 2
    return h == root

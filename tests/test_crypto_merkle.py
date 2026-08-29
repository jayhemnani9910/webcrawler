import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import crypto, merkle, merkle_distributed

# Independently computed (plain hashlib, pairwise-SHA256, no project code) root
# for leaves [b'a', b'b', b'c', b'd']. Checking against this fixed value, rather
# than only a self-generated root, would catch a pairing-order bug shared across
# merkle_root/merkle_proof/verify_proof.
EXPECTED_ROOT_ABCD = '14ede5e8e97ad9372327728f5099b95604a39593cac3bd38a343ad76205213e7'


def test_sign_and_verify():
    data = b'hello world'
    sig = crypto.sign_bytes(data)
    assert crypto.verify_bytes(data, sig)
    assert not crypto.verify_bytes(b'other', sig)


def test_merkle_root_and_proof():
    leaves = [b'a', b'b', b'c', b'd']
    root = merkle.merkle_root(leaves)
    assert isinstance(root, bytes) and len(root) == 32
    assert root.hex() == EXPECTED_ROOT_ABCD
    proof = merkle.merkle_proof(leaves, 2)
    # verify_proof should work for leaf index 2
    assert merkle.verify_proof(b'c', proof, root, 2)


def test_merkle_distributed_root_matches_merkle_root():
    # merkle_sync.py's cross-node delta/forest root anchors on
    # merkle_distributed.merkle_root, a separately written function with the
    # same name and near-identical logic as merkle.merkle_root. Nothing else
    # in the suite calls it directly, so a divergence (e.g. a wrong pairing
    # order fixed in one copy but not the other) would go unnoticed.
    leaves = [b'a', b'b', b'c', b'd']
    root = merkle_distributed.merkle_root(leaves)
    assert root.hex() == EXPECTED_ROOT_ABCD

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src import crypto, merkle


def test_sign_and_verify():
    data = b'hello world'
    sig = crypto.sign_bytes(data)
    assert crypto.verify_bytes(data, sig)
    assert not crypto.verify_bytes(b'other', sig)


def test_merkle_root_and_proof():
    leaves = [b'a', b'b', b'c', b'd']
    root = merkle.merkle_root(leaves)
    assert isinstance(root, bytes) and len(root) == 32
    proof = merkle.merkle_proof(leaves, 2)
    # verify_proof should work for leaf index 2
    assert merkle.verify_proof(b'c', proof, root, 2)

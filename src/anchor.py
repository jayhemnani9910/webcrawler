"""Anchoring prototype: try OpenTimestamps (ots) if available, else create local anchor files.

Provides `anchor_hash(content_hash)` which returns a witness id string that can be stored
in the DB (witness_tx_id). This is a prototype; production should use OpenTimestamps server
or direct blockchain anchoring services.
"""
import os
import time
from pathlib import Path
from . import anchor_ots


ANCHOR_DIR = Path(os.environ.get('WPS_ANCHOR_DIR', 'anchors'))
ANCHOR_DIR.mkdir(parents=True, exist_ok=True)


def anchor_hash(content_hash: str) -> str:
    """Anchor a content hash; return a witness id.

    This will attempt to create an OpenTimestamps (.ots) proof using the `ots`
    CLI (via `src/anchor_ots.py`). If unavailable, a local anchor file is created
    and its path returned. The returned string is suitable for storing in the DB
    as `witness_tx_id` (it may be a filesystem path or an ots filename).
    """
    # Try OTS stamp via CLI wrapper
    ots_path = anchor_ots.stamp_hash(content_hash, ANCHOR_DIR)
    local_proof_path = None
    witness = None
    if ots_path:
        # stamp_hash returned an ots path or identifier; try to fetch proof bytes and persist locally
        proof_bytes = anchor_ots.fetch_proof(ots_path, ANCHOR_DIR)
        if proof_bytes:
            ts = int(time.time())
            fname = ANCHOR_DIR / f"ots.remote.{content_hash}.{ts}.ots"
            with open(fname, 'wb') as f:
                f.write(proof_bytes)
            local_proof_path = str(fname)
        # use ots_path as witness id if provided
        witness = str(ots_path)

    # If we didn't obtain an OTS proof, create a local anchor file
    if not local_proof_path:
        ts = int(time.time())
        fname = ANCHOR_DIR / f"anchor.{content_hash}.{ts}.txt"
        with open(fname, 'w') as f:
            f.write(f"anchor:{content_hash}\ncreated:{ts}\n")
        local_proof_path = str(fname)
    return (witness, local_proof_path)

"""Multi-chain anchoring scaffolds: Bitcoin, Ethereum, Arweave.

These functions are placeholders that record anchor intents and produce a
local witness identifier. Real on-chain anchoring requires broadcasting
transactions and monitoring confirmations; that logic is intentionally
left to operator integration and dedicated modules.
"""
import logging
from pathlib import Path
import time
from .db import get_conn

logger = logging.getLogger(__name__)


def anchor_bitcoin(content_hash: str, anchor_dir: Path) -> str:
    # Placeholder: create a local record indicating intent and return a witness id
    ts = int(time.time())
    fname = anchor_dir / f"btc.{content_hash}.{ts}.anchor"
    fname.write_text(f"bitcoin_anchor:{content_hash}\ncreated:{ts}\n")
    return str(fname)


def anchor_ethereum(content_hash: str, anchor_dir: Path) -> str:
    ts = int(time.time())
    fname = anchor_dir / f"eth.{content_hash}.{ts}.anchor"
    fname.write_text(f"ethereum_anchor:{content_hash}\ncreated:{ts}\n")
    return str(fname)


def anchor_arweave(content_hash: str, anchor_dir: Path) -> str:
    ts = int(time.time())
    fname = anchor_dir / f"ar.{content_hash}.{ts}.anchor"
    fname.write_text(f"arweave_anchor:{content_hash}\ncreated:{ts}\n")
    return str(fname)

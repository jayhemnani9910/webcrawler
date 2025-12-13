"""libp2p adapter scaffold.

This module tries to import a Python libp2p implementation and expose a simple
P2PNode class compatible with the existing `src/p2p.py` messaging API. If the
library is not available, a stub implementation is provided that logs guidance
for operators to install a libp2p implementation or run a Go/JS libp2p relay.

Note: python libp2p implementations are experimental; production deployments
may prefer using an external libp2p relay written in Go/JS and communicate
over a simple protocol (gRPC/HTTP) instead.
"""
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


try:
    # Attempt to import a python libp2p package (community implementations vary)
    from libp2p import new_node  # type: ignore
    _HAS_LIBP2P = True
except Exception:
    _HAS_LIBP2P = False


class P2PNode:
    def __init__(self, listen_multiaddr: Optional[str] = None):
        self.listen_multiaddr = listen_multiaddr
        self.node = None

    async def start(self):
        if not _HAS_LIBP2P:
            logger.warning('libp2p python package not installed; P2P disabled.\n'
                           'Install a libp2p implementation or run an external relay.')
            return
        # Example API — real code depends on chosen libp2p implementation
        self.node = await new_node(listen_multiaddr=self.listen_multiaddr)

    async def stop(self):
        if self.node:
            await self.node.close()

    async def send_message(self, peer_id: str, topic: str, payload: bytes) -> bool:
        if not _HAS_LIBP2P:
            logger.debug('send_message stub called; libp2p not installed.')
            return False
        # Implementation depends on libp2p API
        await self.node.send_message(peer_id, topic, payload)
        return True

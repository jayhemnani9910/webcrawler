"""Gossip protocol scaffolding for global change propagation.

This module provides a simple asynchronous gossip publisher/subscriber that
uses the libp2p relay HTTP bridge if available (/publish endpoint), and falls
back to direct HTTP POSTs to configured peers. This is a best-effort
scaffolding for rapid prototyping; production-grade gossip needs a libp2p
implementation or another robust pubsub transport.
"""
import asyncio
import json
import logging
from typing import List, Callable, Optional
import requests

logger = logging.getLogger(__name__)


class GossipNode:
    def __init__(self, peers: Optional[List[str]] = None, relay_url: Optional[str] = None):
        self.peers = peers or []
        self.relay_url = relay_url  # e.g., http://libp2p-relay:15000/publish

    async def publish(self, topic: str, message: dict) -> bool:
        payload = {'topic': topic, 'message': message}
        # try relay if configured
        if self.relay_url:
            try:
                res = requests.post(self.relay_url, json=payload, timeout=5)
                if res.status_code == 200:
                    return True
            except Exception as e:
                logger.debug('Relay publish failed: %s', e)
        # fallback: POST to peers
        for p in self.peers:
            try:
                url = p.rstrip('/') + '/gossip'
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                logger.debug('Peer publish failed to %s: %s', p, e)
        return True

    async def run_listener(self, host: str = '0.0.0.0', port: int = 17000, handler: Optional[Callable] = None):
        # Minimal listener using asyncio's TCP server is left as a placeholder
        # For now we recommend using an HTTP endpoint in `src/ui.py` to accept gossip messages.
        logger.info('GossipNode.listener placeholder started; use /api/gossip HTTP endpoint for now')
        while True:
            await asyncio.sleep(60)

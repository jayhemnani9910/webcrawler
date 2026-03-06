"""Simple gossip/broadcast prototype using P2PNode send API.
"""
import asyncio
import json
from .p2p import P2PNode


async def _send_to_peer(host, port, message):
    node = P2PNode()
    return await node.send(host, port, message)


def broadcast_change(peers, message, timeout=5):
    """Broadcast a JSON-serializable message to a list of peers (host:port tuples).

    peers: list of (host, port)
    message: dict
    """
    async def _run():
        tasks = []
        for host, port in peers:
            tasks.append(_send_to_peer(host, port, message))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    return asyncio.get_event_loop().run_until_complete(_run())

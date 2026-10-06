"""Simple gossip/broadcast prototype using P2PNode send API.
"""
import asyncio
import json
from .p2p import P2PNode


async def _send_to_peer(host, port, message, timeout=5):
    node = P2PNode()
    return await node.send(host, port, message, timeout=timeout)


def broadcast_change(peers, message, timeout=5):
    """Broadcast a JSON-serializable message to a list of peers (host:port tuples).

    peers: list of (host, port)
    message: dict
    """
    async def _run():
        tasks = []
        for host, port in peers:
            tasks.append(_send_to_peer(host, port, message, timeout=timeout))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    # asyncio.run, not get_event_loop(): the latter raises with no current loop
    # in worker threads and on Python 3.14+.
    return asyncio.run(_run())

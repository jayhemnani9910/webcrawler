import threading
import time
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.p2p import P2PNode
from src.gossip import broadcast_change


def test_broadcast_change():
    received = []

    def on_msg(msg):
        received.append(msg)

    node = P2PNode(host='127.0.0.1', port=9100, on_message=on_msg)

    def run_server():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(node.start())
        loop.run_forever()

    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(0.5)
    peers = [('127.0.0.1', 9100)]
    res = broadcast_change(peers, {'type': 'change', 'id': 123})
    time.sleep(0.2)
    assert received and received[0].get('id') == 123
